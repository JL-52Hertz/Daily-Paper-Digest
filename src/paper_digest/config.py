from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from paper_digest.schedule import normalize_send_time, parse_send_times, parse_time_topic_map, rotate_topic_ids
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
    time_topic_ids: dict[str, tuple[str, ...]] = field(default_factory=dict)
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
        send_times = parse_send_times(os.getenv("PAPER_DIGEST_SEND_TIMES") or os.getenv("PAPER_DIGEST_RUN_TIME", "08:00"))
        run_time = normalize_send_time(os.getenv("PAPER_DIGEST_RUN_TIME") or send_times[0])
        time_topic_ids = parse_time_topic_map(os.getenv("PAPER_DIGEST_TIME_TOPICS"))
        all_topic_ids = _merge_topic_ids(topic_ids, *(time_topic_ids.values()))
        topics = load_active_topics(topic_config_path, all_topic_ids) if load_topics else tuple()
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
            topic_ids=all_topic_ids,
            topics=topics,
            run_time=run_time,
            send_times=send_times,
            time_topic_ids=time_topic_ids,
            timezone=os.getenv("TZ", "Asia/Shanghai"),
            venue_years=_csv_ints(os.getenv("PAPER_DIGEST_VENUE_YEARS"), (2026, 2025, 2024)),
            lookback_days=int(os.getenv("PAPER_DIGEST_LOOKBACK_DAYS", "3")),
            candidate_limit=int(os.getenv("PAPER_DIGEST_CANDIDATE_LIMIT", "50")),
            max_pdf_chars=int(os.getenv("PAPER_DIGEST_MAX_PDF_CHARS", "24000")),
            http_timeout=float(os.getenv("PAPER_DIGEST_HTTP_TIMEOUT", "30")),
        )

    def topic_ids_for_run(self, *, run_time: str | None = None, on_date: date | None = None) -> tuple[str, ...]:
        normalized_run_time = normalize_send_time(run_time or self.run_time)
        candidates = self.time_topic_ids.get(normalized_run_time, self.topic_ids)
        return rotate_topic_ids(candidates, on_date or self.today())

    def topics_for_ids(self, topic_ids: tuple[str, ...]) -> tuple[TopicProfile, ...]:
        by_id = {topic.id: topic for topic in self.topics}
        return tuple(by_id[topic_id] for topic_id in topic_ids if topic_id in by_id)

    def today(self) -> date:
        try:
            tzinfo = ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            return date.today()
        return datetime.now(tzinfo).date()


def _merge_topic_ids(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for topic_id in group:
            normalized = topic_id.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                merged.append(normalized)
    return tuple(merged) or ("vlm",)
