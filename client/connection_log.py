"""Local-only connection log for product clients (device storage, user-exportable).

Events stay on the device under the product data directory. This module never
uploads log content to the node, status page, or any remote collector.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

LOG_FILENAME = "connection_log.jsonl"
DEFAULT_MAX_EVENTS = 500

# Kinds used by the product UI / Settings surface.
KIND_CONNECT = "connect"
KIND_DISCONNECT = "disconnect"
KIND_SESSION = "session"
KIND_ERROR = "error"
KIND_INFO = "info"
KIND_LEAK_TEST = "leak_test"
KIND_SETTINGS = "settings"


@dataclass(frozen=True)
class ConnectionLogEvent:
    """One local connection-log entry."""

    ts: float
    kind: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": float(self.ts),
            "kind": str(self.kind),
            "message": str(self.message),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConnectionLogEvent":
        return cls(
            ts=float(data.get("ts") or 0.0),
            kind=str(data.get("kind") or KIND_INFO),
            message=str(data.get("message") or ""),
        )

    def format_line(self) -> str:
        """Human-readable single line for export / Settings list."""
        try:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.ts))
        except (OverflowError, OSError, ValueError):
            stamp = str(self.ts)
        return f"[{stamp}] {self.kind}: {self.message}"


def log_dir() -> Path:
    """Product local data directory (same family as Windows settings_store)."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(
            Path.home() / "AppData" / "Local"
        )
        return Path(base) / "RestorePrivacy"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "restore-privacy"
    return Path.home() / ".local" / "share" / "restore-privacy"


def default_log_path() -> Path:
    return log_dir() / LOG_FILENAME


def append_event(
    kind: str,
    message: str,
    *,
    path: Optional[Path] = None,
    ts: Optional[float] = None,
    max_events: int = DEFAULT_MAX_EVENTS,
) -> ConnectionLogEvent:
    """Append one event to the local JSONL log; trim oldest if over max_events."""
    event = ConnectionLogEvent(
        ts=float(ts if ts is not None else time.time()),
        kind=str(kind or KIND_INFO),
        message=str(message or "").strip() or "(empty)",
    )
    p = path or default_log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
    if max_events > 0:
        _trim_log(p, max_events=max_events)
    return event


def read_events(
    *,
    path: Optional[Path] = None,
    limit: Optional[int] = None,
) -> list[ConnectionLogEvent]:
    """Read events from the local log (oldest first). ``limit`` keeps the newest N."""
    p = path or default_log_path()
    if not p.is_file():
        return []
    events: list[ConnectionLogEvent] = []
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if isinstance(data, dict):
                events.append(ConnectionLogEvent.from_dict(data))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    if limit is not None and limit >= 0 and len(events) > limit:
        events = events[-limit:]
    return events


def format_export(
    events: Optional[Iterable[ConnectionLogEvent]] = None,
    *,
    path: Optional[Path] = None,
) -> str:
    """Plain-text export body (user can save/share). Never leaves the device here."""
    if events is None:
        events = read_events(path=path)
    lines = [ev.format_line() for ev in events]
    header = (
        "# Restore Privacy connection log (local only)\n"
        "# Not uploaded by the client. User-exported file.\n"
    )
    return header + "\n".join(lines) + ("\n" if lines else "")


def export_to_file(
    dest: Path,
    *,
    source: Optional[Path] = None,
    events: Optional[Iterable[ConnectionLogEvent]] = None,
) -> Path:
    """Write export text to ``dest``; returns path written."""
    body = format_export(events, path=source)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body, encoding="utf-8")
    return dest


def clear_events(*, path: Optional[Path] = None) -> None:
    """Erase the local log file (user-initiated clear)."""
    p = path or default_log_path()
    try:
        if p.is_file():
            p.unlink()
    except OSError:
        pass


def log_module_has_no_network_upload() -> bool:
    """Structural honesty: this module must not import network clients.

    Used by unit tests. Returns True when the source has no upload/HTTP client
    imports. Does not scan the whole process — only this file's source.
    """
    import ast

    src = Path(__file__).read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    banned_roots = {
        "urllib",
        "requests",
        "httpx",
        "socket",
        "http",
        "aiohttp",
        "ftplib",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in banned_roots:
                    return False
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".", 1)[0]
                if root in banned_roots:
                    return False
    # Docstring / export header must state local-only / not uploaded
    low = src.lower()
    return (
        "never" in low
        and "upload" in low
        and ("not uploaded" in low or "local only" in low or "local-only" in low)
    )


def _trim_log(path: Path, *, max_events: int) -> None:
    events = read_events(path=path)
    if len(events) <= max_events:
        return
    keep = events[-max_events:]
    lines = [json.dumps(ev.to_dict(), ensure_ascii=False) for ev in keep]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
