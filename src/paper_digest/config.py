from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from paper_digest.schedule import normalize_send_time, parse_send_schedule, parse_time_topic_map, rotate_topic_ids
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
    llm_provider: str = "deepseek"
    llm_api_key: str | None = None
    llm_model: str = "deepseek-v4-pro"
    llm_base_url: str = "https://api.deepseek.com"
    db_path: Path = Path("data/papers.db")
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-v4-pro"
    deepseek_base_url: str = "https://api.deepseek.com"
    wecom_webhook_url: str | None = None
    wecom_message_type: str = "text"
    wecom_text_chunk_chars: int = 1800
    summary_language: str = "zh"
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
        llm_provider = _normalize_llm_provider(os.getenv("LLM_PROVIDER", "deepseek"))
        llm_model = os.getenv("LLM_MODEL") or _provider_model(llm_provider)
        llm_base_url = (os.getenv("LLM_BASE_URL") or _provider_base_url(llm_provider)).rstrip("/")
        llm_api_key = os.getenv("LLM_API_KEY") or _provider_api_key(llm_provider)
        topic_config_path = Path(os.getenv("PAPER_DIGEST_TOPIC_CONFIG", "config/topics.json"))
        topic_ids = _csv_strings(os.getenv("PAPER_DIGEST_TOPICS"), ("vlm",))
        send_times, time_topic_ids = parse_send_schedule(
            os.getenv("PAPER_DIGEST_SEND_TIMES") or os.getenv("PAPER_DIGEST_RUN_TIME", "08:00")
        )
        run_time = normalize_send_time(os.getenv("PAPER_DIGEST_RUN_TIME") or send_times[0])
        legacy_time_topic_ids = parse_time_topic_map(os.getenv("PAPER_DIGEST_TIME_TOPICS"))
        if legacy_time_topic_ids:
            time_topic_ids = {**time_topic_ids, **legacy_time_topic_ids}
            send_times = tuple(dict.fromkeys((*send_times, *legacy_time_topic_ids)))
        all_topic_ids = _merge_topic_ids(topic_ids, *(time_topic_ids.values()))
        topics = load_active_topics(topic_config_path, all_topic_ids) if load_topics else tuple()
        return cls(
            llm_provider=llm_provider,
            llm_api_key=llm_api_key or None,
            llm_model=llm_model,
            llm_base_url=llm_base_url,
            db_path=Path(os.getenv("PAPER_DIGEST_DB", "data/papers.db")),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY") or None,
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
            wecom_webhook_url=os.getenv("WECOM_WEBHOOK_URL") or None,
            wecom_message_type=os.getenv("WECOM_MESSAGE_TYPE", "text").strip().lower(),
            wecom_text_chunk_chars=int(os.getenv("WECOM_TEXT_CHUNK_CHARS", "1800")),
            summary_language=_normalize_summary_language(
                os.getenv("PAPER_DIGEST_SUMMARY_LANGUAGE") or os.getenv("PAPER_DIGEST_OUTPUT_LANGUAGE", "zh")
            ),
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


def _normalize_summary_language(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "zh": "zh",
        "zh-cn": "zh",
        "cn": "zh",
        "chinese": "zh",
        "中文": "zh",
        "en": "en",
        "en-us": "en",
        "en-gb": "en",
        "english": "en",
        "英文": "en",
    }
    if normalized not in aliases:
        raise ValueError("Invalid PAPER_DIGEST_SUMMARY_LANGUAGE. Expected zh or en.")
    return aliases[normalized]


def _normalize_llm_provider(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(".", "_")
    aliases = {
        "claude": "anthropic",
        "anthropic_claude": "anthropic",
        "aliyun": "dashscope",
        "alibaba": "dashscope",
        "bailian": "dashscope",
        "qwen": "dashscope",
        "ark": "volcengine",
        "doubao": "volcengine",
        "bytedance": "volcengine",
        "byte_dance": "volcengine",
        "baidu": "qianfan",
        "wenxin": "qianfan",
        "ernie": "qianfan",
        "openai_compatible": "openai_compatible",
        "compatible": "openai_compatible",
        "llamacpp": "llama_cpp",
        "llama_cpp": "llama_cpp",
        "llama_cpp_server": "llama_cpp",
    }
    return aliases.get(normalized, normalized or "deepseek")


def _provider_api_key(provider: str) -> str | None:
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY")
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_API_KEY")
    if provider == "deepseek":
        return os.getenv("DEEPSEEK_API_KEY")
    if provider == "dashscope":
        return os.getenv("DASHSCOPE_API_KEY")
    if provider == "volcengine":
        return os.getenv("ARK_API_KEY") or os.getenv("VOLCENGINE_API_KEY")
    if provider == "qianfan":
        return os.getenv("QIANFAN_API_KEY") or os.getenv("BAIDU_API_KEY")
    return os.getenv("OPENAI_COMPATIBLE_API_KEY") or os.getenv("LLM_API_KEY")


def _provider_model(provider: str) -> str:
    if provider == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
    if provider == "dashscope":
        return os.getenv("DASHSCOPE_MODEL", "qwen-plus")
    if provider == "volcengine":
        return os.getenv("ARK_MODEL", "doubao-seed-1-6-251015")
    if provider == "qianfan":
        return os.getenv("QIANFAN_MODEL", "ernie-4.0-turbo-128k")
    if provider == "ollama":
        return os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    if provider == "llama_cpp":
        return os.getenv("LLAMA_CPP_MODEL", "local-model")
    if provider == "openai_compatible":
        return os.getenv("OPENAI_COMPATIBLE_MODEL", "gpt-4o-mini")
    return os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")


def _provider_base_url(provider: str) -> str:
    if provider == "openai":
        return os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    if provider == "dashscope":
        return os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    if provider == "volcengine":
        return os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    if provider == "qianfan":
        return os.getenv("QIANFAN_BASE_URL", "https://qianfan.baidubce.com/v2")
    if provider == "ollama":
        return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    if provider == "llama_cpp":
        return os.getenv("LLAMA_CPP_BASE_URL", "http://localhost:8080/v1")
    if provider == "openai_compatible":
        return os.getenv("OPENAI_COMPATIBLE_BASE_URL", "http://localhost:8000/v1")
    return os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
