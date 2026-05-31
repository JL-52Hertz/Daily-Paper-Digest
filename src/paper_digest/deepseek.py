from __future__ import annotations

import json
import re
from typing import Any

from paper_digest.config import Config
from paper_digest.http import request_json
from paper_digest.models import Paper
from paper_digest.text import truncate_text
from paper_digest.topics import topic_names


SUMMARY_FIELDS = (
    "title",
    "authors",
    "venue_year",
    "paper_url",
    "code_url",
    "motivation",
    "core_problem",
    "method",
    "experiments",
    "contributions_limitations",
)


class DeepSeekClient:
    def __init__(self, config: Config) -> None:
        self.config = config

    def summarize(self, paper: Paper, *, pdf_text: str = "") -> dict[str, Any]:
        if not self.config.deepseek_api_key:
            return fallback_summary(paper)
        payload = {
            "model": self.config.deepseek_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是严谨的 AI 论文解读助手。请只输出 JSON，不要输出 Markdown。"
                        "所有解释字段必须使用中文，英文术语可保留原文。"
                    ),
                },
                {"role": "user", "content": self._prompt(paper, pdf_text)},
            ],
            "temperature": 0.2,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        response = request_json(
            f"{self.config.deepseek_base_url}/chat/completions",
            method="POST",
            headers={"Authorization": f"Bearer {self.config.deepseek_api_key}"},
            json_body=payload,
            timeout=self.config.http_timeout,
        )
        content = response["choices"][0]["message"]["content"]
        return normalize_summary(parse_json_object(content), paper)

    def _prompt(self, paper: Paper, pdf_text: str) -> str:
        body = pdf_text or paper.abstract or ""
        topics = topic_names(self.config.topics, paper.topics)
        return f"""
请阅读下面论文信息，生成适合企业微信群每日论文分享的中文结构化解读。
当前关注研究方向：{topics}

输出 JSON，必须包含这些键：
{", ".join(SUMMARY_FIELDS)}

要求：
1. title 保留论文原始标题。
2. authors 使用作者列表或字符串。
3. venue_year 使用已知 venue/year；未知就写“venue/year 未确认”。
4. code_url 找不到时必须写“暂无公开代码”。
5. motivation、core_problem、method、experiments、contributions_limitations 都用中文，具体但简洁。
6. 不要编造实验结果或代码链接；信息不足时明确说明“论文文本中未明确给出”。

论文元数据：
标题：{paper.title}
作者：{paper.authors_text}
venue/year：{paper.venue_year_text}
论文链接：{paper.paper_url or ""}
代码链接：{paper.code_url or "暂无公开代码"}
摘要：{paper.abstract or ""}

论文正文节选：
{truncate_text(body, self.config.max_pdf_chars)}
""".strip()


def parse_json_object(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def normalize_summary(summary: dict[str, Any], paper: Paper) -> dict[str, Any]:
    normalized = {field: summary.get(field) for field in SUMMARY_FIELDS}
    normalized["title"] = normalized["title"] or paper.title
    normalized["authors"] = normalized["authors"] or paper.authors_text or "作者未确认"
    normalized["venue_year"] = normalized["venue_year"] or paper.venue_year_text
    normalized["paper_url"] = normalized["paper_url"] or paper.paper_url or "暂无论文链接"
    normalized["code_url"] = normalized["code_url"] or paper.code_url or "暂无公开代码"
    for field in ("motivation", "core_problem", "method", "experiments", "contributions_limitations"):
        normalized[field] = normalized[field] or "论文文本中未明确给出。"
    return normalized


def fallback_summary(paper: Paper) -> dict[str, Any]:
    abstract = paper.abstract or "暂无摘要。"
    topics = paper.topics_text
    summary = {
        "title": paper.title,
        "authors": paper.authors_text or "作者未确认",
        "venue_year": paper.venue_year_text,
        "paper_url": paper.paper_url or "暂无论文链接",
        "code_url": paper.code_url or "暂无公开代码",
        "motivation": f"根据摘要，这篇论文关注 {topics} 相关问题。摘要：{abstract}",
        "core_problem": "需要调用 DeepSeek API 后生成更精确的问题归纳；当前为无 API Key 的预览摘要。",
        "method": "需要读取论文正文后由 DeepSeek 总结具体方法实施细节。",
        "experiments": "需要读取论文正文后由 DeepSeek 总结实验设置和结论。",
        "contributions_limitations": "需要读取论文正文后由 DeepSeek 总结贡献与局限。",
    }
    return normalize_summary(summary, paper)
