from __future__ import annotations

import hashlib
import re
from html import unescape
from typing import Iterable

from paper_digest.constants import CODE_URL_PATTERNS, TARGET_VENUES, VENUE_ALIASES, VLM_KEYWORDS
from paper_digest.topics import BUILTIN_TOPICS, TopicProfile


def clean_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", unescape(value)).strip()


def normalize_title(title: str) -> str:
    value = title.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return clean_whitespace(value)


def title_hash(title: str) -> str:
    digest = hashlib.sha256(normalize_title(title).encode("utf-8")).hexdigest()
    return f"title:{digest[:24]}"


def build_unique_id(
    *,
    title: str,
    doi: str | None = None,
    arxiv_id: str | None = None,
    openreview_id: str | None = None,
    semantic_scholar_id: str | None = None,
) -> str:
    if doi:
        return f"doi:{doi.strip().lower()}"
    if arxiv_id:
        return f"arxiv:{arxiv_id.strip().lower()}"
    if openreview_id:
        return f"openreview:{openreview_id.strip()}"
    if semantic_scholar_id:
        return f"s2:{semantic_scholar_id.strip()}"
    return title_hash(title)


def score_vlm_relevance(title: str | None, abstract: str | None) -> float:
    return score_topic_relevance(title, abstract, (BUILTIN_TOPICS["vlm"],))["vlm"]


def score_keywords(title: str | None, abstract: str | None, keywords: Iterable[str]) -> float:
    text = f"{title or ''}\n{abstract or ''}".lower()
    if not text.strip():
        return 0.0
    score = 0.0
    for keyword in keywords:
        count = text.count(keyword.lower())
        if count:
            score += 1.0 + min(count - 1, 3) * 0.25
    return round(score, 3)


def score_topic_relevance(title: str | None, abstract: str | None, topics: Iterable[TopicProfile]) -> dict[str, float]:
    scores: dict[str, float] = {}
    text = f"{title or ''}\n{abstract or ''}".lower()
    for topic in topics:
        score = score_keywords(title, abstract, topic.keywords)
        if topic.id == "vlm":
            if "vision" in text and "language" in text:
                score += 1.5
            if "multimodal" in text or "multi-modal" in text:
                score += 1.0
            if "large language model" in text or "llm" in text:
                score += 0.75
        elif topic.id == "detection":
            if "object" in text and "detect" in text:
                score += 1.25
            if "open vocabulary" in text or "open-vocabulary" in text:
                score += 0.75
        scores[topic.id] = round(score, 3)
    return scores


def matched_topics(topic_scores: dict[str, float]) -> list[str]:
    return [topic_id for topic_id, score in topic_scores.items() if score > 0]


def max_topic_score(topic_scores: dict[str, float]) -> float:
    return max(topic_scores.values(), default=0.0)


def normalize_venue(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = clean_whitespace(value)
    lowered = cleaned.lower()
    for alias, canonical in VENUE_ALIASES.items():
        if alias in lowered:
            return canonical
    upper = cleaned.upper()
    for venue in TARGET_VENUES:
        if venue in upper:
            return "NeurIPS" if venue == "NEURIPS" else venue
    return cleaned


def is_target_venue(venue: str | None) -> bool:
    normalized = normalize_venue(venue)
    if not normalized:
        return False
    upper = normalized.upper()
    return any(target in upper for target in TARGET_VENUES)


def extract_year(*values: str | None) -> int | None:
    for value in values:
        if not value:
            continue
        match = re.search(r"\b(20[0-9]{2})\b", value)
        if match:
            return int(match.group(1))
    return None


def extract_code_url(*texts: str | None) -> str | None:
    for text in texts:
        if not text:
            continue
        for raw_url in re.findall(r"https?://[^\s\]\)\},;<>\"']+", text):
            url = raw_url.rstrip(".。)")
            lowered = url.lower()
            if any(pattern in lowered for pattern in CODE_URL_PATTERNS):
                return url
    return None


def truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 20].rstrip() + "\n...[truncated]"
