from __future__ import annotations

from io import BytesIO

from paper_digest.http import request_bytes, request_bytes_with_progress
from paper_digest.progress import Progress
from paper_digest.text import clean_whitespace, truncate_text


def download_pdf_text(pdf_url: str | None, *, timeout: float, max_chars: int, progress: bool = False) -> str:
    if not pdf_url:
        return ""
    if progress:
        raw = request_bytes_with_progress(
            pdf_url,
            timeout=timeout,
            headers={"Accept": "application/pdf"},
            label="Downloading PDF",
            progress=True,
        )
    else:
        raw = request_bytes(pdf_url, timeout=timeout, headers={"Accept": "application/pdf"})
    return extract_pdf_text(raw, max_chars=max_chars, progress=progress)


def extract_pdf_text(raw_pdf: bytes, *, max_chars: int, progress: bool = False) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return ""
    try:
        reader = PdfReader(BytesIO(raw_pdf))
        chunks: list[str] = []
        pages = reader.pages[:12]
        reporter = Progress(label="Parsing PDF", total=len(pages), enabled=progress, unit=" page")
        reporter.start()
        for index, page in enumerate(pages, start=1):
            text = page.extract_text() or ""
            if text:
                chunks.append(text)
            reporter.update(index)
            if sum(len(chunk) for chunk in chunks) >= max_chars:
                break
        reporter.finish()
        return truncate_text(clean_whitespace("\n".join(chunks)), max_chars)
    except Exception:
        return ""
