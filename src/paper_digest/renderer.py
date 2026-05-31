from __future__ import annotations

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
) -> str:
    authors = summary.get("authors") or paper.authors_text or "作者未确认"
    if isinstance(authors, list):
        authors = ", ".join(str(author) for author in authors)
    code_url = summary.get("code_url") or paper.code_url or "暂无公开代码"
    paper_url = summary.get("paper_url") or paper.paper_url or "暂无论文链接"
    title = topic_names(active_topics, paper.topics) if active_topics else paper.topics_text
    markdown = f"""
### 每日论文精选

**研究方向**：{title}

**标题**：{summary.get("title") or paper.title}

**作者**：{authors}

**Venue/Year**：{summary.get("venue_year") or paper.venue_year_text}

**论文链接**：{_link(paper_url)}

**代码链接**：{_link(code_url)}

**研究动机**：{summary.get("motivation")}

**核心问题**：{summary.get("core_problem")}

**方法怎么实施**：{summary.get("method")}

**实验结论**：{summary.get("experiments")}

**贡献与局限**：{summary.get("contributions_limitations")}
""".strip()
    return truncate_text(markdown, max_chars)


def render_wecom_text(
    paper: Paper,
    summary: dict[str, Any],
    *,
    active_topics: tuple[TopicProfile, ...] = (),
) -> str:
    authors = summary.get("authors") or paper.authors_text or "作者未确认"
    if isinstance(authors, list):
        authors = ", ".join(str(author) for author in authors)
    code_url = summary.get("code_url") or paper.code_url or "暂无公开代码"
    paper_url = summary.get("paper_url") or paper.paper_url or "暂无论文链接"
    title = topic_names(active_topics, paper.topics) if active_topics else paper.topics_text
    return f"""
每日论文精选

研究方向：{title}

标题：{summary.get("title") or paper.title}

作者：{authors}

Venue/Year：{summary.get("venue_year") or paper.venue_year_text}

论文链接：{paper_url}

代码链接：{code_url}

研究动机：{summary.get("motivation")}

核心问题：{summary.get("core_problem")}

方法怎么实施：{summary.get("method")}

实验结论：{summary.get("experiments")}

贡献与局限：{summary.get("contributions_limitations")}
""".strip()


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


def _link(value: object) -> str:
    text = str(value or "").strip()
    if not text or text == "暂无公开代码" or text.startswith("暂无"):
        return text or "暂无"
    if text.startswith("http://") or text.startswith("https://"):
        return f"[{text}]({text})"
    return text
