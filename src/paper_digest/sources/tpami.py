from __future__ import annotations

import time
import urllib.parse

from paper_digest.config import Config
from paper_digest.http import HttpError, request_json
from paper_digest.models import Paper
from paper_digest.sources.semantic_scholar import FIELDS, SemanticScholarSource
from paper_digest.text import normalize_venue


TPAMI_QUERY_PREFIX = '"IEEE Transactions on Pattern Analysis and Machine Intelligence"'


class TPAMISource:
    base_url = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, config: Config) -> None:
        self.config = config
        self.semantic_scholar = SemanticScholarSource(config)

    def fetch_candidates(self, years: tuple[int, ...]) -> list[Paper]:
        papers: list[Paper] = []
        for year in years:
            for topic in self.config.topics:
                params = {
                    "query": f"{TPAMI_QUERY_PREFIX} {topic.query_text}",
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
                    paper = self.semantic_scholar._paper_from_item(item)
                    if _is_tpami(paper.venue):
                        paper.source = "tpami_semantic_scholar"
                        papers.append(paper)
                time.sleep(0.12 if self.config.s2_api_key else 1.05)
        return papers

    def _headers(self) -> dict[str, str]:
        if self.config.s2_api_key:
            return {"x-api-key": self.config.s2_api_key}
        return {}


def _is_tpami(venue: str | None) -> bool:
    normalized = normalize_venue(venue)
    if not normalized:
        return False
    upper = normalized.upper()
    return "TPAMI" in upper or "PATTERN ANALYSIS AND MACHINE INTELLIGENCE" in upper
