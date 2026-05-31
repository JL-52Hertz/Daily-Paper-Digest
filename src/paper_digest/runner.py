from __future__ import annotations

from dataclasses import dataclass

from paper_digest.config import Config
from paper_digest.deepseek import DeepSeekClient
from paper_digest.http import HttpError
from paper_digest.library import PaperLibrary
from paper_digest.models import Paper, RunResult
from paper_digest.pdf_text import download_pdf_text
from paper_digest.renderer import render_wecom_markdown, render_wecom_text, split_text_chunks
from paper_digest.sources.arxiv import ArxivSource
from paper_digest.sources.cvf import CVFSource
from paper_digest.sources.openreview import OpenReviewSource
from paper_digest.sources.semantic_scholar import SemanticScholarSource
from paper_digest.sources.tpami import TPAMISource
from paper_digest.text import extract_code_url
from paper_digest.wecom import WeComSender


@dataclass(slots=True)
class DiscoveryReport:
    arxiv_count: int = 0
    cvf_count: int = 0
    semantic_scholar_count: int = 0
    openreview_count: int = 0
    tpami_count: int = 0
    stored_count: int = 0
    errors: list[str] | None = None

    def add_error(self, message: str) -> None:
        if self.errors is None:
            self.errors = []
        self.errors.append(message)


class PaperDigestRunner:
    def __init__(self, config: Config) -> None:
        self.config = config

    def discover(self, library: PaperLibrary) -> DiscoveryReport:
        report = DiscoveryReport(errors=[])
        papers: list[Paper] = []

        arxiv = ArxivSource(self.config)
        cvf = CVFSource(self.config)
        s2 = SemanticScholarSource(self.config)
        openreview = OpenReviewSource(self.config)
        tpami = TPAMISource(self.config)

        try:
            arxiv_recent = arxiv.fetch_recent()
            report.arxiv_count += len(arxiv_recent)
            papers.extend(s2.enrich(arxiv_recent))
        except Exception as exc:
            report.add_error(f"arXiv recent fetch failed: {exc}")

        try:
            s2_papers = s2.search_venue_candidates(self.config.venue_years)
            report.semantic_scholar_count += len(s2_papers)
            papers.extend(s2_papers)
        except Exception as exc:
            report.add_error(f"Semantic Scholar venue search failed: {exc}")

        try:
            cvf_papers = cvf.fetch_candidates(self.config.venue_years)
            report.cvf_count += len(cvf_papers)
            papers.extend(cvf_papers)
        except Exception as exc:
            report.add_error(f"CVF OpenAccess fetch failed: {exc}")

        try:
            openreview_papers = openreview.fetch_candidates(self.config.venue_years)
            report.openreview_count += len(openreview_papers)
            papers.extend(openreview_papers)
        except Exception as exc:
            report.add_error(f"OpenReview fetch failed: {exc}")

        try:
            tpami_papers = tpami.fetch_candidates(self.config.venue_years)
            report.tpami_count += len(tpami_papers)
            papers.extend(tpami_papers)
        except Exception as exc:
            report.add_error(f"TPAMI fetch failed: {exc}")

        if not papers:
            for year in self.config.venue_years:
                try:
                    yearly = arxiv.fetch_year(year)
                    report.arxiv_count += len(yearly)
                    papers.extend(yearly)
                except Exception as exc:
                    report.add_error(f"arXiv {year} fallback fetch failed: {exc}")

        report.stored_count = library.upsert_many(papers)
        return report

    def run(self, *, send: bool, refresh_summary: bool = False) -> RunResult:
        with PaperLibrary(self.config.db_path) as library:
            report = self.discover(library)
            paper = library.choose_next_paper(self.config.venue_years, self.config.topic_ids)
            if paper is None:
                details = "; ".join(report.errors or [])
                message = f"No unsent paper candidate found for topics: {', '.join(self.config.topic_ids)}."
                if details:
                    message += f" Source errors: {details}"
                return RunResult(paper=None, markdown=None, sent=False, message=message)

            if send and not self.config.deepseek_api_key and not paper.summary_json:
                return RunResult(
                    paper=paper,
                    markdown=None,
                    sent=False,
                    message="DEEPSEEK_API_KEY is required for --send when no cached summary exists.",
                )

            summary = paper.summary_json
            if refresh_summary or summary is None:
                pdf_text = self._pdf_text_for(paper)
                code_url = paper.code_url or extract_code_url(paper.abstract, pdf_text)
                if code_url:
                    paper.code_url = code_url
                summary = DeepSeekClient(self.config).summarize(paper, pdf_text=pdf_text)
                library.update_summary(paper.unique_id, summary, code_url=paper.code_url)

            message_type = self.config.wecom_message_type
            content = self._render_content(paper, summary, message_type=message_type)

            if not send:
                return RunResult(
                    paper=paper,
                    markdown=content,
                    sent=False,
                    message=f"Dry run selected {paper.unique_id}; stored {report.stored_count} candidates.",
                )

            if not self.config.wecom_webhook_url:
                return RunResult(
                    paper=paper,
                    markdown=content,
                    sent=False,
                    message="WECOM_WEBHOOK_URL is required for --send.",
                )

            try:
                sender = WeComSender(self.config.wecom_webhook_url, timeout=self.config.http_timeout)
                for chunk in self._message_chunks(content, message_type=message_type):
                    sender.send(chunk, message_type=message_type)
            except Exception as exc:
                library.record_send_error(paper.unique_id, str(exc))
                return RunResult(paper=paper, markdown=content, sent=False, message=f"WeCom send failed: {exc}")

            library.mark_sent(paper.unique_id)
            return RunResult(paper=paper, markdown=content, sent=True, message=f"Sent {paper.unique_id}.")

    def _pdf_text_for(self, paper: Paper) -> str:
        try:
            return download_pdf_text(
                paper.pdf_url,
                timeout=self.config.http_timeout,
                max_chars=self.config.max_pdf_chars,
            )
        except HttpError:
            return ""
        except Exception:
            return ""

    def _render_content(self, paper: Paper, summary: dict[str, object], *, message_type: str) -> str:
        if message_type == "markdown":
            return render_wecom_markdown(paper, summary, active_topics=self.config.topics)
        if message_type == "text":
            return render_wecom_text(paper, summary, active_topics=self.config.topics)
        raise ValueError(f"Unsupported WECOM_MESSAGE_TYPE: {message_type}")

    def _message_chunks(self, content: str, *, message_type: str) -> list[str]:
        if message_type == "text":
            return split_text_chunks(content, max_chars=self.config.wecom_text_chunk_chars)
        return [content]
