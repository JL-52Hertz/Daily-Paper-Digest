from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from paper_digest.schedule import parse_send_times
from paper_digest.topics import TopicProfile, load_active_topics


def _csv_ints(value: str | None, default: tuple[int, ...]) -> tuple[int, ...]:
    if not value:
        return default
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


def _csv_strings(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        return default
    return tuple(item.strip().lower() for item in value.split(",") if item.strip())


@dataclass(slots=True)
class Config:
    db_path: Path = Path("data/papers.db")
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-v4-pro"
    deepseek_base_url: str = "https://api.deepseek.com"
    wecom_webhook_url: str | None = None
    wecom_message_type: str = "text"
    wecom_text_chunk_chars: int = 1800
    s2_api_key: str | None = None
    topic_config_path: Path = Path("config/topics.json")
    topic_ids: tuple[str, ...] = ("vlm",)
    topics: tuple[TopicProfile, ...] = field(default_factory=tuple)
    run_time: str = "08:00"
    send_times: tuple[str, ...] = ("08:00",)
    timezone: str = "Asia/Shanghai"
    venue_years: tuple[int, ...] = (2026, 2025, 2024)
    lookback_days: int = 3
    candidate_limit: int = 50
    max_pdf_chars: int = 24000
    http_timeout: float = 30.0

    @classmethod
    def from_env(cls, *, load_topics: bool = True) -> "Config":
        topic_config_path = Path(os.getenv("PAPER_DIGEST_TOPIC_CONFIG", "config/topics.json"))
        topic_ids = _csv_strings(os.getenv("PAPER_DIGEST_TOPICS"), ("vlm",))
        run_time = os.getenv("PAPER_DIGEST_RUN_TIME", "08:00")
        send_times = parse_send_times(os.getenv("PAPER_DIGEST_SEND_TIMES") or run_time)
        topics = load_active_topics(topic_config_path, topic_ids) if load_topics else tuple()
        return cls(
            db_path=Path(os.getenv("PAPER_DIGEST_DB", "data/papers.db")),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY") or None,
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
            wecom_webhook_url=os.getenv("WECOM_WEBHOOK_URL") or None,
            wecom_message_type=os.getenv("WECOM_MESSAGE_TYPE", "text").strip().lower(),
            wecom_text_chunk_chars=int(os.getenv("WECOM_TEXT_CHUNK_CHARS", "1800")),
            s2_api_key=os.getenv("S2_API_KEY") or None,
            topic_config_path=topic_config_path,
            topic_ids=topic_ids,
            topics=topics,
            run_time=run_time,
            send_times=send_times,
            timezone=os.getenv("TZ", "Asia/Shanghai"),
            venue_years=_csv_ints(os.getenv("PAPER_DIGEST_VENUE_YEARS"), (2026, 2025, 2024)),
            lookback_days=int(os.getenv("PAPER_DIGEST_LOOKBACK_DAYS", "3")),
            candidate_limit=int(os.getenv("PAPER_DIGEST_CANDIDATE_LIMIT", "50")),
            max_pdf_chars=int(os.getenv("PAPER_DIGEST_MAX_PDF_CHARS", "24000")),
            http_timeout=float(os.getenv("PAPER_DIGEST_HTTP_TIMEOUT", "30")),
        )
