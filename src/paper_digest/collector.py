from __future__ import annotations

from dataclasses import dataclass, replace
from math import ceil

from paper_digest.config import Config
from paper_digest.library import PaperLibrary
from paper_digest.models import Paper
from paper_digest.progress import StageProgress
from paper_digest.sources.arxiv import ArxivSource
from paper_digest.sources.cvf import CVFSource
from paper_digest.sources.openreview import OpenReviewSource
from paper_digest.sources.semantic_scholar import SemanticScholarSource
from paper_digest.sources.tpami import TPAMISource


DEFAULT_COLLECT_SOURCES = ("cvf", "openreview")
SUPPORTED_COLLECT_SOURCES = ("cvf", "openreview", "arxiv", "semantic_scholar", "tpami")


@dataclass(slots=True)
class CollectResult:
    candidates: int
    selected: int
    upserted: int
    source_counts: dict[str, int]
    errors: list[str]


class PaperCollector:
    def __init__(self, config: Config, *, progress: StageProgress | None = None) -> None:
        self.config = config
        self.progress = progress

    def collect(
        self,
        *,
        topic_ids: tuple[str, ...],
        years: tuple[int, ...],
        sources: tuple[str, ...] = DEFAULT_COLLECT_SOURCES,
        limit: int = 100,
        include_existing: bool = False,
        balance: bool = True,
    ) -> CollectResult:
        collect_config = self._config_for_topic_ids(topic_ids)
        source_counts: dict[str, int] = {}
        errors: list[str] = []
        candidates: list[Paper] = []

        with PaperLibrary(collect_config.db_path) as library:
            self._step(
                "Preparing collection for "
                f"topics: {', '.join(topic_ids)}; years: {', '.join(str(year) for year in years)}"
            )
            existing_ids = {paper.unique_id for paper in library.all_papers()}

            for source in sources:
                self._step(f"Fetching {source} candidates")
                try:
                    source_papers = self._fetch_source(source, collect_config, years)
                except Exception as exc:
                    source_papers = []
                    errors.append(f"{source} failed: {exc}")
                    self._info(f"{source} failed: {exc}")
                source_counts[source] = len(source_papers)
                candidates.extend(source_papers)
                self._info(f"{source}: {len(source_papers)} candidates")

            unique_candidates = _unique_papers(candidates)
            self._step(f"Selecting up to {limit} papers")
            selected = select_papers_for_collection(
                unique_candidates,
                topic_ids=topic_ids,
                limit=limit,
                existing_ids=set() if include_existing else existing_ids,
                balance=balance,
            )
            self._info(f"selected: {len(selected)} papers")

            self._step("Writing selected papers to library")
            upserted = library.upsert_many(selected)
            self._info(f"stored/updated: {upserted} papers")

        self._finish("Collection complete")
        return CollectResult(
            candidates=len(unique_candidates),
            selected=len(selected),
            upserted=upserted,
            source_counts=source_counts,
            errors=errors,
        )

    def _fetch_source(self, source: str, config: Config, years: tuple[int, ...]) -> list[Paper]:
        if source == "cvf":
            return CVFSource(config).fetch_candidates(years)
        if source == "openreview":
            return OpenReviewSource(config).fetch_candidates(years)
        if source == "arxiv":
            arxiv = ArxivSource(config)
            papers: list[Paper] = []
            for year in years:
                papers.extend(arxiv.fetch_year(year))
            return papers
        if source == "semantic_scholar":
            return SemanticScholarSource(config).search_venue_candidates(years)
        if source == "tpami":
            return TPAMISource(config).fetch_candidates(years)
        raise ValueError(f"Unsupported collect source: {source}")

    def _config_for_topic_ids(self, topic_ids: tuple[str, ...]) -> Config:
        topics = self.config.topics_for_ids(topic_ids)
        if not topics:
            return self.config
        return replace(self.config, topic_ids=topic_ids, topics=topics)

    def _step(self, message: str) -> None:
        if self.progress:
            self.progress.step(message)

    def _info(self, message: str) -> None:
        if self.progress:
            self.progress.info(message)

    def _finish(self, message: str) -> None:
        if self.progress:
            self.progress.finish(message)


def select_papers_for_collection(
    candidates: list[Paper],
    *,
    topic_ids: tuple[str, ...],
    limit: int,
    existing_ids: set[str],
    balance: bool = True,
) -> list[Paper]:
    fresh = [paper for paper in candidates if paper.unique_id not in existing_ids]
    fresh.sort(key=lambda paper: (-_max_score(paper, topic_ids), paper.title))
    if limit <= 0:
        return []
    if not balance or len(topic_ids) <= 1:
        return fresh[:limit]

    selected: list[Paper] = []
    selected_ids: set[str] = set()
    per_topic = ceil(limit / len(topic_ids))
    for topic_id in topic_ids:
        pool = [paper for paper in fresh if topic_id in paper.topics and paper.unique_id not in selected_ids]
        pool.sort(key=lambda paper: (-_topic_score(paper, topic_id), paper.title))
        for paper in pool[:per_topic]:
            selected.append(paper)
            selected_ids.add(paper.unique_id)
            if len(selected) >= limit:
                return selected

    for paper in fresh:
        if paper.unique_id in selected_ids:
            continue
        selected.append(paper)
        selected_ids.add(paper.unique_id)
        if len(selected) >= limit:
            break
    return selected


def parse_collect_sources(value: str | None) -> tuple[str, ...]:
    if not value:
        return DEFAULT_COLLECT_SOURCES
    sources = tuple(dict.fromkeys(item.strip().lower() for item in value.split(",") if item.strip()))
    unknown = sorted(set(sources) - set(SUPPORTED_COLLECT_SOURCES))
    if unknown:
        raise ValueError(
            "Unsupported collect source(s): "
            f"{', '.join(unknown)}. Supported: {', '.join(SUPPORTED_COLLECT_SOURCES)}."
        )
    return sources or DEFAULT_COLLECT_SOURCES


def _unique_papers(papers: list[Paper]) -> list[Paper]:
    seen: set[str] = set()
    unique: list[Paper] = []
    for paper in papers:
        if paper.unique_id in seen:
            continue
        seen.add(paper.unique_id)
        unique.append(paper)
    return unique


def _topic_score(paper: Paper, topic_id: str) -> float:
    return float(paper.topic_scores.get(topic_id, 0.0))


def _max_score(paper: Paper, topic_ids: tuple[str, ...]) -> float:
    return max((_topic_score(paper, topic_id) for topic_id in topic_ids), default=0.0)
