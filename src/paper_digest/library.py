from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from paper_digest.models import Paper, utc_now_iso
from paper_digest.text import is_target_venue, title_hash


class PaperLibrary:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self.init_schema()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "PaperLibrary":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS papers (
                unique_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                authors_json TEXT NOT NULL DEFAULT '[]',
                venue TEXT,
                year INTEGER,
                paper_url TEXT,
                pdf_url TEXT,
                code_url TEXT,
                abstract TEXT,
                vlm_score REAL NOT NULL DEFAULT 0,
                topics_json TEXT NOT NULL DEFAULT '[]',
                topic_scores_json TEXT NOT NULL DEFAULT '{}',
                source TEXT NOT NULL DEFAULT 'unknown',
                discovered_at TEXT NOT NULL,
                published_at TEXT,
                doi TEXT,
                arxiv_id TEXT,
                openreview_id TEXT,
                semantic_scholar_id TEXT,
                summary_json TEXT,
                sent INTEGER NOT NULL DEFAULT 0,
                sent_at TEXT,
                send_error TEXT,
                is_target_venue INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_papers_sent ON papers(sent);
            CREATE INDEX IF NOT EXISTS idx_papers_rank
                ON papers(sent, is_target_venue, year, vlm_score, published_at);
            CREATE INDEX IF NOT EXISTS idx_papers_arxiv ON papers(arxiv_id);
            CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
            CREATE INDEX IF NOT EXISTS idx_papers_s2 ON papers(semantic_scholar_id);
            """
        )
        self._add_missing_columns()
        self._conn.commit()

    def _add_missing_columns(self) -> None:
        columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(papers)").fetchall()
        }
        if "topics_json" not in columns:
            self._conn.execute("ALTER TABLE papers ADD COLUMN topics_json TEXT NOT NULL DEFAULT '[]'")
        if "topic_scores_json" not in columns:
            self._conn.execute("ALTER TABLE papers ADD COLUMN topic_scores_json TEXT NOT NULL DEFAULT '{}'")
        self._conn.execute(
            """
            UPDATE papers
            SET topics_json = '["vlm"]',
                topic_scores_json = printf('{"vlm": %.6g}', vlm_score)
            WHERE topics_json = '[]'
              AND vlm_score > 0
            """
        )

    def upsert_paper(self, paper: Paper) -> None:
        existing = self.get_paper(paper.unique_id)
        if existing:
            paper.topics = sorted(set(existing.topics + paper.topics))
            paper.topic_scores = self._merge_topic_scores(existing.topic_scores, paper.topic_scores)
            paper.vlm_score = max(existing.vlm_score, paper.vlm_score, max(paper.topic_scores.values(), default=0.0))
        now = utc_now_iso()
        authors_json = json.dumps(paper.authors, ensure_ascii=False)
        topics_json = json.dumps(paper.topics, ensure_ascii=False)
        topic_scores_json = json.dumps(paper.topic_scores, ensure_ascii=False)
        summary_json = json.dumps(paper.summary_json, ensure_ascii=False) if paper.summary_json else None
        target = 1 if is_target_venue(paper.venue) else 0
        self._conn.execute(
            """
            INSERT INTO papers (
                unique_id, title, authors_json, venue, year, paper_url, pdf_url,
                code_url, abstract, vlm_score, topics_json, topic_scores_json, source, discovered_at, published_at,
                doi, arxiv_id, openreview_id, semantic_scholar_id, summary_json,
                sent, sent_at, send_error, is_target_venue, updated_at
            )
            VALUES (
                :unique_id, :title, :authors_json, :venue, :year, :paper_url, :pdf_url,
                :code_url, :abstract, :vlm_score, :topics_json, :topic_scores_json, :source, :discovered_at, :published_at,
                :doi, :arxiv_id, :openreview_id, :semantic_scholar_id, :summary_json,
                :sent, :sent_at, :send_error, :is_target_venue, :updated_at
            )
            ON CONFLICT(unique_id) DO UPDATE SET
                title = excluded.title,
                authors_json = CASE
                    WHEN excluded.authors_json != '[]' THEN excluded.authors_json
                    ELSE papers.authors_json
                END,
                venue = COALESCE(excluded.venue, papers.venue),
                year = COALESCE(excluded.year, papers.year),
                paper_url = COALESCE(excluded.paper_url, papers.paper_url),
                pdf_url = COALESCE(excluded.pdf_url, papers.pdf_url),
                code_url = COALESCE(excluded.code_url, papers.code_url),
                abstract = COALESCE(excluded.abstract, papers.abstract),
                vlm_score = MAX(excluded.vlm_score, papers.vlm_score),
                topics_json = CASE
                    WHEN excluded.topics_json != '[]' THEN excluded.topics_json
                    ELSE papers.topics_json
                END,
                topic_scores_json = CASE
                    WHEN excluded.topic_scores_json != '{}' THEN excluded.topic_scores_json
                    ELSE papers.topic_scores_json
                END,
                source = CASE
                    WHEN instr(papers.source, excluded.source) > 0 THEN papers.source
                    ELSE papers.source || ',' || excluded.source
                END,
                published_at = COALESCE(excluded.published_at, papers.published_at),
                doi = COALESCE(excluded.doi, papers.doi),
                arxiv_id = COALESCE(excluded.arxiv_id, papers.arxiv_id),
                openreview_id = COALESCE(excluded.openreview_id, papers.openreview_id),
                semantic_scholar_id = COALESCE(excluded.semantic_scholar_id, papers.semantic_scholar_id),
                summary_json = COALESCE(excluded.summary_json, papers.summary_json),
                send_error = CASE WHEN papers.sent = 1 THEN papers.send_error ELSE NULL END,
                is_target_venue = MAX(excluded.is_target_venue, papers.is_target_venue),
                updated_at = excluded.updated_at
            """,
            {
                "unique_id": paper.unique_id,
                "title": paper.title,
                "authors_json": authors_json,
                "venue": paper.venue,
                "year": paper.year,
                "paper_url": paper.paper_url,
                "pdf_url": paper.pdf_url,
                "code_url": paper.code_url,
                "abstract": paper.abstract,
                "vlm_score": paper.vlm_score,
                "topics_json": topics_json,
                "topic_scores_json": topic_scores_json,
                "source": paper.source,
                "discovered_at": paper.discovered_at,
                "published_at": paper.published_at,
                "doi": paper.doi,
                "arxiv_id": paper.arxiv_id,
                "openreview_id": paper.openreview_id,
                "semantic_scholar_id": paper.semantic_scholar_id,
                "summary_json": summary_json,
                "sent": int(paper.sent),
                "sent_at": paper.sent_at,
                "send_error": paper.send_error,
                "is_target_venue": target,
                "updated_at": now,
            },
        )
        self._conn.commit()

    def upsert_many(self, papers: Iterable[Paper]) -> int:
        count = 0
        for paper in papers:
            self.upsert_paper(paper)
            count += 1
        return count

    def get_paper(self, unique_id: str) -> Paper | None:
        row = self._conn.execute("SELECT * FROM papers WHERE unique_id = ?", (unique_id,)).fetchone()
        return self._row_to_paper(row) if row else None

    def find_by_pdf_url(self, pdf_url: str) -> Paper | None:
        row = self._conn.execute("SELECT * FROM papers WHERE pdf_url = ? LIMIT 1", (pdf_url,)).fetchone()
        return self._row_to_paper(row) if row else None

    def find_by_title_hash(self, normalized_title_hash: str) -> Paper | None:
        for row in self._conn.execute("SELECT * FROM papers").fetchall():
            paper = self._row_to_paper(row)
            if title_hash(paper.title) == normalized_title_hash:
                return paper
        return None

    def choose_next_paper(self, venue_years: tuple[int, ...], active_topic_ids: tuple[str, ...] = ("vlm",)) -> Paper | None:
        placeholders = ",".join("?" for _ in venue_years)
        rows = self._conn.execute(
            f"""
            SELECT *
            FROM papers
            WHERE sent = 0
              AND is_target_venue = 1
              AND vlm_score > 0
              AND (year IS NULL OR year IN ({placeholders}))
            """,
            venue_years,
        ).fetchall()
        matched: list[Paper] = []
        for row in rows:
            paper = self._row_to_paper(row)
            if self._matches_active_topics(paper, active_topic_ids):
                matched.append(paper)
        matched.sort(key=lambda paper: self._selection_key(paper, venue_years, active_topic_ids))
        return matched[0] if matched else None

    def update_summary(self, unique_id: str, summary: dict[str, object], code_url: str | None = None) -> None:
        self._conn.execute(
            """
            UPDATE papers
            SET summary_json = ?,
                code_url = COALESCE(?, code_url),
                updated_at = ?
            WHERE unique_id = ?
            """,
            (json.dumps(summary, ensure_ascii=False), code_url, utc_now_iso(), unique_id),
        )
        self._conn.commit()

    def mark_sent(self, unique_id: str) -> None:
        self._conn.execute(
            """
            UPDATE papers
            SET sent = 1,
                sent_at = ?,
                send_error = NULL,
                updated_at = ?
            WHERE unique_id = ?
            """,
            (utc_now_iso(), utc_now_iso(), unique_id),
        )
        self._conn.commit()

    def record_send_error(self, unique_id: str, error: str) -> None:
        self._conn.execute(
            """
            UPDATE papers
            SET sent = 0,
                send_error = ?,
                updated_at = ?
            WHERE unique_id = ?
            """,
            (error[:1000], utc_now_iso(), unique_id),
        )
        self._conn.commit()

    def stats(self) -> dict[str, int]:
        row = self._conn.execute(
            """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN sent = 1 THEN 1 ELSE 0 END) AS sent,
              SUM(CASE WHEN sent = 0 THEN 1 ELSE 0 END) AS unsent,
              SUM(CASE WHEN is_target_venue = 1 THEN 1 ELSE 0 END) AS target_venue,
              SUM(CASE WHEN topics_json != '[]' THEN 1 ELSE 0 END) AS topic_tagged
            FROM papers
            """
        ).fetchone()
        return {key: int(row[key] or 0) for key in row.keys()}

    def topic_stats(self) -> list[dict[str, int | str]]:
        stats: dict[str, dict[str, int | str]] = {}
        for paper in self.all_papers():
            for topic_id in _paper_topic_ids(paper):
                item = stats.setdefault(topic_id, {"topic_id": topic_id, "total": 0, "sent": 0, "unsent": 0})
                item["total"] = int(item["total"]) + 1
                if paper.sent:
                    item["sent"] = int(item["sent"]) + 1
                else:
                    item["unsent"] = int(item["unsent"]) + 1
        return sorted(
            stats.values(),
            key=lambda item: (-int(item["total"]), str(item["topic_id"])),
        )

    def sent_papers_by_topic(self, topic_id: str) -> list[Paper]:
        normalized_topic_id = topic_id.strip().lower()
        papers = [
            paper
            for paper in self.all_papers()
            if paper.sent and normalized_topic_id in _paper_topic_ids(paper)
        ]
        papers.sort(key=lambda paper: (paper.sent_at or "", paper.title), reverse=True)
        return papers

    def all_papers(self) -> list[Paper]:
        rows = self._conn.execute("SELECT * FROM papers ORDER BY updated_at DESC, title ASC").fetchall()
        return [self._row_to_paper(row) for row in rows]

    @staticmethod
    def _year_priority_case(venue_years: tuple[int, ...]) -> str:
        return " ".join(f"WHEN year = {year} THEN {idx}" for idx, year in enumerate(venue_years))

    @staticmethod
    def _matches_active_topics(paper: Paper, active_topic_ids: tuple[str, ...]) -> bool:
        active = {topic_id.lower() for topic_id in active_topic_ids}
        paper_topics = {topic_id.lower() for topic_id in paper.topics}
        if paper_topics:
            return bool(active & paper_topics)
        return "vlm" in active and paper.vlm_score > 0

    @classmethod
    def _selection_key(
        cls,
        paper: Paper,
        venue_years: tuple[int, ...],
        active_topic_ids: tuple[str, ...],
    ) -> tuple[int, float, float, str]:
        year_priority = venue_years.index(paper.year) if paper.year in venue_years else 999
        active_score = cls._active_topic_score(paper, active_topic_ids)
        return (year_priority, -active_score, -cls._date_value(paper.published_at or paper.discovered_at), paper.title)

    @staticmethod
    def _active_topic_score(paper: Paper, active_topic_ids: tuple[str, ...]) -> float:
        active = tuple(topic_id.lower() for topic_id in active_topic_ids)
        scores = [float(paper.topic_scores.get(topic_id, 0)) for topic_id in active]
        if not any(scores) and "vlm" in active:
            scores.append(float(paper.vlm_score or 0))
        return max(scores, default=0.0)

    @staticmethod
    def _date_value(value: str | None) -> float:
        if not value:
            return 0.0
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized).timestamp()
        except ValueError:
            try:
                return datetime.strptime(value[:10], "%Y-%m-%d").timestamp()
            except ValueError:
                return 0.0

    @staticmethod
    def _merge_topic_scores(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
        merged = dict(left)
        for topic_id, score in right.items():
            merged[topic_id] = max(float(score), float(merged.get(topic_id, 0)))
        return merged

    @staticmethod
    def _row_to_paper(row: sqlite3.Row) -> Paper:
        summary = json.loads(row["summary_json"]) if row["summary_json"] else None
        topics = json.loads(row["topics_json"] or "[]") if "topics_json" in row.keys() else []
        topic_scores = json.loads(row["topic_scores_json"] or "{}") if "topic_scores_json" in row.keys() else {}
        if not topics and float(row["vlm_score"] or 0) > 0:
            topics = ["vlm"]
            topic_scores = {"vlm": float(row["vlm_score"] or 0)}
        return Paper(
            unique_id=row["unique_id"],
            title=row["title"],
            authors=json.loads(row["authors_json"] or "[]"),
            venue=row["venue"],
            year=row["year"],
            paper_url=row["paper_url"],
            pdf_url=row["pdf_url"],
            code_url=row["code_url"],
            abstract=row["abstract"],
            vlm_score=float(row["vlm_score"] or 0),
            topics=topics,
            topic_scores=topic_scores,
            source=row["source"],
            discovered_at=row["discovered_at"],
            published_at=row["published_at"],
            doi=row["doi"],
            arxiv_id=row["arxiv_id"],
            openreview_id=row["openreview_id"],
            semantic_scholar_id=row["semantic_scholar_id"],
            summary_json=summary,
            sent=bool(row["sent"]),
            sent_at=row["sent_at"],
            send_error=row["send_error"],
        )


def _paper_topic_ids(paper: Paper) -> tuple[str, ...]:
    topics = tuple(dict.fromkeys(topic.strip().lower() for topic in paper.topics if topic.strip()))
    if topics:
        return topics
    if paper.vlm_score > 0:
        return ("vlm",)
    return ("untagged",)
