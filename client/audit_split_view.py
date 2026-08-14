"""In-client AUDIT.md split view — device-only visit logs + pane refresh policy.

When the Restore Privacy Tunnel client opens ``https://restoreprivacy.online/AUDIT.md``,
it must **not** dump user browsing stats onto the public document. Instead the
client shows two labelled halves:

* **Left — Your browsing stats** (dynamic): dedicated ping + this device's
  connection/visit log. Updates without a full-page reload.
* **Right — Project and files** (manual): public AUDIT.md + project file index.
  Changes only when the user refreshes that pane.

Visit events are appended to the **on-device** connection log only. This module
never uploads log content.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse

# Distinct pane identities (tests + UI must use these exact labels).
LEFT_PANE_ID = "user_browsing_stats"
RIGHT_PANE_ID = "project_files"
LEFT_PANE_LABEL = "Your browsing stats"
RIGHT_PANE_LABEL = "Project and files"

AUDIT_STATUS_PATH = "/AUDIT.md"
DEFAULT_AUDIT_URL = "https://restoreprivacy.online/AUDIT.md"

DEVICE_ONLY_RETENTION_PREFIX = "your data is only retained by your own device. "
DEVICE_ONLY_RETENTION_TYPEWRITER = "privacy, restored."
DEVICE_ONLY_RETENTION_SENTENCE = (
    DEVICE_ONLY_RETENTION_PREFIX + DEVICE_ONLY_RETENTION_TYPEWRITER
)

# Local connection-log kind for an in-client AUDIT visit (device only).
KIND_AUDIT_VISIT = "audit_visit"
AUDIT_VISIT_MESSAGE = "AUDIT.md visit (device-only log)"

WEEKLY_WIPE_MAX_AGE_SEC = 7 * 24 * 3600

_STATE_ORDER = {"Green": 0, "Amber": 1, "Red": 2}


def is_audit_url(url: str) -> bool:
    """True when *url* is the public AUDIT.md document (any origin path)."""
    raw = (url or "").strip()
    if not raw:
        return False
    try:
        parsed = urlparse(raw)
        path = (parsed.path or raw).rstrip("/")
    except ValueError:
        path = raw.rstrip("/")
    return path.lower().endswith("/audit.md") or path.lower() == "audit.md"


def pane_may_auto_update(pane_id: str) -> bool:
    """Left pane is dynamic; right pane is manual-refresh only."""
    return str(pane_id or "").strip() == LEFT_PANE_ID


def pane_label(pane_id: str) -> str:
    pid = str(pane_id or "").strip()
    if pid == LEFT_PANE_ID:
        return LEFT_PANE_LABEL
    if pid == RIGHT_PANE_ID:
        return RIGHT_PANE_LABEL
    return pid or "(unknown pane)"


@dataclass
class AuditSplitState:
    """In-memory two-pane snapshot (not uploaded)."""

    left_sample: dict[str, Any] = field(default_factory=dict)
    right_snapshot: dict[str, Any] = field(default_factory=dict)
    left_generation: int = 0
    right_generation: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_sample": dict(self.left_sample),
            "right_snapshot": dict(self.right_snapshot),
            "left_generation": int(self.left_generation),
            "right_generation": int(self.right_generation),
            "left_label": LEFT_PANE_LABEL,
            "right_label": RIGHT_PANE_LABEL,
        }


def apply_pane_refresh(
    state: AuditSplitState | None,
    pane_id: str,
    payload: Mapping[str, Any] | None,
    *,
    explicit: bool = False,
) -> AuditSplitState:
    """Apply a new sample to one pane.

    Left always accepts a new sample. Right accepts a sample **only** when
    *explicit* is True (manual refresh). Opening the view should pass
    ``explicit=True`` once per pane to seed both sides.
    """
    cur = state if isinstance(state, AuditSplitState) else AuditSplitState()
    pid = str(pane_id or "").strip()
    sample = dict(payload or {})
    if pid == RIGHT_PANE_ID and not explicit:
        return cur
    if pid == LEFT_PANE_ID:
        return replace(
            cur,
            left_sample=sample,
            left_generation=int(cur.left_generation) + 1,
        )
    if pid == RIGHT_PANE_ID:
        return replace(
            cur,
            right_snapshot=sample,
            right_generation=int(cur.right_generation) + 1,
        )
    return cur


def catalog_overall_for_installed(
    packages: Sequence[Mapping[str, Any]] | None,
    installed_platforms: Iterable[str] | None,
) -> str:
    """Worst RAG among packages the user actually has installed.

    Uninstalled platforms are ignored so a single-OS device does not paint
    catalog overall Red for other catalog installers they never installed.
    With no installed list, returns Green (do not invent Red).
    """
    installed = {
        str(p or "").strip().lower()
        for p in (installed_platforms or ())
        if str(p or "").strip()
    }
    rows = list(packages or [])
    if not installed:
        return "Green"
    considered = [
        r
        for r in rows
        if str(r.get("platform") or "").strip().lower() in installed
    ]
    if not considered:
        return "Green"
    worst = "Green"
    for row in considered:
        st = str(row.get("state") or "Red")
        if _STATE_ORDER.get(st, 2) > _STATE_ORDER.get(worst, 0):
            worst = st
    return worst


def evaluate_weekly_wipe_prerequisite(
    *,
    last_wipe_at: float | int | None = None,
    now: float | int | None = None,
    max_age_sec: float = WEEKLY_WIPE_MAX_AGE_SEC,
) -> dict[str, Any]:
    """Fail-closed: residual node leak wipe must have run within *max_age_sec*.

    Missing or stale last-wipe is **not** a pass. Weekly erasure of residual
    leak that might be left on the node is an audit prerequisite.
    """
    import time

    t_now = float(now if now is not None else time.time())
    if last_wipe_at is None:
        return {
            "ok": False,
            "prerequisite": "weekly_residual_leak_wipe",
            "reason": "no weekly residual leak wipe recorded",
            "last_wipe_at": None,
            "max_age_sec": float(max_age_sec),
        }
    try:
        last = float(last_wipe_at)
    except (TypeError, ValueError):
        return {
            "ok": False,
            "prerequisite": "weekly_residual_leak_wipe",
            "reason": "weekly residual leak wipe timestamp unreadable",
            "last_wipe_at": last_wipe_at,
            "max_age_sec": float(max_age_sec),
        }
    age = t_now - last
    if age < 0:
        age = 0.0
    if age > float(max_age_sec):
        return {
            "ok": False,
            "prerequisite": "weekly_residual_leak_wipe",
            "reason": (
                f"weekly residual leak wipe is stale ({int(age)}s old; "
                f"max {int(max_age_sec)}s)"
            ),
            "last_wipe_at": last,
            "age_sec": age,
            "max_age_sec": float(max_age_sec),
        }
    return {
        "ok": True,
        "prerequisite": "weekly_residual_leak_wipe",
        "reason": "weekly residual leak wipe current",
        "last_wipe_at": last,
        "age_sec": age,
        "max_age_sec": float(max_age_sec),
    }


def last_wipe_at_from_state(state: Mapping[str, Any] | None) -> float | None:
    """Extract a unix timestamp from fleet-wipe / weekly-wipe state."""
    if not isinstance(state, Mapping):
        return None
    for key in ("last_wipe_at", "last_completed_at", "wiped_at", "completed_at"):
        raw = state.get(key)
        if raw is None or raw == "":
            continue
        if isinstance(raw, (int, float)):
            return float(raw)
        text = str(raw).strip()
        if not text:
            continue
        try:
            return float(text)
        except ValueError:
            pass
        # ISO-8601 Z
        try:
            from datetime import datetime, timezone

            iso = text.replace("Z", "+00:00")
            return datetime.fromisoformat(iso).timestamp()
        except ValueError:
            continue
    return None


def build_user_browsing_stats(
    events: Sequence[Mapping[str, Any] | Any] | None,
    ping: Mapping[str, Any] | None,
    *,
    now: float | None = None,
    platform: str = "",
) -> dict[str, Any]:
    """Left-pane payload from **local** events + dedicated ping (no upload)."""
    import time

    rows: list[dict[str, Any]] = []
    for ev in events or ():
        if isinstance(ev, Mapping):
            rows.append(dict(ev))
        else:
            rows.append(
                {
                    "ts": getattr(ev, "ts", 0),
                    "kind": getattr(ev, "kind", ""),
                    "message": getattr(ev, "message", ""),
                }
            )
    ping = dict(ping or {})
    last_connect = ""
    last_visit = ""
    visit_count = 0
    for ev in rows:
        kind = str(ev.get("kind") or "")
        msg = str(ev.get("message") or "")
        if kind == "connect":
            last_connect = msg
        if kind == KIND_AUDIT_VISIT:
            visit_count += 1
            last_visit = msg
    return {
        "pane": LEFT_PANE_ID,
        "label": LEFT_PANE_LABEL,
        "dynamic": True,
        "platform": str(platform or ""),
        "ping_ok": bool(ping.get("ok")),
        "ping_ms": ping.get("rtt_ms") if ping.get("rtt_ms") is not None else ping.get("rttMs"),
        "ping_host": str(ping.get("host") or ""),
        "ping_error": str(ping.get("error") or ""),
        "event_count": len(rows),
        "audit_visit_count": visit_count,
        "last_connect": last_connect,
        "last_visit": last_visit,
        "recent": [
            {
                "kind": str(e.get("kind") or ""),
                "message": str(e.get("message") or "")[:200],
            }
            for e in rows[-8:]
        ],
        "retention": DEVICE_ONLY_RETENTION_SENTENCE,
        "retention_prefix": DEVICE_ONLY_RETENTION_PREFIX,
        "retention_typewriter": DEVICE_ONLY_RETENTION_TYPEWRITER,
        "sampled_at": float(now if now is not None else time.time()),
        "device_only": True,
    }


def build_project_files_snapshot(
    *,
    audit_text: str = "",
    file_names: Sequence[str] | None = None,
    catalog_overall: str = "",
    catalog_version: str = "",
) -> dict[str, Any]:
    """Right-pane payload: project AUDIT + file names (no user browsing stats)."""
    names = [str(n).strip() for n in (file_names or ()) if str(n).strip()]
    body = str(audit_text or "")
    return {
        "pane": RIGHT_PANE_ID,
        "label": RIGHT_PANE_LABEL,
        "dynamic": False,
        "manual_refresh_only": True,
        "catalog_version": str(catalog_version or ""),
        "catalog_overall": str(catalog_overall or ""),
        "audit_excerpt": body[:4000],
        "audit_chars": len(body),
        "files": names,
        "retention": DEVICE_ONLY_RETENTION_SENTENCE,
    }


def default_project_file_names() -> list[str]:
    """Main project documents shown on the right pane."""
    return [
        "AUDIT.md",
        "README.md",
        "PRIVACY_POLICY.md",
        "LICENSE",
        "CREDITS.md",
        "client/VERSION",
    ]


def visit_log_detail(*, platform: str = "", ping_ms: Any = None) -> dict[str, Any]:
    """Safe local-only detail for an AUDIT visit append."""
    out: dict[str, Any] = {
        "surface": "AUDIT.md",
        "device_only": True,
        "uploaded": False,
    }
    if platform:
        out["platform"] = str(platform)
    if ping_ms is not None:
        try:
            out["ping_ms"] = float(ping_ms)
        except (TypeError, ValueError):
            pass
    return out


def append_audit_visit_to_device_log(
    *,
    path: Any = None,
    platform: str = "",
    ping_ms: Any = None,
    ts: float | None = None,
) -> Any:
    """Append this AUDIT visit to the **on-device** connection log (never upload).

    Imperative: a user opening AUDIT.md in the RPT client must leave a local
    visit record on their device.
    """
    from client.connection_log import append_event

    return append_event(
        KIND_AUDIT_VISIT,
        AUDIT_VISIT_MESSAGE,
        path=path,
        ts=ts,
        detail=visit_log_detail(platform=platform, ping_ms=ping_ms),
    )


def render_split_markup(state: AuditSplitState) -> str:
    """Structural HTML used by the in-client view (and source-excerpt tests)."""
    left = state.left_sample or {}
    right = state.right_snapshot or {}
    ping = left.get("ping_ms")
    ping_txt = f"{ping} ms" if ping is not None else "n/a"
    files = right.get("files") or []
    file_lis = "".join(f"<li>{_esc(str(n))}</li>" for n in files)
    recent = left.get("recent") or []
    rec_lis = "".join(
        f"<li>{_esc(str(r.get('kind','')))}: {_esc(str(r.get('message','')))}</li>"
        for r in recent
        if isinstance(r, Mapping)
    )
    prefix = _esc(DEVICE_ONLY_RETENTION_PREFIX)
    typed = _esc(DEVICE_ONLY_RETENTION_TYPEWRITER)
    return f"""<section id="rpt-audit-split" data-audit-split="1">
  <aside id="rpt-audit-left" data-pane="{LEFT_PANE_ID}" data-dynamic="1"
         aria-label="{LEFT_PANE_LABEL}">
    <h2 class="rpt-audit-pane-label">{LEFT_PANE_LABEL}</h2>
    <p class="rpt-audit-ping">dedicated ping: {_esc(ping_txt)}</p>
    <ul class="rpt-audit-recent">{rec_lis}</ul>
    <p class="rpt-audit-retention">{prefix}<span class="suite-typewriter suite-typewriter-welcome neon-type"
       data-typewriter="1" data-typewriter-role="welcome"
       data-typewriter-text="{typed}">{typed}</span></p>
  </aside>
  <main id="rpt-audit-right" data-pane="{RIGHT_PANE_ID}" data-dynamic="0"
        data-manual-refresh="1" aria-label="{RIGHT_PANE_LABEL}">
    <h2 class="rpt-audit-pane-label">{RIGHT_PANE_LABEL}</h2>
    <p class="rpt-audit-catalog">catalog { _esc(str(right.get('catalog_version') or '')) }
       overall {_esc(str(right.get('catalog_overall') or ''))}</p>
    <ul class="rpt-audit-files">{file_lis}</ul>
    <button type="button" id="rpt-audit-right-refresh">Refresh project files</button>
    <pre class="rpt-audit-md">{_esc(str(right.get('audit_excerpt') or '')[:1200])}</pre>
  </main>
</section>
"""


def show_audit_split_window(
    parent: Any,
    *,
    connection_log_path: Any = None,
    platform: str = "",
    audit_text: str = "",
    ping: Mapping[str, Any] | None = None,
) -> AuditSplitState:
    """Open the in-client two-pane AUDIT view and **append the visit to device log**.

    Tk window when *parent* is a Tk widget; otherwise still appends the visit
    and returns the seeded pane state (headless / tests).
    """
    ev = append_audit_visit_to_device_log(
        path=connection_log_path,
        platform=platform,
        ping_ms=(ping or {}).get("rtt_ms"),
    )
    try:
        from client.connection_log import read_events

        events = read_events(path=connection_log_path)
    except Exception:
        events = [ev]
    left = build_user_browsing_stats(events, ping, platform=platform)
    right = build_project_files_snapshot(
        audit_text=audit_text,
        file_names=default_project_file_names(),
        catalog_overall=catalog_overall_for_installed(
            [{"platform": platform, "state": "Green"}],
            [platform] if platform else [],
        ),
    )
    state = apply_pane_refresh(None, LEFT_PANE_ID, left, explicit=True)
    state = apply_pane_refresh(state, RIGHT_PANE_ID, right, explicit=True)
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        return state
    if parent is None:
        return state
    try:
        win = tk.Toplevel(parent)
        win.title("Most recent audit")
        win.geometry("960x560")
        pane = ttk.Panedwindow(win, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)
        left_fr = ttk.Frame(pane, padding=12)
        right_fr = ttk.Frame(pane, padding=12)
        pane.add(left_fr, weight=1)
        pane.add(right_fr, weight=1)
        ttk.Label(left_fr, text=LEFT_PANE_LABEL, font=("Segoe UI", 12, "bold")).pack(
            anchor="w"
        )
        ttk.Label(
            left_fr,
            text=f"dedicated ping: {left.get('ping_ms') if left.get('ping_ms') is not None else 'n/a'}",
        ).pack(anchor="w", pady=(8, 0))
        ttk.Label(
            left_fr,
            text=f"visits on this device: {left.get('audit_visit_count') or 0}",
        ).pack(anchor="w")
        ttk.Label(
            left_fr,
            text=DEVICE_ONLY_RETENTION_PREFIX,
            wraplength=400,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(16, 0))
        ttk.Label(
            left_fr,
            text=DEVICE_ONLY_RETENTION_TYPEWRITER,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(right_fr, text=RIGHT_PANE_LABEL, font=("Segoe UI", 12, "bold")).pack(
            anchor="w"
        )
        for name in default_project_file_names():
            ttk.Label(right_fr, text=name).pack(anchor="w")

        def _manual_right() -> None:
            nonlocal state
            nxt = build_project_files_snapshot(
                audit_text=audit_text,
                file_names=default_project_file_names(),
            )
            state = apply_pane_refresh(state, RIGHT_PANE_ID, nxt, explicit=True)

        ttk.Button(
            right_fr, text="Refresh project files", command=_manual_right
        ).pack(anchor="w", pady=(12, 0))
    except Exception:
        return state
    return state


def _esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
