from __future__ import annotations

from typing import Any

from paper_digest.http import request_json


class WeComSender:
    def __init__(self, webhook_url: str, *, timeout: float = 30.0) -> None:
        self.webhook_url = webhook_url
        self.timeout = timeout

    def send(self, content: str, *, message_type: str = "text") -> None:
        if message_type == "markdown":
            payload: dict[str, Any] = {
                "msgtype": "markdown",
                "markdown": {"content": content},
            }
        elif message_type == "text":
            payload = {
                "msgtype": "text",
                "text": {"content": content},
            }
        else:
            raise ValueError(f"Unsupported WECOM_MESSAGE_TYPE: {message_type}")
        response = request_json(
            self.webhook_url,
            method="POST",
            json_body=payload,
            timeout=self.timeout,
        )
        if response.get("errcode") != 0:
            raise RuntimeError(f"WeCom send failed: {response}")

    def send_markdown(self, markdown: str) -> None:
        self.send(markdown, message_type="markdown")
