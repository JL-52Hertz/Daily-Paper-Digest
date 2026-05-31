from __future__ import annotations

import base64
import re
import shutil
import shlex
from pathlib import Path
from xml.sax.saxutils import escape


TIME_RE = re.compile(r"^(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)$")


def parse_send_times(value: str | None, default: tuple[str, ...] = ("08:00",)) -> tuple[str, ...]:
    if not value:
        return default
    times: list[str] = []
    for raw in value.split(","):
        item = raw.strip()
        if not item:
            continue
        times.append(normalize_send_time(item))
    return tuple(dict.fromkeys(times)) or default


def normalize_send_time(value: str) -> str:
    match = TIME_RE.match(value.strip())
    if not match:
        raise ValueError(f"Invalid send time: {value!r}. Expected HH:MM, for example 08:00 or 20:30.")
    return f"{int(match.group('hour')):02d}:{int(match.group('minute')):02d}"


def cron_lines(
    send_times: tuple[str, ...],
    *,
    workdir: Path,
    timezone: str,
    uv_path: str | None = None,
    log_path: str = "logs/paper-digest.log",
) -> list[str]:
    executable = uv_path or shutil.which("uv") or "uv"
    workdir_text = shlex.quote(str(workdir))
    executable_text = shlex.quote(executable)
    timezone_text = shlex.quote(timezone)
    log_text = shlex.quote(log_path)
    lines: list[str] = []
    for send_time in send_times:
        hour, minute = send_time.split(":", 1)
        command = (
            f"cd {workdir_text} && TZ={timezone_text} {executable_text} run paper-digest run --send "
            f">> {log_text} 2>&1"
        )
        lines.append(f"{int(minute)} {int(hour)} * * * {command}")
    return lines


def launchd_plist(
    send_times: tuple[str, ...],
    *,
    workdir: Path,
    timezone: str,
    uv_path: str | None = None,
    label: str = "com.paper-digest.daily",
    stdout_path: str = "logs/paper-digest.log",
    stderr_path: str = "logs/paper-digest.err.log",
) -> str:
    executable = uv_path or shutil.which("uv") or "uv"
    intervals = "\n".join(_launchd_interval(send_time) for send_time in send_times)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{escape(label)}</string>
  <key>WorkingDirectory</key>
  <string>{escape(str(workdir))}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>TZ</key>
    <string>{escape(timezone)}</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>{escape(executable)}</string>
    <string>run</string>
    <string>paper-digest</string>
    <string>run</string>
    <string>--send</string>
  </array>
  <key>StartCalendarInterval</key>
  <array>
{intervals}
  </array>
  <key>StandardOutPath</key>
  <string>{escape(str(workdir / stdout_path))}</string>
  <key>StandardErrorPath</key>
  <string>{escape(str(workdir / stderr_path))}</string>
</dict>
</plist>
"""


def windows_task_commands(
    send_times: tuple[str, ...],
    *,
    workdir: Path,
    timezone: str,
    uv_path: str | None = None,
    task_prefix: str = "PaperDigest",
    log_path: str = "logs\\paper-digest.log",
) -> list[str]:
    executable = uv_path or "uv"
    commands: list[str] = []
    for send_time in send_times:
        task_name = f"{task_prefix}-{send_time.replace(':', '')}"
        script = (
            f"Set-Location -LiteralPath {_ps_quote(str(workdir))}\n"
            f"$env:TZ = {_ps_quote(timezone)}\n"
            f"& {_ps_quote(executable)} run paper-digest run --send *>> {_ps_quote(log_path)}"
        )
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        commands.append(
            f"# {task_name}: {executable} run paper-digest run --send\n"
            "$action = New-ScheduledTaskAction -Execute 'powershell.exe' "
            f"-Argument {_ps_quote('-NoProfile -ExecutionPolicy Bypass -EncodedCommand ' + encoded)}\n"
            f"$trigger = New-ScheduledTaskTrigger -Daily -At {_ps_quote(send_time)}\n"
            f"Register-ScheduledTask -TaskName {_ps_quote(task_name)} -Action $action -Trigger $trigger -Force"
        )
    return commands


def _launchd_interval(send_time: str) -> str:
    hour, minute = send_time.split(":", 1)
    return f"""    <dict>
      <key>Hour</key>
      <integer>{int(hour)}</integer>
      <key>Minute</key>
      <integer>{int(minute)}</integer>
    </dict>"""


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
