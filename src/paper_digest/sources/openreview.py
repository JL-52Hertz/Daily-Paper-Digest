from __future__ import annotations

import urllib.parse

from paper_digest.config import Config
from paper_digest.http import HttpError, request_json
from paper_digest.models import Paper
from paper_digest.text import (
    build_unique_id,
    clean_whitespace,
    extract_code_url,
    matched_topics,
    max_topic_score,
    normalize_venue,
    score_topic_relevance,
)
from paper_digest.topics import TopicProfile


OPENREVIEW_VENUES = (
    "ICLR.cc/{year}/Conference",
    "NeurIPS.cc/{year}/Conference",
    "ICML.cc/{year}/Conference",
    "AAAI.org/{year}/Conference",
)


class OpenReviewSource:
    base_url = "https://api2.openreview.net"

    def __init__(self, config: Config) -> None:
        self.config = config

    def fetch_candidates(self, years: tuple[int, ...]) -> list[Paper]:
        papers: list[Paper] = []
        for year in years:
            for template in OPENREVIEW_VENUES:
                venue_id = template.format(year=year)
                params = {
                    "content.venueid": venue_id,
                    "limit": str(min(self.config.candidate_limit, 50)),
                }
                url = f"{self.base_url}/notes?{urllib.parse.urlencode(params)}"
                try:
                    payload = request_json(url, timeout=self.config.http_timeout)
                except HttpError:
                    continue
                for note in payload.get("notes", []):
                    paper = self._paper_from_note(note, venue_id, year, self.config.topics)
                    if paper.vlm_score > 0:
                        papers.append(paper)
        return papers

    @staticmethod
    def _paper_from_note(
        note: dict[str, object],
        venue_id: str,
        year: int,
        topics: tuple[TopicProfile, ...],
    ) -> Paper:
        content = note.get("content") if isinstance(note.get("content"), dict) else {}
        assert isinstance(content, dict)
        title = _content_value(content.get("title"))
        abstract = _content_value(content.get("abstract"))
        authors_value = content.get("authors")
        authors = authors_value.get("value", []) if isinstance(authors_value, dict) else []
        authors = [str(author) for author in authors if str(author).strip()]
        note_id = str(note.get("id") or "")
        forum_id = str(note.get("forum") or note_id)
        paper_url = f"https://openreview.net/forum?id={forum_id}" if forum_id else None
        pdf_url = f"https://openreview.net/pdf?id={forum_id}" if forum_id else None
        venue = normalize_venue(venue_id)
        code_url = extract_code_url(abstract, paper_url)
        topic_scores = score_topic_relevance(title, abstract, topics)
        return Paper(
            unique_id=build_unique_id(title=title, openreview_id=forum_id or note_id),
            title=title,
            authors=authors,
            venue=venue,
            year=year,
            paper_url=paper_url,
            pdf_url=pdf_url,
            code_url=code_url,
            abstract=abstract,
            vlm_score=max_topic_score(topic_scores),
            topics=matched_topics(topic_scores),
            topic_scores=topic_scores,
            source="openreview",
            openreview_id=forum_id or note_id,
        )


def _content_value(value: object) -> str:
    if isinstance(value, dict):
        return clean_whitespace(str(value.get("value") or ""))
    return clean_whitespace(str(value or ""))
