from __future__ import annotations

import time
import urllib.parse
from typing import Any

from paper_digest.config import Config
from paper_digest.constants import TARGET_VENUES
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


FIELDS = ",".join(
    (
        "paperId",
        "externalIds",
        "title",
        "authors",
        "venue",
        "year",
        "url",
        "abstract",
        "openAccessPdf",
        "publicationVenue",
        "publicationDate",
        "tldr",
    )
)


class SemanticScholarSource:
    base_url = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, config: Config) -> None:
        self.config = config

    def enrich(self, papers: list[Paper], *, limit: int = 20) -> list[Paper]:
        enriched: list[Paper] = []
        for paper in papers[:limit]:
            try:
                enriched.append(self._enrich_one(paper))
            except HttpError:
                enriched.append(paper)
            time.sleep(0.12 if self.config.s2_api_key else 1.05)
        enriched.extend(papers[limit:])
        return enriched

    def search_venue_candidates(self, years: tuple[int, ...]) -> list[Paper]:
        results: list[Paper] = []
        for year in years:
            for topic in self.config.topics:
                params = {
                    "query": topic.query_text,
                    "year": str(year),
                    "limit": str(min(self.config.candidate_limit, 100)),
                    "fields": FIELDS,
                }
                url = f"{self.base_url}/paper/search?{urllib.parse.urlencode(params)}"
                try:
                    payload = request_json(url, headers=self._headers(), timeout=self.config.http_timeout)
                except HttpError:
                    continue
                for item in payload.get("data", []):
                    paper = self._paper_from_item(item)
                    if paper.venue and any(v.upper() in paper.venue.upper() for v in TARGET_VENUES):
                        results.append(paper)
                time.sleep(0.12 if self.config.s2_api_key else 1.05)
        return results

    def _enrich_one(self, paper: Paper) -> Paper:
        external_id = None
        if paper.arxiv_id:
            external_id = f"ARXIV:{paper.arxiv_id}"
        elif paper.doi:
            external_id = f"DOI:{paper.doi}"
        if not external_id:
            return paper
        url = f"{self.base_url}/paper/{urllib.parse.quote(external_id)}?fields={urllib.parse.quote(FIELDS)}"
        payload = request_json(url, headers=self._headers(), timeout=self.config.http_timeout)
        merged = self._paper_from_item(payload, unique_id=paper.unique_id)
        topic_scores = _merge_topic_scores(paper.topic_scores, merged.topic_scores)
        return Paper(
            unique_id=paper.unique_id,
            title=merged.title or paper.title,
            authors=merged.authors or paper.authors,
            venue=merged.venue or paper.venue,
            year=merged.year or paper.year,
            paper_url=paper.paper_url or merged.paper_url,
            pdf_url=paper.pdf_url or merged.pdf_url,
            code_url=paper.code_url or merged.code_url,
            abstract=paper.abstract or merged.abstract,
            vlm_score=max(paper.vlm_score, merged.vlm_score),
            topics=sorted(set(paper.topics + merged.topics)),
            topic_scores=topic_scores,
            source=f"{paper.source},semantic_scholar",
            discovered_at=paper.discovered_at,
            published_at=paper.published_at or merged.published_at,
            doi=paper.doi or merged.doi,
            arxiv_id=paper.arxiv_id or merged.arxiv_id,
            openreview_id=paper.openreview_id or merged.openreview_id,
            semantic_scholar_id=merged.semantic_scholar_id or paper.semantic_scholar_id,
        )

    def _paper_from_item(self, item: dict[str, Any], unique_id: str | None = None) -> Paper:
        title = clean_whitespace(item.get("title") or "")
        authors = [clean_whitespace(author.get("name")) for author in item.get("authors", []) if author.get("name")]
        publication_venue = item.get("publicationVenue") or {}
        alternate_names = publication_venue.get("alternate_names") or []
        venue = normalize_venue(
            item.get("venue")
            or publication_venue.get("name")
            or (alternate_names[0] if alternate_names else None)
        )
        abstract = clean_whitespace(item.get("abstract") or "")
        external = item.get("externalIds") or {}
        doi = external.get("DOI")
        arxiv_id = external.get("ArXiv")
        openreview_id = external.get("OpenReview")
        paper_id = item.get("paperId")
        pdf_url = (item.get("openAccessPdf") or {}).get("url")
        tldr = (item.get("tldr") or {}).get("text")
        code_url = extract_code_url(abstract, tldr, item.get("url"), pdf_url)
        topic_scores = score_topic_relevance(title, f"{abstract}\n{tldr or ''}", self.config.topics)
        resolved_id = unique_id or build_unique_id(
            title=title,
            doi=doi,
            arxiv_id=arxiv_id,
            openreview_id=openreview_id,
            semantic_scholar_id=paper_id,
        )
        return Paper(
            unique_id=resolved_id,
            title=title,
            authors=authors,
            venue=venue,
            year=item.get("year"),
            paper_url=item.get("url"),
            pdf_url=pdf_url,
            code_url=code_url,
            abstract=abstract or tldr,
            vlm_score=max_topic_score(topic_scores),
            topics=matched_topics(topic_scores),
            topic_scores=topic_scores,
            source="semantic_scholar",
            published_at=item.get("publicationDate"),
            doi=doi,
            arxiv_id=arxiv_id,
            openreview_id=openreview_id,
            semantic_scholar_id=paper_id,
        )

    def _headers(self) -> dict[str, str]:
        if self.config.s2_api_key:
            return {"x-api-key": self.config.s2_api_key}
        return {}


def _merge_topic_scores(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    merged = dict(left)
    for topic_id, score in right.items():
        merged[topic_id] = max(float(score), float(merged.get(topic_id, 0)))
    return merged
