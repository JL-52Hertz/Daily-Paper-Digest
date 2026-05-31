from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class TopicProfile:
    id: str
    name: str
    description: str = ""
    categories: tuple[str, ...] = ("cs.CV", "cs.AI", "cs.LG")
    keywords: tuple[str, ...] = field(default_factory=tuple)
    arxiv_terms: tuple[str, ...] = field(default_factory=tuple)
    semantic_scholar_query: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TopicProfile":
        topic_id = str(data["id"]).strip().lower()
        return cls(
            id=topic_id,
            name=str(data.get("name") or topic_id).strip(),
            description=str(data.get("description") or "").strip(),
            categories=tuple(str(item).strip() for item in data.get("categories", []) if str(item).strip()),
            keywords=tuple(str(item).strip() for item in data.get("keywords", []) if str(item).strip()),
            arxiv_terms=tuple(str(item).strip() for item in data.get("arxiv_terms", []) if str(item).strip()),
            semantic_scholar_query=str(data.get("semantic_scholar_query") or "").strip(),
        )

    @property
    def query_text(self) -> str:
        if self.semantic_scholar_query:
            return self.semantic_scholar_query
        return " ".join(self.keywords[:8])


BUILTIN_TOPICS = {
    "vlm": TopicProfile(
        id="vlm",
        name="VLM",
        description="Vision-language and multimodal LLM papers.",
        categories=("cs.CV", "cs.CL", "cs.AI", "cs.LG"),
        keywords=(
            "vision-language",
            "vision language",
            "visual-language",
            "visual language",
            "multimodal large language model",
            "multi-modal large language model",
            "multimodal llm",
            "multi-modal llm",
            "large multimodal model",
            "large multi-modal model",
            "vlm",
            "vllm",
            "image-text",
            "image text",
            "video-text",
            "video text",
            "visual question answering",
            "vqa",
            "document vqa",
            "visual grounding",
            "referring expression",
            "image captioning",
            "video captioning",
        ),
        arxiv_terms=(
            "vision language",
            "vision-language",
            "visual language",
            "multimodal",
            "multi-modal",
            "large multimodal model",
            "visual question answering",
            "image text",
            "video text",
            "VLM",
        ),
        semantic_scholar_query="vision language multimodal large language model visual question answering",
    ),
    "detection": TopicProfile(
        id="detection",
        name="Object Detection",
        description="Object detection and detection foundation model papers.",
        categories=("cs.CV", "cs.AI", "cs.LG"),
        keywords=(
            "object detection",
            "object detector",
            "detection transformer",
            "detr",
            "yolo",
            "open-vocabulary detection",
            "open vocabulary detection",
            "zero-shot detection",
            "few-shot detection",
            "3d object detection",
            "3d detection",
            "video object detection",
        ),
        arxiv_terms=(
            "object detection",
            "object detector",
            "detection transformer",
            "DETR",
            "YOLO",
            "open vocabulary detection",
            "3D object detection",
            "video object detection",
        ),
        semantic_scholar_query="object detection detection transformer DETR YOLO open vocabulary detection",
    ),
}


def load_topic_catalog(path: Path) -> dict[str, TopicProfile]:
    catalog = dict(BUILTIN_TOPICS)
    if not path.exists():
        return catalog
    data = json.loads(path.read_text(encoding="utf-8"))
    for item in data.get("topics", []):
        topic = TopicProfile.from_dict(item)
        catalog[topic.id] = topic
    return catalog


def load_active_topics(path: Path, topic_ids: tuple[str, ...]) -> tuple[TopicProfile, ...]:
    catalog = load_topic_catalog(path)
    topics: list[TopicProfile] = []
    missing: list[str] = []
    for topic_id in topic_ids:
        normalized = topic_id.strip().lower()
        if not normalized:
            continue
        topic = catalog.get(normalized)
        if topic is None:
            missing.append(normalized)
            continue
        topics.append(topic)
    if missing:
        available = ", ".join(sorted(catalog))
        raise ValueError(f"Unknown topic(s): {', '.join(missing)}. Available topics: {available}")
    if not topics:
        topics.append(catalog["vlm"])
    return tuple(topics)


def topic_names(topics: tuple[TopicProfile, ...], topic_ids: list[str] | None = None) -> str:
    if topic_ids:
        by_id = {topic.id: topic for topic in topics}
        names = [by_id.get(topic_id).name if topic_id in by_id else topic_id for topic_id in topic_ids]
    else:
        names = [topic.name for topic in topics]
    return "/".join(names) if names else "AI"
