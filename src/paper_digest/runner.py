from __future__ import annotations

from dataclasses import dataclass, replace

from paper_digest.config import Config
from paper_digest.http import HttpError
from paper_digest.library import PaperLibrary
from paper_digest.llm import LLMClient
from paper_digest.models import Paper, RunResult
from paper_digest.pdf_text import download_pdf_text
from paper_digest.progress import StageProgress
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
    def __init__(self, config: Config, *, progress: StageProgress | None = None) -> None:
        self.config = config
        self.progress = progress

    def discover(self, library: PaperLibrary, *, topic_ids: tuple[str, ...] | None = None) -> DiscoveryReport:
        report = DiscoveryReport(errors=[])
        papers: list[Paper] = []
        source_config = self._config_for_topic_ids(topic_ids)

        arxiv = ArxivSource(source_config)
        cvf = CVFSource(source_config)
        s2 = SemanticScholarSource(source_config)
        openreview = OpenReviewSource(source_config)
        tpami = TPAMISource(source_config)

        try:
            self._step("Fetching arXiv recent papers and metadata")
            arxiv_recent = arxiv.fetch_recent()
            report.arxiv_count += len(arxiv_recent)
            papers.extend(s2.enrich(arxiv_recent))
            self._info(f"arXiv recent: {len(arxiv_recent)} papers")
        except Exception as exc:
            report.add_error(f"arXiv recent fetch failed: {exc}")
            self._info(f"arXiv recent failed: {exc}")

        try:
            self._step("Searching Semantic Scholar venue candidates")
            s2_papers = s2.search_venue_candidates(source_config.venue_years)
            report.semantic_scholar_count += len(s2_papers)
            papers.extend(s2_papers)
            self._info(f"Semantic Scholar: {len(s2_papers)} papers")
        except Exception as exc:
            report.add_error(f"Semantic Scholar venue search failed: {exc}")
            self._info(f"Semantic Scholar failed: {exc}")

        try:
            self._step("Fetching CVF OpenAccess candidates")
            cvf_papers = cvf.fetch_candidates(source_config.venue_years)
            report.cvf_count += len(cvf_papers)
            papers.extend(cvf_papers)
            self._info(f"CVF OpenAccess: {len(cvf_papers)} papers")
        except Exception as exc:
            report.add_error(f"CVF OpenAccess fetch failed: {exc}")
            self._info(f"CVF OpenAccess failed: {exc}")

        try:
            self._step("Fetching OpenReview candidates")
            openreview_papers = openreview.fetch_candidates(source_config.venue_years)
            report.openreview_count += len(openreview_papers)
            papers.extend(openreview_papers)
            self._info(f"OpenReview: {len(openreview_papers)} papers")
        except Exception as exc:
            report.add_error(f"OpenReview fetch failed: {exc}")
            self._info(f"OpenReview failed: {exc}")

        try:
            self._step("Fetching TPAMI candidates")
            tpami_papers = tpami.fetch_candidates(source_config.venue_years)
            report.tpami_count += len(tpami_papers)
            papers.extend(tpami_papers)
            self._info(f"TPAMI: {len(tpami_papers)} papers")
        except Exception as exc:
            report.add_error(f"TPAMI fetch failed: {exc}")
            self._info(f"TPAMI failed: {exc}")

        if not papers:
            self._info("No candidates found from primary sources; trying yearly arXiv fallback")
            for year in source_config.venue_years:
                try:
                    yearly = arxiv.fetch_year(year)
                    report.arxiv_count += len(yearly)
                    papers.extend(yearly)
                    self._info(f"arXiv {year} fallback: {len(yearly)} papers")
                except Exception as exc:
                    report.add_error(f"arXiv {year} fallback fetch failed: {exc}")
                    self._info(f"arXiv {year} fallback failed: {exc}")

        self._step("Writing candidates to paper library")
        report.stored_count = library.upsert_many(papers)
        self._info(f"stored/updated: {report.stored_count} candidates")
        return report

    def run(
        self,
        *,
        send: bool,
        refresh_summary: bool = False,
        rotate_topics: bool = True,
        refresh_library: bool = False,
    ) -> RunResult:
        with PaperLibrary(self.config.db_path) as library:
            run_topic_ids = self.config.topic_ids_for_run(rotate=rotate_topics)
            selected_topic_ids = run_topic_ids[:1]
            self._info(f"run topic: {', '.join(selected_topic_ids)}")
            report = DiscoveryReport(errors=[])
            discovery_ran = False
            if refresh_library:
                report = self.discover(library, topic_ids=selected_topic_ids)
                discovery_ran = True

            self._step(f"Selecting next paper for topic: {', '.join(selected_topic_ids)}")
            paper, render_topic_ids = self._choose_next_paper(library, selected_topic_ids)
            if paper is None and not discovery_ran:
                self._info("no local candidate found; fetching online sources")
                report = self.discover(library, topic_ids=selected_topic_ids)
                discovery_ran = True
                self._step(f"Selecting next paper for topic: {', '.join(selected_topic_ids)}")
                paper, render_topic_ids = self._choose_next_paper(library, selected_topic_ids)
            if paper is None:
                details = "; ".join(report.errors or [])
                message = f"No unsent paper candidate found for topic: {', '.join(selected_topic_ids)}."
                if details:
                    message += f" Source errors: {details}"
                self._finish("No paper selected")
                return RunResult(paper=None, markdown=None, sent=False, message=message)
            if not discovery_ran:
                self._info("using local paper library; skipped online discovery")
            self._info(f"selected: {paper.title}")

            llm_client = LLMClient(self.config)
            summary = paper.summary_json
            needs_summary = refresh_summary or summary is None or not self._summary_language_matches(summary)
            if send and not llm_client.is_available() and needs_summary:
                self._finish("Stopped before summarization")
                return RunResult(
                    paper=paper,
                    markdown=None,
                    sent=False,
                    message=(
                        "A configured LLM is required for --send when no cached summary exists. "
                        "Set LLM_PROVIDER/LLM_MODEL/LLM_API_KEY, or use a local provider such as ollama."
                    ),
                )

            if needs_summary:
                self._step("Downloading and parsing selected PDF")
                pdf_text = self._pdf_text_for(paper, progress=self.progress is not None and self.progress.enabled)
                self._info(f"extracted PDF text chars: {len(pdf_text)}")
                code_url = paper.code_url or extract_code_url(paper.abstract, pdf_text)
                if code_url:
                    paper.code_url = code_url
                self._step(f"Calling {llm_client.provider_name} to generate summary")
                summary = llm_client.summarize(paper, pdf_text=pdf_text)
                library.update_summary(paper.unique_id, summary, code_url=paper.code_url)
                self._info("summary cached in database")
            else:
                self._step("Using cached summary")

            self._step("Rendering WeCom message")
            message_type = self.config.wecom_message_type
            content = self._render_content(paper, summary, message_type=message_type, topic_ids=render_topic_ids)

            if not send:
                self._finish("Dry run complete")
                return RunResult(
                    paper=paper,
                    markdown=content,
                    sent=False,
                    message=self._dry_run_message(paper, report=report, discovery_ran=discovery_ran),
                )

            if not self.config.wecom_webhook_url:
                self._finish("Stopped before WeCom send")
                return RunResult(
                    paper=paper,
                    markdown=content,
                    sent=False,
                    message="WECOM_WEBHOOK_URL is required for --send.",
                )

            try:
                chunks = self._message_chunks(content, message_type=message_type)
                self._step(f"Sending WeCom message ({len(chunks)} chunk{'s' if len(chunks) != 1 else ''})")
                sender = WeComSender(self.config.wecom_webhook_url, timeout=self.config.http_timeout)
                for index, chunk in enumerate(chunks, start=1):
                    sender.send(chunk, message_type=message_type)
                    self._info(f"sent chunk {index}/{len(chunks)}")
            except Exception as exc:
                library.record_send_error(paper.unique_id, str(exc))
                self._finish("WeCom send failed")
                return RunResult(paper=paper, markdown=content, sent=False, message=f"WeCom send failed: {exc}")

            library.mark_sent(paper.unique_id)
            self._finish("Send complete")
            return RunResult(paper=paper, markdown=content, sent=True, message=f"Sent {paper.unique_id}.")

    @staticmethod
    def _dry_run_message(paper: Paper, *, report: DiscoveryReport, discovery_ran: bool) -> str:
        if discovery_ran:
            return f"Dry run selected {paper.unique_id}; stored {report.stored_count} candidates."
        return f"Dry run selected {paper.unique_id}; used local paper library."

    def _pdf_text_for(self, paper: Paper, *, progress: bool = False) -> str:
        try:
            return download_pdf_text(
                paper.pdf_url,
                timeout=self.config.http_timeout,
                max_chars=self.config.max_pdf_chars,
                progress=progress,
            )
        except HttpError:
            return ""
        except Exception:
            return ""

    def _config_for_topic_ids(self, topic_ids: tuple[str, ...] | None) -> Config:
        if not topic_ids:
            return self.config
        topics = self.config.topics_for_ids(topic_ids)
        if not topics:
            return self.config
        return replace(self.config, topic_ids=topic_ids, topics=topics)

    def _choose_next_paper(
        self,
        library: PaperLibrary,
        run_topic_ids: tuple[str, ...],
    ) -> tuple[Paper | None, tuple[str, ...]]:
        for topic_id in run_topic_ids:
            paper = library.choose_next_paper(self.config.venue_years, (topic_id,))
            if paper is not None:
                return paper, (topic_id,)
        return None, run_topic_ids

    def _render_content(
        self,
        paper: Paper,
        summary: dict[str, object],
        *,
        message_type: str,
        topic_ids: tuple[str, ...],
    ) -> str:
        display_topic_ids = tuple(dict.fromkeys(topic_ids + tuple(paper.topics)))
        active_topics = self.config.topics_for_ids(display_topic_ids)
        if message_type == "markdown":
            return render_wecom_markdown(paper, summary, active_topics=active_topics, language=self.config.summary_language)
        if message_type == "text":
            return render_wecom_text(paper, summary, active_topics=active_topics, language=self.config.summary_language)
        raise ValueError(f"Unsupported WECOM_MESSAGE_TYPE: {message_type}")

    def _summary_language_matches(self, summary: dict[str, object]) -> bool:
        summary_language = str(summary.get("_language") or "zh").lower()
        return summary_language == self.config.summary_language

    def _message_chunks(self, content: str, *, message_type: str) -> list[str]:
        if message_type == "text":
            return split_text_chunks(content, max_chars=self.config.wecom_text_chunk_chars)
        return [content]

    def _step(self, message: str) -> None:
        if self.progress:
            self.progress.step(message)

    def _info(self, message: str) -> None:
        if self.progress:
            self.progress.info(message)

    def _finish(self, message: str) -> None:
        if self.progress:
            self.progress.finish(message)
