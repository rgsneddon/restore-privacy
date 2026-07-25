"""Local-only connection log for product clients (device storage, user-exportable).

Events stay on the device under the product data directory. This module never
uploads log content to the node, VPN APP Shop, or any remote collector.

Support handoff: the user exports a plain-text file (Settings → Export log) and
emails that file to support themselves. Diagnostics in the export are for that
manual handoff only — not auto-telemetry.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

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

# Keys commonly useful for support (safe, no secrets).
_DIAG_PREFERRED_KEYS = (
    "product",
    "client_version",
    "platform",
    "os_name",
    "python",
    "outcome",
    "error",
    "error_code",
    "residual_host",
    "residual_port",
    "entry_country",
    "multihop",
    "session_vpn_ip",
    "residual_capture",
)


@dataclass(frozen=True)
class ConnectionLogEvent:
    """One local connection-log entry (optional support diagnostics in *detail*)."""

    ts: float
    kind: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ts": float(self.ts),
            "kind": str(self.kind),
            "message": str(self.message),
        }
        if self.detail:
            # Only JSON-serializable scalars / short strings
            clean: dict[str, Any] = {}
            for k, v in self.detail.items():
                key = str(k).strip()
                if not key:
                    continue
                if isinstance(v, (bool, int, float)):
                    clean[key] = v
                elif v is None:
                    continue
                else:
                    s = str(v).strip()
                    if s:
                        clean[key] = s[:500]
            if clean:
                out["detail"] = clean
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConnectionLogEvent":
        raw_detail = data.get("detail")
        detail: dict[str, Any] = {}
        if isinstance(raw_detail, dict):
            detail = {str(k): v for k, v in raw_detail.items()}
        return cls(
            ts=float(data.get("ts") or 0.0),
            kind=str(data.get("kind") or KIND_INFO),
            message=str(data.get("message") or ""),
            detail=detail,
        )

    def format_line(self) -> str:
        """Human-readable single line for export / Settings list."""
        try:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.ts))
        except (OverflowError, OSError, ValueError):
            stamp = str(self.ts)
        base = f"[{stamp}] {self.kind}: {self.message}"
        if not self.detail:
            return base
        # Prefer compact key=value tails for support scanning
        parts: list[str] = []
        for key in _DIAG_PREFERRED_KEYS:
            if key in self.detail and key not in ("product", "client_version", "platform", "os_name", "python"):
                parts.append(f"{key}={self.detail[key]}")
        # Any remaining custom keys (skip base diag already in export header)
        skip = set(_DIAG_PREFERRED_KEYS[:5])
        for key, val in self.detail.items():
            if key in skip:
                continue
            if key in _DIAG_PREFERRED_KEYS and any(p.startswith(f"{key}=") for p in parts):
                continue
            if key not in _DIAG_PREFERRED_KEYS:
                parts.append(f"{key}={val}")
        if not parts:
            return base
        return base + " | " + " ".join(parts)


def product_client_version() -> str:
    """Shipped client VERSION string (no network)."""
    try:
        p = Path(__file__).resolve().parent / "VERSION"
        if p.is_file():
            v = p.read_text(encoding="utf-8").strip().splitlines()[0].strip()
            if v:
                return v
    except OSError:
        pass
    return "unknown"


def build_support_diagnostics(
    *,
    extra: Mapping[str, Any] | None = None,
    include_runtime: bool = True,
) -> dict[str, Any]:
    """Small diagnostic snapshot for support export / event detail.

    Pure local facts only — never opens network sockets or calls remote APIs.
    """
    snap: dict[str, Any] = {
        "product": "Restore Privacy",
        "client_version": product_client_version(),
    }
    if include_runtime:
        snap["platform"] = str(sys.platform)
        snap["os_name"] = str(os.name)
        snap["python"] = (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )
    if extra:
        for k, v in extra.items():
            key = str(k).strip()
            if not key or v is None:
                continue
            if isinstance(v, (bool, int, float)):
                snap[key] = v
            else:
                s = str(v).strip()
                if s:
                    snap[key] = s[:500]
    return snap


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
    detail: Mapping[str, Any] | None = None,
    include_diagnostics: bool = True,
) -> ConnectionLogEvent:
    """Append one event to the local JSONL log; trim oldest if over max_events.

    When *include_diagnostics* is true (default), merges a support diagnostic
    snapshot (version / platform) with any caller *detail* (endpoint, error, …).
    """
    merged: dict[str, Any] = {}
    if include_diagnostics:
        merged.update(build_support_diagnostics())
    if detail:
        for k, v in detail.items():
            key = str(k).strip()
            if not key or v is None:
                continue
            if isinstance(v, (bool, int, float)):
                merged[key] = v
            else:
                s = str(v).strip()
                if s:
                    merged[key] = s[:500]
    event = ConnectionLogEvent(
        ts=float(ts if ts is not None else time.time()),
        kind=str(kind or KIND_INFO),
        message=str(message or "").strip() or "(empty)",
        detail=merged,
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
    diagnostics: Mapping[str, Any] | None = None,
) -> str:
    """Plain-text export body (user can save/email). Never leaves the device here."""
    if events is None:
        events = read_events(path=path)
    event_list = list(events)
    snap = build_support_diagnostics(extra=diagnostics)
    header_lines = [
        "# Restore Privacy connection log (local only)",
        "# Not uploaded by the client. User-exported file for support handoff.",
        "# Support: email this file to support yourself (no automatic upload).",
        f"# product={snap.get('product')} client_version={snap.get('client_version')}",
        f"# platform={snap.get('platform')} os_name={snap.get('os_name')} "
        f"python={snap.get('python')}",
        "# --- events ---",
    ]
    lines = [ev.format_line() for ev in event_list]
    body = "\n".join(header_lines) + "\n"
    if lines:
        body += "\n".join(lines) + "\n"
    return body


def export_to_file(
    dest: Path,
    *,
    source: Optional[Path] = None,
    events: Optional[Iterable[ConnectionLogEvent]] = None,
    diagnostics: Mapping[str, Any] | None = None,
) -> Path:
    """Write export text to ``dest``; returns path written."""
    body = format_export(events, path=source, diagnostics=diagnostics)
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
