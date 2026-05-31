from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from paper_digest.config import Config
from paper_digest.http import request_json
from paper_digest.topics import TopicProfile, load_topic_catalog


def topic_id_from_name(name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "topic"


def generate_topic(name: str, *, config: Config, topic_id: str | None = None, use_llm: bool = True) -> TopicProfile:
    resolved_id = topic_id_from_name(topic_id or name)
    if use_llm and config.deepseek_api_key:
        try:
            return _generate_with_deepseek(name, topic_id=resolved_id, config=config)
        except Exception:
            pass
    return _generate_heuristic(name, topic_id=resolved_id)


def add_topic_to_file(path: Path, topic: TopicProfile, *, force: bool = False) -> None:
    data = {"topics": []}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    topics = data.setdefault("topics", [])
    existing_index = next((idx for idx, item in enumerate(topics) if item.get("id") == topic.id), None)
    item = topic_to_dict(topic)
    if existing_index is not None:
        if not force:
            raise ValueError(f"Topic already exists: {topic.id}. Use --force to overwrite it.")
        topics[existing_index] = item
    else:
        topics.append(item)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def topic_to_dict(topic: TopicProfile) -> dict[str, Any]:
    return {
        "id": topic.id,
        "name": topic.name,
        "description": topic.description,
        "categories": list(topic.categories),
        "keywords": list(topic.keywords),
        "arxiv_terms": list(topic.arxiv_terms),
        "semantic_scholar_query": topic.semantic_scholar_query,
    }


def ensure_topic_can_be_added(path: Path, topic_id: str, *, force: bool) -> None:
    catalog = load_topic_catalog(path)
    if topic_id in catalog and not force:
        raise ValueError(f"Topic already exists: {topic_id}. Use --force to overwrite it.")


def _generate_with_deepseek(name: str, *, topic_id: str, config: Config) -> TopicProfile:
    payload = {
        "model": config.deepseek_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You generate JSON configuration for an academic paper topic search system. "
                    "Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": f"""
Create a topic config for: {name}

Return a JSON object with exactly these keys:
id, name, description, categories, keywords, arxiv_terms, semantic_scholar_query

Rules:
- id must be "{topic_id}".
- name should be concise title case.
- description should be one sentence.
- categories should use arXiv CS categories such as cs.CV, cs.LG, cs.AI, cs.CL, cs.RO.
- keywords should contain 18-30 English search phrases, including synonyms and common abbreviations.
- arxiv_terms should contain 8-14 high precision query phrases.
- semantic_scholar_query should be a compact keyword query string.
- Do not include markdown.
""".strip(),
            },
        ],
        "temperature": 0.2,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    response = request_json(
        f"{config.deepseek_base_url}/chat/completions",
        method="POST",
        headers={"Authorization": f"Bearer {config.deepseek_api_key}"},
        json_body=payload,
        timeout=config.http_timeout,
    )
    content = response["choices"][0]["message"]["content"]
    data = json.loads(content)
    data["id"] = topic_id
    return TopicProfile.from_dict(data)


def _generate_heuristic(name: str, *, topic_id: str) -> TopicProfile:
    phrase = _clean_phrase(name)
    lowered = phrase.lower()
    categories = _guess_categories(lowered)
    keywords = _generic_keywords(lowered)
    if "efficient" in lowered and "train" in lowered:
        keywords = _dedupe(
            [
                lowered,
                "efficient training",
                "training efficiency",
                "data-efficient training",
                "data efficient training",
                "sample efficient learning",
                "sample-efficient learning",
                "training data selection",
                "data selection",
                "coreset selection",
                "curriculum learning",
                "active learning",
                "efficient fine-tuning",
                "parameter-efficient fine-tuning",
                "peft",
                "lora",
                "low-rank adaptation",
                "knowledge distillation",
                "model distillation",
                "pruning",
                "sparse training",
                "training acceleration",
                "compute-efficient training",
                "low-cost training",
            ]
        )
    arxiv_terms = keywords[:12]
    return TopicProfile(
        id=topic_id,
        name=_title_case(phrase),
        description=f"Papers related to {phrase}, including methods, systems, benchmarks, and applications.",
        categories=tuple(categories),
        keywords=tuple(keywords),
        arxiv_terms=tuple(arxiv_terms),
        semantic_scholar_query=" ".join(keywords[:10]),
    )


def _generic_keywords(lowered: str) -> list[str]:
    words = lowered.split()
    variants = [lowered]
    if len(words) > 1:
        variants.append("-".join(words))
    variants.extend(
        [
            f"{lowered} method",
            f"{lowered} model",
            f"{lowered} learning",
            f"{lowered} benchmark",
            f"{lowered} dataset",
            f"{lowered} optimization",
            f"{lowered} neural network",
            f"{lowered} deep learning",
            f"{lowered} foundation model",
            f"{lowered} large model",
        ]
    )
    return _dedupe(variants)


def _guess_categories(lowered: str) -> list[str]:
    categories = ["cs.LG", "cs.AI"]
    if any(term in lowered for term in ("vision", "image", "video", "detection", "segmentation", "visual")):
        categories.insert(0, "cs.CV")
    if any(term in lowered for term in ("language", "text", "nlp", "llm", "translation")):
        categories.append("cs.CL")
    if any(term in lowered for term in ("robot", "robotics", "planning", "control")):
        categories.append("cs.RO")
    return _dedupe(categories)


def _clean_phrase(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _title_case(value: str) -> str:
    preserve = {"llm": "LLM", "vlm": "VLM", "nlp": "NLP", "ai": "AI"}
    words = []
    for word in value.split():
        words.append(preserve.get(word.lower(), word.capitalize()))
    return " ".join(words)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _clean_phrase(value)
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result
