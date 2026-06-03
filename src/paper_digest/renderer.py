from __future__ import annotations

import re
from typing import Any

from paper_digest.models import Paper
from paper_digest.text import truncate_text
from paper_digest.topics import TopicProfile, topic_names


def render_wecom_markdown(
    paper: Paper,
    summary: dict[str, Any],
    *,
    active_topics: tuple[TopicProfile, ...] = (),
    max_chars: int = 3900,
    language: str = "zh",
) -> str:
    labels = _labels(language)
    authors = summary.get("authors") or paper.authors_text or labels["unknown_authors"]
    if isinstance(authors, list):
        authors = ", ".join(str(author) for author in authors)
    code_url = summary.get("code_url") or paper.code_url or labels["no_code"]
    paper_url = summary.get("paper_url") or paper.paper_url or labels["no_paper_link"]
    title = topic_names(active_topics, paper.topics) if active_topics else paper.topics_text
    sep = labels["sep"]
    sections = [
        f"### {labels['heading']}",
        f"**{labels['topic']}**{sep}{title}",
        f"**{labels['title']}**{sep}{summary.get('title') or paper.title}",
        f"**{labels['authors']}**{sep}{authors}",
        f"**Venue/Year**{sep}{summary.get('venue_year') or paper.venue_year_text}",
        f"**{labels['paper_url']}**{sep}{_link(paper_url, language=language)}",
        f"**{labels['code_url']}**{sep}{_link(code_url, language=language)}",
        _markdown_section(labels["motivation"], summary.get("motivation"), sep),
        _markdown_section(labels["core_problem"], summary.get("core_problem"), sep),
        _markdown_section(labels["method"], summary.get("method"), sep),
        _markdown_section(labels["experiments"], summary.get("experiments"), sep),
        _markdown_section(labels["contributions"], _summary_value(summary, "contributions"), sep),
        _markdown_section(labels["limitations"], _summary_value(summary, "limitations"), sep),
    ]
    markdown = "\n\n".join(sections)
    return truncate_text(markdown, max_chars)


def render_wecom_text(
    paper: Paper,
    summary: dict[str, Any],
    *,
    active_topics: tuple[TopicProfile, ...] = (),
    language: str = "zh",
) -> str:
    labels = _labels(language)
    authors = summary.get("authors") or paper.authors_text or labels["unknown_authors"]
    if isinstance(authors, list):
        authors = ", ".join(str(author) for author in authors)
    code_url = summary.get("code_url") or paper.code_url or labels["no_code"]
    paper_url = summary.get("paper_url") or paper.paper_url or labels["no_paper_link"]
    title = topic_names(active_topics, paper.topics) if active_topics else paper.topics_text
    sep = labels["sep"]
    sections = [
        labels["heading"],
        f"{labels['topic']}{sep}{title}",
        f"{labels['title']}{sep}{summary.get('title') or paper.title}",
        f"{labels['authors']}{sep}{authors}",
        f"Venue/Year{sep}{summary.get('venue_year') or paper.venue_year_text}",
        f"{labels['paper_url']}{sep}{paper_url}",
        f"{labels['code_url']}{sep}{code_url}",
        _text_section(labels["motivation"], summary.get("motivation"), sep),
        _text_section(labels["core_problem"], summary.get("core_problem"), sep),
        _text_section(labels["method"], summary.get("method"), sep),
        _text_section(labels["experiments"], summary.get("experiments"), sep),
        _text_section(labels["contributions"], _summary_value(summary, "contributions"), sep),
        _text_section(labels["limitations"], _summary_value(summary, "limitations"), sep),
    ]
    return "\n\n".join(sections).strip()


def split_text_chunks(content: str, *, max_chars: int) -> list[str]:
    if len(content) <= max_chars:
        return [content]
    chunks: list[str] = []
    current = ""
    for paragraph in content.split("\n\n"):
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        while len(paragraph) > max_chars:
            chunks.append(paragraph[:max_chars])
            paragraph = paragraph[max_chars:]
        current = paragraph
    if current:
        chunks.append(current)
    total = len(chunks)
    if total <= 1:
        return chunks
    return [f"({idx}/{total})\n{chunk}" for idx, chunk in enumerate(chunks, start=1)]


def _link(value: object, *, language: str = "zh") -> str:
    text = str(value or "").strip()
    no_value_prefixes = ("暂无", "No ")
    if not text or text in {"暂无公开代码", "No public code yet"} or text.startswith(no_value_prefixes):
        return text or _labels(language)["unavailable"]
    if text.startswith("http://") or text.startswith("https://"):
        return f"[{text}]({text})"
    return text


def _summary_value(summary: dict[str, Any], key: str) -> object:
    if summary.get(key):
        return summary[key]
    if key == "contributions":
        return summary.get("contributions_limitations")
    return None


def _markdown_section(label: str, value: object, sep: str) -> str:
    text = _format_block(value)
    if "\n" in text:
        return f"**{label}**{sep}\n{text}"
    return f"**{label}**{sep}{text}"


def _text_section(label: str, value: object, sep: str) -> str:
    text = _format_block(value)
    if "\n" in text:
        return f"{label}{sep}\n{text}"
    return f"{label}{sep}{text}"


def _format_block(value: object) -> str:
    if isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value if str(item).strip()]
        return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("\\n", "\n")
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    marker = r"(?:\d+\.\s+|\d+[)）]\s*|\d+、\s*|[（(]\d+[）)]\s*|[-*•]\s+)"
    separator = r"(?:(?<=[：:;；。!?？])[ \t]*|[ \t]+)"
    text = re.sub(rf"(?<!^)(?<!\n){separator}(?={marker})", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _labels(language: str) -> dict[str, str]:
    if language == "en":
        return {
            "heading": "Daily Paper Digest",
            "topic": "Research Topic",
            "title": "Title",
            "authors": "Authors",
            "paper_url": "Paper Link",
            "code_url": "Code Link",
            "motivation": "Motivation",
            "core_problem": "Core Problem",
            "method": "Method",
            "experiments": "Experimental Findings",
            "contributions": "Contributions",
            "limitations": "Limitations",
            "unknown_authors": "Authors not confirmed",
            "no_paper_link": "No paper link available",
            "no_code": "No public code yet",
            "unavailable": "Unavailable",
            "sep": ": ",
        }
    return {
        "heading": "每日论文精选",
        "topic": "研究方向",
        "title": "标题",
        "authors": "作者",
        "paper_url": "论文链接",
        "code_url": "代码链接",
        "motivation": "研究动机",
        "core_problem": "核心问题",
        "method": "方法怎么实施",
        "experiments": "实验结论",
        "contributions": "贡献",
        "limitations": "局限",
        "unknown_authors": "作者未确认",
        "no_paper_link": "暂无论文链接",
        "no_code": "暂无公开代码",
        "unavailable": "暂无",
        "sep": "：",
    }
