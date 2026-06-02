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
    "contributions",
    "limitations",
)

LEGACY_COMBINED_FIELD = "contributions_limitations"


class LLMClient:
    def __init__(self, config: Config) -> None:
        self.config = config

    @property
    def provider_name(self) -> str:
        names = {
            "deepseek": "DeepSeek",
            "openai": "OpenAI",
            "anthropic": "Claude/Anthropic",
            "dashscope": "Alibaba DashScope",
            "volcengine": "Volcengine Ark",
            "qianfan": "Baidu Qianfan",
            "ollama": "Ollama",
            "llama_cpp": "llama.cpp",
            "openai_compatible": "OpenAI-compatible",
        }
        return names.get(self.config.llm_provider, self.config.llm_provider)

    def is_available(self) -> bool:
        if self.config.llm_provider in {"ollama", "llama_cpp"}:
            return bool(self._model and self._base_url)
        if self.config.llm_provider == "openai_compatible":
            return bool(self._model and self._base_url)
        return bool(self._api_key and self._model and self._base_url)

    def summarize(self, paper: Paper, *, pdf_text: str = "") -> dict[str, Any]:
        if not self.is_available():
            return fallback_summary(paper, provider_name=self.provider_name, language=self.config.summary_language)
        content = self.complete_json(
            system=system_prompt(self.config.summary_language),
            prompt=self._prompt(paper, pdf_text),
        )
        return normalize_summary(parse_json_object(content), paper, language=self.config.summary_language)

    def complete_json(self, *, system: str, prompt: str) -> str:
        provider = self.config.llm_provider
        if provider in {
            "deepseek",
            "openai",
            "dashscope",
            "volcengine",
            "qianfan",
            "openai_compatible",
            "llama_cpp",
        }:
            return self._complete_openai_compatible(system=system, prompt=prompt)
        if provider == "anthropic":
            return self._complete_anthropic(system=system, prompt=prompt)
        if provider == "ollama":
            return self._complete_ollama(system=system, prompt=prompt)
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

    @property
    def _api_key(self) -> str | None:
        if self.config.llm_provider == "deepseek":
            return self.config.llm_api_key or self.config.deepseek_api_key
        return self.config.llm_api_key

    @property
    def _model(self) -> str:
        if self.config.llm_provider == "deepseek":
            return self.config.llm_model or self.config.deepseek_model
        return self.config.llm_model

    @property
    def _base_url(self) -> str:
        if self.config.llm_provider == "deepseek":
            return (self.config.llm_base_url or self.config.deepseek_base_url).rstrip("/")
        return self.config.llm_base_url.rstrip("/")

    def _complete_openai_compatible(self, *, system: str, prompt: str) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "stream": False,
        }
        if self.config.llm_provider in {"deepseek", "openai", "dashscope", "volcengine", "openai_compatible"}:
            payload["response_format"] = {"type": "json_object"}
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        response = request_json(
            _join_url(self._base_url, "chat/completions"),
            method="POST",
            headers=headers,
            json_body=payload,
            timeout=self.config.llm_timeout,
        )
        return response["choices"][0]["message"]["content"]

    def _complete_anthropic(self, *, system: str, prompt: str) -> str:
        payload = {
            "model": self._model,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1800,
            "temperature": 0.2,
        }
        response = request_json(
            _join_url(self._base_url, "v1/messages"),
            method="POST",
            headers={
                "x-api-key": self._api_key or "",
                "anthropic-version": "2023-06-01",
            },
            json_body=payload,
            timeout=self.config.llm_timeout,
        )
        return _anthropic_text(response)

    def _complete_ollama(self, *, system: str, prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        }
        response = request_json(
            _join_url(self._base_url, "api/chat"),
            method="POST",
            json_body=payload,
            timeout=self.config.llm_timeout,
        )
        return response.get("message", {}).get("content") or response.get("response") or ""

    def _prompt(self, paper: Paper, pdf_text: str) -> str:
        body = pdf_text or paper.abstract or ""
        topics = topic_names(self.config.topics, paper.topics)
        if self.config.summary_language == "en":
            return f"""
Please read the paper information below and write a structured English digest suitable for WeCom paper sharing.
Current research topics: {topics}

Output JSON only. The JSON object must contain these keys:
{", ".join(SUMMARY_FIELDS)}

Requirements:
1. Keep title as the original paper title.
2. authors can be a list or a string.
3. venue_year should use the known venue/year; if unknown, write "venue/year not confirmed".
4. code_url must be "No public code yet" when no public code link is found.
5. motivation, core_problem, method, experiments, contributions, and limitations must be in English, specific, and concise.
6. Keep contributions and limitations as separate fields.
7. If the paper does not explicitly discuss limitations, infer plausible limitations from assumptions, data, experiments, scope, or deployment constraints, and start limitations with "Model analysis (paper does not explicitly state limitations):".
8. Do not invent experimental results or code links. If the paper text does not clearly specify something, say so explicitly.
9. When a field has multiple points, use newline-separated numbered items such as "1. ...\n2. ..." instead of one long paragraph.
10. Keep the information density of motivation, core_problem, method, and experiments high; do not shorten them just to make the output look cleaner.

Paper metadata:
Title: {paper.title}
Authors: {paper.authors_text}
Venue/year: {_venue_year_text(paper, language="en")}
Paper link: {paper.paper_url or ""}
Code link: {paper.code_url or "No public code yet"}
Abstract: {paper.abstract or ""}

Paper text excerpt:
{truncate_text(body, self.config.max_pdf_chars)}
""".strip()
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
5. motivation、core_problem、method、experiments、contributions、limitations 都用中文，具体但简洁。
6. contributions 和 limitations 必须分开写。
7. 如果论文没有明确讨论局限，请根据方法假设、数据与实验设置、适用范围、部署约束等自行分析合理局限，并在 limitations 开头写“以下为模型分析，论文未明确说明：”。
8. 不要编造实验结果或代码链接；信息不足时明确说明“论文文本中未明确给出”。
9. 当某个字段需要分点时，使用换行编号，例如“1. ...\n2. ...”，不要挤在同一段里。
10. 保持 motivation、core_problem、method、experiments 的信息密度，不要为了版式更整齐而压缩细节。

论文元数据：
标题：{paper.title}
作者：{paper.authors_text}
venue/year：{_venue_year_text(paper, language="zh")}
论文链接：{paper.paper_url or ""}
代码链接：{paper.code_url or "暂无公开代码"}
摘要：{paper.abstract or ""}

论文正文节选：
{truncate_text(body, self.config.max_pdf_chars)}
""".strip()


def system_prompt(language: str) -> str:
    if language == "en":
        return (
            "You are a rigorous AI paper reading assistant. Output JSON only, not Markdown. "
            "All explanatory fields must be written in English."
        )
    return (
        "你是严谨的 AI 论文解读助手。请只输出 JSON，不要输出 Markdown。"
        "所有解释字段必须使用中文，英文术语可保留原文。"
    )


def parse_json_object(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def normalize_summary(summary: dict[str, Any], paper: Paper, *, language: str = "zh") -> dict[str, Any]:
    messages = _language_messages(language)
    normalized = {field: summary.get(field) for field in SUMMARY_FIELDS}
    legacy_contributions_limitations = summary.get(LEGACY_COMBINED_FIELD)
    normalized["title"] = normalized["title"] or paper.title
    normalized["authors"] = normalized["authors"] or paper.authors_text or messages["unknown_authors"]
    normalized["venue_year"] = normalized["venue_year"] or _venue_year_text(paper, language=language)
    normalized["paper_url"] = normalized["paper_url"] or paper.paper_url or messages["no_paper_link"]
    normalized["code_url"] = normalized["code_url"] or paper.code_url or messages["no_code"]
    for field in ("motivation", "core_problem", "method", "experiments"):
        normalized[field] = normalized[field] or messages["not_specified"]
    normalized["contributions"] = (
        normalized["contributions"] or legacy_contributions_limitations or messages["not_specified"]
    )
    normalized["limitations"] = normalized["limitations"] or messages["limitations_model_analysis"]
    normalized["_language"] = language
    return normalized


def fallback_summary(paper: Paper, *, provider_name: str = "LLM", language: str = "zh") -> dict[str, Any]:
    if language == "en":
        abstract = paper.abstract or "No abstract available."
        topics = paper.topics_text
        summary = {
            "title": paper.title,
            "authors": paper.authors_text or "Authors not confirmed",
            "venue_year": _venue_year_text(paper, language="en"),
            "paper_url": paper.paper_url or "No paper link available",
            "code_url": paper.code_url or "No public code yet",
            "motivation": f"Based on the abstract, this paper focuses on {topics}. Abstract: {abstract}",
            "core_problem": (
                f"Configure an available {provider_name} model to generate a more precise problem summary. "
                "This is a no-LLM preview summary."
            ),
            "method": f"Read the full paper with {provider_name} to summarize the implementation details.",
            "experiments": f"Read the full paper with {provider_name} to summarize the experimental setup and findings.",
            "contributions": f"Read the full paper with {provider_name} to summarize the contributions.",
            "limitations": (
                "Model analysis (paper does not explicitly state limitations): "
                f"Read the full paper with {provider_name} before drawing reliable limitation conclusions."
            ),
        }
        return normalize_summary(summary, paper, language=language)

    abstract = paper.abstract or "暂无摘要。"
    topics = paper.topics_text
    summary = {
        "title": paper.title,
        "authors": paper.authors_text or "作者未确认",
        "venue_year": paper.venue_year_text,
        "paper_url": paper.paper_url or "暂无论文链接",
        "code_url": paper.code_url or "暂无公开代码",
        "motivation": f"根据摘要，这篇论文关注 {topics} 相关问题。摘要：{abstract}",
        "core_problem": f"需要配置可用的 {provider_name} 模型后生成更精确的问题归纳；当前为无模型调用的预览摘要。",
        "method": f"需要读取论文正文后由 {provider_name} 总结具体方法实施细节。",
        "experiments": f"需要读取论文正文后由 {provider_name} 总结实验设置和结论。",
        "contributions": f"需要读取论文正文后由 {provider_name} 总结贡献。",
        "limitations": f"以下为模型分析，论文未明确说明：需要读取论文正文后由 {provider_name} 判断可靠局限。",
    }
    return normalize_summary(summary, paper, language=language)


def _language_messages(language: str) -> dict[str, str]:
    if language == "en":
        return {
            "unknown_authors": "Authors not confirmed",
            "no_paper_link": "No paper link available",
            "no_code": "No public code yet",
            "not_specified": "The paper text does not clearly specify this.",
            "limitations_model_analysis": (
                "Model analysis (paper does not explicitly state limitations): "
                "The available paper text does not provide enough detail to identify reliable limitations."
            ),
        }
    return {
        "unknown_authors": "作者未确认",
        "no_paper_link": "暂无论文链接",
        "no_code": "暂无公开代码",
        "not_specified": "论文文本中未明确给出。",
        "limitations_model_analysis": "以下为模型分析，论文未明确说明：当前论文文本不足以判断可靠局限。",
    }


def _venue_year_text(paper: Paper, *, language: str) -> str:
    if paper.venue and paper.year:
        return f"{paper.venue} {paper.year}"
    if paper.venue:
        return paper.venue
    if paper.year:
        return str(paper.year)
    if language == "en":
        return "venue/year not confirmed"
    return "venue/year 未确认"


def _join_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    cleaned_path = path.lstrip("/")
    if base.endswith("/v1") and cleaned_path.startswith("v1/"):
        cleaned_path = cleaned_path[3:]
    return f"{base}/{cleaned_path}"


def _anthropic_text(response: dict[str, Any]) -> str:
    content = response.get("content") or []
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    return "\n".join(part for part in parts if part)
