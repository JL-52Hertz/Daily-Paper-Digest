from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import unquote

from paper_digest.config import Config
from paper_digest.http import request_bytes_with_progress
from paper_digest.library import PaperLibrary
from paper_digest.models import Paper
from paper_digest.pdf_text import extract_pdf_text
from paper_digest.progress import Progress
from paper_digest.text import (
    build_unique_id,
    clean_whitespace,
    extract_code_url,
    extract_year,
    matched_topics,
    max_topic_score,
    normalize_venue,
    score_topic_relevance,
    title_hash,
)
from paper_digest.topics import TopicProfile


@dataclass(slots=True)
class ImportOptions:
    title: str | None = None
    authors: list[str] | None = None
    venue: str | None = None
    year: int | None = None
    paper_url: str | None = None
    pdf_url: str | None = None
    code_url: str | None = None
    abstract: str | None = None
    topics: tuple[str, ...] | None = None
    force_sent: bool = False


@dataclass(slots=True)
class ImportResult:
    paper: Paper
    inserted: bool
    existing_id: str | None = None

    @property
    def message(self) -> str:
        action = "imported" if self.inserted else "updated existing"
        return f"{action}: {self.paper.unique_id} - {self.paper.title}"


class PaperImporter:
    def __init__(self, config: Config, library: PaperLibrary) -> None:
        self.config = config
        self.library = library

    def import_url(
        self,
        pdf_url: str,
        options: ImportOptions | None = None,
        *,
        extract_text: bool = True,
        show_progress: bool = True,
    ) -> ImportResult:
        options = options or ImportOptions()
        text = ""
        if extract_text:
            raw_pdf = request_bytes_with_progress(
                pdf_url,
                timeout=self.config.http_timeout,
                headers={"Accept": "application/pdf"},
                label="Downloading PDF",
                progress=show_progress,
            )
            text = extract_pdf_text(raw_pdf, max_chars=self.config.max_pdf_chars, progress=show_progress)
        inferred_title = _title_from_url(pdf_url)
        resolved = replace(
            options,
            title=options.title or inferred_title,
            pdf_url=pdf_url,
            paper_url=options.paper_url or _paper_url_from_pdf_url(pdf_url),
        )
        paper = self._paper_from_text(text, source="manual_url", options=resolved)
        return self._upsert_with_dedupe(paper)

    def import_file(
        self,
        pdf_path: Path | str,
        options: ImportOptions | None = None,
        *,
        extract_text: bool = True,
        show_progress: bool = True,
    ) -> ImportResult:
        options = options or ImportOptions()
        path = Path(pdf_path)
        text = ""
        if extract_text:
            reporter = Progress(label="Reading PDF", total=path.stat().st_size, enabled=show_progress, unit="B")
            reporter.start()
            raw_pdf = path.read_bytes()
            reporter.update(len(raw_pdf))
            reporter.finish()
            text = extract_pdf_text(raw_pdf, max_chars=self.config.max_pdf_chars, progress=show_progress)
        fallback_title = options.title or _title_from_filename(path)
        resolved = replace(options, title=fallback_title)
        paper = self._paper_from_text(text, source="manual_file", options=resolved)
        return self._upsert_with_dedupe(paper)

    def _paper_from_text(self, text: str, *, source: str, options: ImportOptions) -> Paper:
        title = clean_whitespace(options.title or _title_from_pdf_text(text) or "Untitled imported paper")
        abstract = clean_whitespace(options.abstract or _abstract_from_pdf_text(text))
        venue = normalize_venue(options.venue or _venue_from_url(options.pdf_url) or _venue_from_text(text))
        year = options.year or extract_year(options.pdf_url, options.paper_url, text[:2000])
        authors = options.authors or []
        topic_profiles = self._topic_profiles(options.topics)
        topic_scores = score_topic_relevance(title, f"{abstract}\n{text[:4000]}", topic_profiles)
        topics = [topic_id.lower() for topic_id in (options.topics or tuple(matched_topics(topic_scores)))]
        if options.topics:
            for topic_id in topics:
                topic_scores.setdefault(topic_id, max(topic_scores.values(), default=1.0) or 1.0)
        code_url = options.code_url or extract_code_url(text)
        unique_id = _unique_id_from_url(options.pdf_url or options.paper_url) or build_unique_id(title=title)
        return Paper(
            unique_id=unique_id,
            title=title,
            authors=authors,
            venue=venue,
            year=year,
            paper_url=options.paper_url,
            pdf_url=options.pdf_url,
            code_url=code_url,
            abstract=abstract or None,
            vlm_score=max_topic_score(topic_scores),
            topics=topics,
            topic_scores=topic_scores,
            source=source,
            sent=options.force_sent,
        )

    def _topic_profiles(self, topic_ids: tuple[str, ...] | None) -> tuple[TopicProfile, ...]:
        if not topic_ids:
            return self.config.topics
        topic_ids = tuple(topic_id.lower() for topic_id in topic_ids)
        by_id = {topic.id: topic for topic in self.config.topics}
        missing = [topic_id for topic_id in topic_ids if topic_id not in by_id]
        if missing:
            raise ValueError(f"Unknown topic(s) for import: {', '.join(missing)}")
        return tuple(by_id[topic_id] for topic_id in topic_ids)

    def _upsert_with_dedupe(self, paper: Paper) -> ImportResult:
        existing = self._find_existing(paper)
        inserted = existing is None
        if existing:
            paper.unique_id = existing.unique_id
        self.library.upsert_paper(paper)
        stored = self.library.get_paper(paper.unique_id) or paper
        return ImportResult(paper=stored, inserted=inserted, existing_id=existing.unique_id if existing else None)

    def _find_existing(self, paper: Paper) -> Paper | None:
        existing = self.library.get_paper(paper.unique_id)
        if existing:
            return existing
        if paper.pdf_url:
            existing = self.library.find_by_pdf_url(paper.pdf_url)
            if existing:
                return existing
        return self.library.find_by_title_hash(title_hash(paper.title))


def _paper_url_from_pdf_url(pdf_url: str) -> str | None:
    if "arxiv.org/pdf/" in pdf_url:
        return pdf_url.replace("/pdf/", "/abs/").removesuffix(".pdf")
    if "openreview.net/pdf" in pdf_url:
        return pdf_url.replace("/pdf", "/forum")
    if "openaccess.thecvf.com" in pdf_url:
        return pdf_url
    return None


def _unique_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    arxiv = re.search(r"arxiv\.org/(?:pdf|abs)/([^/?#]+)", url, flags=re.I)
    if arxiv:
        return "arxiv:" + re.sub(r"\.pdf$|v\d+$", "", arxiv.group(1), flags=re.I).lower()
    openreview = re.search(r"openreview\.net/(?:pdf|forum)\?id=([^&#]+)", url, flags=re.I)
    if openreview:
        return "openreview:" + openreview.group(1)
    cvf = re.search(r"openaccess\.thecvf\.com/.*/papers/([^/?#]+)", url, flags=re.I)
    if cvf:
        return "cvf:" + re.sub(r"_paper\.pdf$", "", cvf.group(1), flags=re.I).lower()
    return None


def _title_from_filename(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"(_supp|_supplementary)$", "", stem, flags=re.I)
    return clean_whitespace(stem.replace("_", " ").replace("-", " "))


def _title_from_url(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"/papers/([^/?#]+)", unquote(url), flags=re.I)
    if not match:
        return None
    stem = re.sub(r"_paper\.pdf$", "", match.group(1), flags=re.I)
    return clean_whitespace(stem.replace("_", " ").replace("-", " "))


def _title_from_pdf_text(text: str) -> str | None:
    if not text:
        return None
    first = text.split(". Abstract", 1)[0]
    lines = [clean_whitespace(line) for line in re.split(r"\n| {2,}", first) if clean_whitespace(line)]
    for line in lines[:12]:
        if 10 <= len(line) <= 220 and not line.lower().startswith(("abstract", "proceedings", "cvpr")):
            return line
    return None


def _abstract_from_pdf_text(text: str) -> str:
    match = re.search(r"\bAbstract\b[.:\s]*(?P<abstract>.*?)(?:\b1\s+Introduction\b|\bIntroduction\b)", text, flags=re.I | re.S)
    if not match:
        return ""
    return clean_whitespace(match.group("abstract"))[:4000]


def _venue_from_url(url: str | None) -> str | None:
    if not url:
        return None
    decoded = unquote(url)
    if "openaccess.thecvf.com" in decoded:
        for venue in ("CVPR", "ICCV", "ECCV"):
            if f"/{venue}" in decoded or f"_{venue}_" in decoded:
                return venue
    return None


def _venue_from_text(text: str) -> str | None:
    head = text[:3000]
    for venue in ("CVPR", "ICCV", "ECCV", "ICLR", "NeurIPS", "ICML", "AAAI", "TPAMI"):
        if re.search(rf"\b{re.escape(venue)}\b", head, flags=re.I):
            return normalize_venue(venue)
    return None
