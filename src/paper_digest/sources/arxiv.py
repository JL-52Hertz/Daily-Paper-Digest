from __future__ import annotations

import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from paper_digest.config import Config
from paper_digest.http import request_text
from paper_digest.models import Paper
from paper_digest.text import (
    build_unique_id,
    clean_whitespace,
    extract_code_url,
    extract_year,
    matched_topics,
    max_topic_score,
    normalize_venue,
    score_topic_relevance,
)
from paper_digest.topics import BUILTIN_TOPICS, TopicProfile

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"


class ArxivSource:
    endpoint = "https://export.arxiv.org/api/query"

    def __init__(self, config: Config) -> None:
        self.config = config

    def fetch_recent(self) -> list[Paper]:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=self.config.lookback_days)
        date_filter = f"submittedDate:[{start:%Y%m%d%H%M} TO {now:%Y%m%d%H%M}]"
        return self._fetch(date_filter=date_filter, max_results=self.config.candidate_limit)

    def fetch_year(self, year: int) -> list[Paper]:
        date_filter = f"submittedDate:[{year}01010000 TO {year}12312359]"
        return self._fetch(date_filter=date_filter, max_results=self.config.candidate_limit)

    def _fetch(self, *, date_filter: str, max_results: int) -> list[Paper]:
        query = f"({self._category_query(self.config.topics)}) AND ({self._topic_query(self.config.topics)}) AND {date_filter}"
        params = {
            "search_query": query,
            "start": "0",
            "max_results": str(max_results),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"{self.endpoint}?{urllib.parse.urlencode(params)}"
        feed = request_text(url, timeout=self.config.http_timeout)
        return self._parse_feed(feed, topics=self.config.topics)

    @staticmethod
    def _category_query(topics: tuple[TopicProfile, ...]) -> str:
        categories: list[str] = []
        for topic in topics:
            categories.extend(topic.categories)
        if not categories:
            categories = ["cs.CV", "cs.CL", "cs.AI", "cs.LG"]
        return " OR ".join(f"cat:{cat}" for cat in sorted(set(categories)))

    @staticmethod
    def _topic_query(topics: tuple[TopicProfile, ...]) -> str:
        terms: list[str] = []
        for topic in topics:
            terms.extend(topic.arxiv_terms or topic.keywords[:10])
        if not terms:
            terms = ["vision language", "multimodal"]
        return " OR ".join(_arxiv_all_term(term) for term in sorted(set(terms), key=str.lower))

    @staticmethod
    def _parse_feed(feed: str, topics: tuple[TopicProfile, ...] | None = None) -> list[Paper]:
        active_topics = topics or (BUILTIN_TOPICS["vlm"],)
        root = ET.fromstring(feed)
        papers: list[Paper] = []
        for entry in root.findall(f"{ATOM}entry"):
            title = clean_whitespace(_text(entry, f"{ATOM}title"))
            abstract = clean_whitespace(_text(entry, f"{ATOM}summary"))
            paper_url = clean_whitespace(_text(entry, f"{ATOM}id")) or None
            arxiv_id = _extract_arxiv_id(paper_url)
            pdf_url = _pdf_url(entry, arxiv_id)
            authors = [
                clean_whitespace(_text(author, f"{ATOM}name"))
                for author in entry.findall(f"{ATOM}author")
                if clean_whitespace(_text(author, f"{ATOM}name"))
            ]
            published_at = clean_whitespace(_text(entry, f"{ATOM}published")) or None
            updated_at = clean_whitespace(_text(entry, f"{ATOM}updated")) or None
            doi = clean_whitespace(_text(entry, f"{ARXIV}doi")) or None
            comment = clean_whitespace(_text(entry, f"{ARXIV}comment")) or None
            journal_ref = clean_whitespace(_text(entry, f"{ARXIV}journal_ref")) or None
            venue = normalize_venue(journal_ref or comment)
            year = extract_year(journal_ref, comment, published_at, updated_at)
            code_url = extract_code_url(comment, abstract)
            topic_scores = score_topic_relevance(title, abstract, active_topics)
            unique_id = build_unique_id(title=title, doi=doi, arxiv_id=arxiv_id)
            papers.append(
                Paper(
                    unique_id=unique_id,
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
                    source="arxiv",
                    published_at=published_at,
                    doi=doi,
                    arxiv_id=arxiv_id,
                )
            )
        return papers


def _text(element: ET.Element, path: str) -> str:
    found = element.find(path)
    return found.text if found is not None and found.text else ""


def _extract_arxiv_id(paper_url: str | None) -> str | None:
    if not paper_url:
        return None
    match = re.search(r"/abs/([^/?#]+)", paper_url)
    if not match:
        return None
    return re.sub(r"v\d+$", "", match.group(1))


def _pdf_url(entry: ET.Element, arxiv_id: str | None) -> str | None:
    for link in entry.findall(f"{ATOM}link"):
        title = link.attrib.get("title", "").lower()
        mime = link.attrib.get("type", "").lower()
        href = link.attrib.get("href")
        if href and (title == "pdf" or mime == "application/pdf"):
            return href
    if arxiv_id:
        return f"https://arxiv.org/pdf/{arxiv_id}"
    return None


def _arxiv_all_term(term: str) -> str:
    escaped = term.replace('"', "")
    if re.search(r"\s|-", escaped):
        return f'all:"{escaped}"'
    return f"all:{escaped}"
