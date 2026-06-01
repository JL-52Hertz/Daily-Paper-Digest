from __future__ import annotations

import sys
from dataclasses import dataclass
from time import monotonic


@dataclass(slots=True)
class Progress:
    label: str
    total: int | None = None
    enabled: bool = True
    unit: str = ""
    _last_render: float = 0.0
    _current: int = 0
    _done: bool = False

    def start(self) -> None:
        if not self.enabled:
            return
        self._render(force=True)

    def update(self, current: int | None = None, *, advance: int = 0) -> None:
        if current is not None:
            self._current = current
        else:
            self._current += advance
        if not self.enabled:
            return
        now = monotonic()
        if now - self._last_render >= 0.1:
            self._render()

    def finish(self, suffix: str = "done") -> None:
        if self.total is not None:
            self._current = self.total
        self._done = True
        if self.enabled:
            self._render(force=True, suffix=suffix)
            sys.stderr.write("\n")
            sys.stderr.flush()

    def _render(self, *, force: bool = False, suffix: str = "") -> None:
        if not force and not self.enabled:
            return
        self._last_render = monotonic()
        if self.total:
            ratio = min(max(self._current / self.total, 0.0), 1.0)
            width = 24
            filled = int(width * ratio)
            bar = "#" * filled + "-" * (width - filled)
            percent = int(ratio * 100)
            current = _format_amount(self._current, self.unit)
            total = _format_amount(self.total, self.unit)
            text = f"\r{self.label}: [{bar}] {percent:3d}% {current}/{total}"
        else:
            current = _format_amount(self._current, self.unit)
            text = f"\r{self.label}: {current}"
        if suffix:
            text += f" {suffix}"
        sys.stderr.write(text)
        sys.stderr.flush()


@dataclass(slots=True)
class StageProgress:
    total: int
    enabled: bool = True
    _current: int = 0

    def step(self, message: str) -> None:
        if not self.enabled:
            return
        self._current = min(self._current + 1, self.total)
        width = 24
        filled = int(width * self._current / self.total) if self.total else width
        bar = "#" * filled + "-" * (width - filled)
        sys.stderr.write(f"[{bar}] {self._current}/{self.total} {message}\n")
        sys.stderr.flush()

    def info(self, message: str) -> None:
        if not self.enabled:
            return
        sys.stderr.write(f"  - {message}\n")
        sys.stderr.flush()

    def finish(self, message: str = "Done") -> None:
        if not self.enabled:
            return
        if self._current < self.total:
            self._current = self.total
        width = 24
        bar = "#" * width
        sys.stderr.write(f"[{bar}] {self.total}/{self.total} {message}\n")
        sys.stderr.flush()


def _format_amount(value: int, unit: str) -> str:
    if unit == "B":
        return _format_bytes(value)
    if unit:
        return f"{value}{unit}"
    return str(value)


def _format_bytes(value: int) -> str:
    amount = float(value)
    for suffix in ("B", "KB", "MB", "GB"):
        if amount < 1024 or suffix == "GB":
            if suffix == "B":
                return f"{int(amount)}{suffix}"
            return f"{amount:.1f}{suffix}"
        amount /= 1024
