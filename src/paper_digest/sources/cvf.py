from __future__ import annotations

import re
from urllib.parse import urljoin

from paper_digest.config import Config
from paper_digest.http import HttpError, request_text
from paper_digest.models import Paper
from paper_digest.text import (
    build_unique_id,
    clean_whitespace,
    extract_year,
    matched_topics,
    max_topic_score,
    normalize_venue,
    score_topic_relevance,
)


CVF_BASE_URL = "https://openaccess.thecvf.com/"
CVF_VENUES = ("CVPR", "ICCV", "ECCV")


class CVFSource:
    def __init__(self, config: Config) -> None:
        self.config = config

    def fetch_candidates(self, years: tuple[int, ...]) -> list[Paper]:
        papers: list[Paper] = []
        for year in years:
            for venue in CVF_VENUES:
                url = f"{CVF_BASE_URL}{venue}{year}?day=all"
                try:
                    html = request_text(url, timeout=self.config.http_timeout)
                except HttpError:
                    continue
                papers.extend(self._parse_listing(html, venue=venue, year=year, listing_url=url))
        return papers

    def _parse_listing(self, html: str, *, venue: str, year: int, listing_url: str) -> list[Paper]:
        blocks = re.findall(
            r'(<dt\s+class="ptitle".*?</dt>\s*<dd>.*?)(?=<dt\s+class="ptitle"|</dl>|$)',
            html,
            flags=re.I | re.S,
        )
        papers: list[Paper] = []
        for block in blocks:
            paper = self._paper_from_block(block, venue=venue, year=year, listing_url=listing_url)
            if paper and paper.vlm_score > 0:
                papers.append(paper)
        return papers

    def _paper_from_block(self, block: str, *, venue: str, year: int, listing_url: str) -> Paper | None:
        title_match = re.search(
            r'<dt\s+class="ptitle".*?<a\s+href="(?P<href>[^"]+)".*?>(?P<title>.*?)</a>',
            block,
            flags=re.I | re.S,
        )
        if not title_match:
            return None
        title = _strip_html(title_match.group("title"))
        paper_url = urljoin(listing_url, title_match.group("href"))
        pdf_url = _extract_pdf_url(block, listing_url)
        author_match = re.search(r"</dt>\s*<dd>(?P<authors>.*?)</dd>", block, flags=re.I | re.S)
        authors = _split_authors(_strip_html(author_match.group("authors"))) if author_match else []
        inferred_year = extract_year(paper_url, pdf_url) or year
        topic_scores = score_topic_relevance(title, "", self.config.topics)
        unique_id = _cvf_unique_id(pdf_url or paper_url) or build_unique_id(title=title)
        return Paper(
            unique_id=unique_id,
            title=title,
            authors=authors,
            venue=normalize_venue(venue),
            year=inferred_year,
            paper_url=paper_url,
            pdf_url=pdf_url,
            vlm_score=max_topic_score(topic_scores),
            topics=matched_topics(topic_scores),
            topic_scores=topic_scores,
            source="cvf_openaccess",
            published_at=str(inferred_year) if inferred_year else None,
        )


def _extract_pdf_url(block: str, listing_url: str) -> str | None:
    for href in re.findall(r'href="([^"]+)"', block, flags=re.I):
        if ".pdf" in href.lower() and "/papers/" in href:
            return urljoin(listing_url, href)
    return None


def _strip_html(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return clean_whitespace(without_tags)


def _split_authors(value: str) -> list[str]:
    return [author.strip() for author in value.split(",") if author.strip()]


def _cvf_unique_id(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"/papers/([^/?#]+)", url, flags=re.I)
    if not match:
        return None
    slug = re.sub(r"_paper\.pdf$|\.html$", "", match.group(1), flags=re.I)
    return "cvf:" + slug.lower()
