from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class Paper:
    unique_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    venue: str | None = None
    year: int | None = None
    paper_url: str | None = None
    pdf_url: str | None = None
    code_url: str | None = None
    abstract: str | None = None
    vlm_score: float = 0.0
    topics: list[str] = field(default_factory=list)
    topic_scores: dict[str, float] = field(default_factory=dict)
    source: str = "unknown"
    discovered_at: str = field(default_factory=utc_now_iso)
    published_at: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    openreview_id: str | None = None
    semantic_scholar_id: str | None = None
    summary_json: dict[str, Any] | None = None
    sent: bool = False
    sent_at: str | None = None
    send_error: str | None = None

    @property
    def authors_text(self) -> str:
        return ", ".join(self.authors)

    @property
    def venue_year_text(self) -> str:
        if self.venue and self.year:
            return f"{self.venue} {self.year}"
        if self.venue:
            return self.venue
        if self.year:
            return str(self.year)
        return "venue/year 未确认"

    @property
    def relevance_score(self) -> float:
        return max(self.topic_scores.values(), default=self.vlm_score)

    @property
    def topics_text(self) -> str:
        return "/".join(self.topics) if self.topics else "AI"


@dataclass(slots=True)
class RunResult:
    paper: Paper | None
    markdown: str | None
    sent: bool
    message: str
