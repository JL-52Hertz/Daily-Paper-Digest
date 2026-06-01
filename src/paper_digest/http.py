from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any

from paper_digest.progress import Progress


class HttpError(RuntimeError):
    pass


def request_bytes(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> bytes:
    body = None
    request_headers = {"User-Agent": "wechat-paper-digest/0.1"}
    if headers:
        request_headers.update(headers)
    if json_body is not None:
        body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except (TimeoutError, socket.timeout) as exc:
        raise HttpError(f"Request timed out after {timeout:g}s for {url}") from exc
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HttpError(f"HTTP {exc.code} for {url}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise HttpError(f"Request failed for {url}: {exc.reason}") from exc


def request_bytes_with_progress(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    label: str = "Downloading",
    progress: bool = True,
) -> bytes:
    request_headers = {"User-Agent": "wechat-paper-digest/0.1"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, headers=request_headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            total = int(response.headers.get("Content-Length") or 0) or None
            reporter = Progress(label=label, total=total, enabled=progress, unit="B")
            reporter.start()
            chunks: list[bytes] = []
            downloaded = 0
            while True:
                chunk = response.read(1024 * 128)
                if not chunk:
                    break
                chunks.append(chunk)
                downloaded += len(chunk)
                reporter.update(downloaded)
            reporter.finish()
            return b"".join(chunks)
    except (TimeoutError, socket.timeout) as exc:
        raise HttpError(f"Request timed out after {timeout:g}s for {url}") from exc
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HttpError(f"HTTP {exc.code} for {url}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise HttpError(f"Request failed for {url}: {exc.reason}") from exc


def request_text(url: str, *, timeout: float = 30.0, headers: dict[str, str] | None = None) -> str:
    return request_bytes(url, timeout=timeout, headers=headers).decode("utf-8", errors="replace")


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    raw = request_bytes(url, method=method, headers=headers, json_body=json_body, timeout=timeout)
    return json.loads(raw.decode("utf-8"))
