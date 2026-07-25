"""Public countdown: next **entry** (Node A) data clear only.

Display for https://restoreprivacy.online/ homepage. Period matches the product
**weekly entry wipe** service (``OnUnitActiveSec=604800`` / ``7d``).

Honesty:
- **Node A (entry)** aligns with the real weekly entry wipe/rebuild cadence.
- **Exit is never wiped/rebuilt by the weekly service** — no exit timer on the
  homepage (exit stays up for residual failover during entry drain).
- “DATA IS CLEARED” means a **live** preferred-entry wipe/rebuild completion
  (not dry-run timer fires). Without a last-clear anchor the UI uses a fixed
  ~7d epoch grid (mid-period remaining is expected).
- Does **not** erase VPS provider off-box backups/netflow.
"""

from __future__ import annotations

import html
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

# Exact OBJECTIVE labels (case/spacing preserved)
NODE_A_ENTRY_LABEL = "ALL NODE A (ENTRY NODE) DATA IS CLEARED in"
# Kept for tests/back-compat references; not rendered on the homepage (0.3.7+).
NODE_B_EXIT_LABEL = "ALL NODE B (EXIT NODE) DATA IS CLEARED IN"

# Matches weekly entry wipe timer (scripts/install_ephemeral_timer.sh PERIOD=7d)
NODE_WIPE_PERIOD = timedelta(days=7)
NODE_WIPE_PERIOD_SECONDS = int(NODE_WIPE_PERIOD.total_seconds())  # 604800

# Legacy phase constant (unused for public HTML; exit timer removed 0.3.7)
NODE_B_PHASE_SECONDS = NODE_WIPE_PERIOD_SECONDS // 2

# Durable last-clear (written by live preferred-entry wipe completion)
ENTRY_LAST_CLEAR_ENV = "RPT_NODE_A_LAST_CLEAR"
ENTRY_LAST_CLEAR_FILE_ENV = "RPT_NODE_A_LAST_CLEAR_FILE"
ENTRY_LAST_CLEAR_REL = "var/rpt-node-a-last-clear.json"

HONESTY_BLURB = (
    "Preferred entry: ~7d live wipe/rebuild cadence (full selfhost reinstall). "
    "Countdown resets from last live clear when recorded; otherwise a fixed "
    "weekly grid. Dry-run timer fires do not clear data. Exit is never wiped "
    "by this timer (failover). Does not erase provider backups/netflow."
)


def _utc_now(now: datetime | None = None) -> datetime:
    n = now if now is not None else datetime.now(timezone.utc)
    if n.tzinfo is None:
        n = n.replace(tzinfo=timezone.utc)
    return n.astimezone(timezone.utc)


def parse_iso_utc(value: str | None) -> datetime | None:
    """Parse ISO-8601 (``...Z`` or offset) to UTC datetime."""
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def remaining_seconds_until(
    deadline: datetime,
    *,
    now: datetime | None = None,
) -> int:
    """Whole seconds remaining until *deadline* (0 if overdue)."""
    n = _utc_now(now)
    d = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
    delta = d.astimezone(timezone.utc) - n
    return max(0, int(delta.total_seconds()))


def format_countdown(seconds: int) -> str:
    """Compact countdown string (D:HH:MM:SS when days > 0, else HH:MM:SS)."""
    parts = split_countdown_units(seconds)
    d, h, m, s = parts["days"], parts["hours"], parts["minutes"], parts["seconds"]
    if d > 0:
        return f"{d}d {h:02d}:{m:02d}:{s:02d}"
    return f"{h:02d}:{m:02d}:{s:02d}"


def split_countdown_units(seconds: int) -> dict[str, int]:
    """Split remaining seconds into days, hours, minutes, seconds."""
    total = max(0, int(seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    return {
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "seconds": secs,
    }


def unit_boxes_html(seconds: int, *, value_id_prefix: str) -> str:
    """Rounded unit boxes for D / H / M / S (server-rendered initial values)."""
    u = split_countdown_units(seconds)
    cells = (
        ("days", "DAYS", u["days"]),
        ("hours", "HRS", u["hours"]),
        ("minutes", "MIN", u["minutes"]),
        ("seconds", "SEC", u["seconds"]),
    )
    parts: list[str] = []
    for key, lab, val in cells:
        vid = f"{value_id_prefix}-{key}"
        parts.append(
            f'<div class="nw-unit" data-unit="{key}">'
            f'<span class="nw-unit-value" id="{html.escape(vid)}">'
            f"{int(val):02d}</span>"
            f'<span class="nw-unit-label">{lab}</span></div>'
        )
    return (
        f'<div class="nw-units" id="{html.escape(value_id_prefix)}-units" '
        f'aria-live="polite">{"".join(parts)}</div>'
    )


def next_deadline_on_grid(
    *,
    now: datetime | None = None,
    period_seconds: int = NODE_WIPE_PERIOD_SECONDS,
    phase_seconds: int = 0,
) -> datetime:
    """Next clear deadline on a fixed period grid (unix epoch aligned + phase).

    When *now* lands exactly on a boundary, remaining is a full period (next cycle).
    """
    n = _utc_now(now)
    p = int(period_seconds)
    if p <= 0:
        raise ValueError("period_seconds must be positive")
    phase = int(phase_seconds) % p
    epoch = int(n.timestamp())
    # Position within the phased period
    pos = (epoch - phase) % p
    if pos == 0:
        wait = p
    else:
        wait = p - pos
    return datetime.fromtimestamp(epoch + wait, tz=timezone.utc)


def next_clear_from_last(
    last_clear_at: datetime,
    *,
    now: datetime | None = None,
    period: timedelta | None = None,
) -> datetime:
    """Roll *last_clear_at* + period forward until strictly after *now*."""
    n = _utc_now(now)
    p = period if period is not None else NODE_WIPE_PERIOD
    last = last_clear_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    last = last.astimezone(timezone.utc)
    nxt = last + p
    # Cap iterations for safety
    for _ in range(10_000):
        if nxt > n:
            return nxt
        nxt = nxt + p
    return nxt


def _env_last_clear(env_name: str) -> datetime | None:
    return parse_iso_utc(os.environ.get(env_name, "") or None)


def _read_last_clear_file(path: str | Path) -> datetime | None:
    """Parse durable last-clear JSON ``{last_clear_at: ISO}``."""
    try:
        p = Path(path)
        if not p.is_file():
            return None
        import json

        blob = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(blob, dict):
            return None
        return parse_iso_utc(str(blob.get("last_clear_at") or "") or None)
    except Exception:  # noqa: BLE001
        return None


def resolve_entry_last_clear(
    *,
    install_root: str | None = None,
    explicit: datetime | None = None,
) -> datetime | None:
    """Preferred-entry last-clear for the public countdown.

    Priority:
    1. *explicit* argument (tests / caller)
    2. ``RPT_NODE_A_LAST_CLEAR`` env (status host / Render override)
    3. ``RPT_NODE_A_LAST_CLEAR_FILE`` path
    4. ``{install_root}/var/rpt-node-a-last-clear.json`` (live wipe durable write)
    5. default install root ``/opt/restore-privacy/var/rpt-node-a-last-clear.json``
    """
    if explicit is not None:
        return explicit
    env_dt = _env_last_clear(ENTRY_LAST_CLEAR_ENV)
    if env_dt is not None:
        return env_dt
    file_env = (os.environ.get(ENTRY_LAST_CLEAR_FILE_ENV) or "").strip()
    if file_env:
        dt = _read_last_clear_file(file_env)
        if dt is not None:
            return dt
    roots: list[str] = []
    if install_root:
        roots.append(install_root.rstrip("/") or install_root)
    env_root = (os.environ.get("INSTALL_ROOT") or os.environ.get("RPT_INSTALL_ROOT") or "").strip()
    if env_root:
        roots.append(env_root.rstrip("/"))
    roots.append("/opt/restore-privacy")
    seen: set[str] = set()
    for root in roots:
        if root in seen:
            continue
        seen.add(root)
        dt = _read_last_clear_file(f"{root}/{ENTRY_LAST_CLEAR_REL}")
        if dt is not None:
            return dt
    return None


def node_line_state(
    *,
    role: str,
    label: str,
    now: datetime | None = None,
    next_clear_at: datetime | None = None,
    last_clear_at: datetime | None = None,
    period_seconds: int | None = None,
    phase_seconds: int = 0,
) -> dict[str, Any]:
    """Pure state for one node clear countdown line."""
    n = _utc_now(now)
    p_sec = int(period_seconds if period_seconds is not None else NODE_WIPE_PERIOD_SECONDS)
    p = timedelta(seconds=p_sec)
    if next_clear_at is not None:
        nxt = next_clear_at if next_clear_at.tzinfo else next_clear_at.replace(
            tzinfo=timezone.utc
        )
        nxt = nxt.astimezone(timezone.utc)
        # If past, roll by period so UI never dies at zero forever without reset
        if nxt <= n:
            nxt = next_clear_from_last(nxt, now=n, period=p)
    elif last_clear_at is not None:
        nxt = next_clear_from_last(last_clear_at, now=n, period=p)
    else:
        nxt = next_deadline_on_grid(
            now=n, period_seconds=p_sec, phase_seconds=phase_seconds
        )
    rem = remaining_seconds_until(nxt, now=n)
    units = split_countdown_units(rem)
    return {
        "role": role,
        "label": label,
        "available": True,
        "next_clear_at": nxt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "remaining_seconds": rem,
        "display": format_countdown(rem),
        "units": units,
        "period_seconds": p_sec,
    }


def dual_node_wipe_state(
    *,
    now: datetime | None = None,
    entry_next: datetime | None = None,
    exit_next: datetime | None = None,
    entry_last: datetime | None = None,
    exit_last: datetime | None = None,
    period_seconds: int | None = None,
) -> dict[str, Any]:
    """State for both Node A (entry) and Node B (exit) countdown lines."""
    p_sec = int(period_seconds if period_seconds is not None else NODE_WIPE_PERIOD_SECONDS)
    # Optional anchors: explicit args → env / durable last-clear file → grid
    if entry_last is None:
        entry_last = resolve_entry_last_clear()
    if exit_last is None:
        exit_last = _env_last_clear("RPT_NODE_B_LAST_CLEAR")
    if entry_next is None:
        entry_next = parse_iso_utc(os.environ.get("RPT_NODE_A_NEXT_CLEAR", "") or None)
    if exit_next is None:
        exit_next = parse_iso_utc(os.environ.get("RPT_NODE_B_NEXT_CLEAR", "") or None)

    entry = node_line_state(
        role="entry",
        label=NODE_A_ENTRY_LABEL,
        now=now,
        next_clear_at=entry_next,
        last_clear_at=entry_last,
        period_seconds=p_sec,
        phase_seconds=0,
    )
    exit_line = node_line_state(
        role="exit",
        label=NODE_B_EXIT_LABEL,
        now=now,
        next_clear_at=exit_next,
        last_clear_at=exit_last,
        period_seconds=p_sec,
        phase_seconds=NODE_B_PHASE_SECONDS if exit_next is None and exit_last is None else 0,
    )
    return {
        "period_seconds": p_sec,
        "entry": entry,
        "exit": exit_line,
        "blurb": HONESTY_BLURB,
        "labels": {
            "entry": NODE_A_ENTRY_LABEL,
            "exit": NODE_B_EXIT_LABEL,
        },
    }


def render_node_wipe_countdown_html(
    *,
    now: datetime | None = None,
    entry_next: datetime | None = None,
    exit_next: datetime | None = None,
    entry_last: datetime | None = None,
    exit_last: datetime | None = None,
) -> str:
    """Entry-only HTML countdown + 1s client tick (exit timer not rendered)."""
    state = dual_node_wipe_state(
        now=now,
        entry_next=entry_next,
        exit_next=exit_next,
        entry_last=entry_last,
        exit_last=exit_last,
    )
    a = state["entry"]
    label_a = html.escape(str(a["label"]))
    next_a = html.escape(str(a["next_clear_at"]))
    blurb = html.escape(str(state["blurb"]))
    period = int(state["period_seconds"])
    boxes_a = unit_boxes_html(int(a["remaining_seconds"]), value_id_prefix="nw-entry")

    return f"""  <div class="node-wipe-countdown panel-card" id="node-wipe-countdown"
       data-period-seconds="{period}"
       data-next-entry="{next_a}"
       data-entry-only="1">
    <h2 class="panel-title" id="node-wipe-heading">Entry node data clear timer</h2>
    <div class="node-wipe-row" id="node-wipe-row-entry">
      <span class="node-wipe-label" id="node-wipe-label-entry">{label_a}</span>
      {boxes_a}
    </div>
    <p class="node-wipe-blurb" id="node-wipe-blurb">{blurb}</p>
  </div>
  <script>
  (function () {{
    var root = document.getElementById("node-wipe-countdown");
    if (!root) return;
    var nextA = root.getAttribute("data-next-entry") || "";
    var period = parseInt(root.getAttribute("data-period-seconds") || "604800", 10);
    if (!period || period < 1) period = 604800;
    function pad(n) {{ return n < 10 ? "0" + n : String(n); }}
    function split(sec) {{
      sec = Math.max(0, Math.floor(sec));
      var d = Math.floor(sec / 86400);
      var h = Math.floor((sec % 86400) / 3600);
      var m = Math.floor((sec % 3600) / 60);
      var s = sec % 60;
      return {{ d: d, h: h, m: m, s: s }};
    }}
    function paint(prefix, sec) {{
      var u = split(sec);
      var map = {{ days: u.d, hours: u.h, minutes: u.m, seconds: u.s }};
      Object.keys(map).forEach(function (k) {{
        var el = document.getElementById(prefix + "-" + k);
        if (el) el.textContent = pad(map[k]);
      }});
    }}
    function roll(iso) {{
      var d = Date.parse(iso);
      if (isNaN(d)) return null;
      var now = Date.now();
      while (d <= now) {{ d += period * 1000; }}
      return d;
    }}
    var deadlineA = roll(nextA);
    function tick() {{
      var now = Date.now();
      if (deadlineA != null) {{
        while (deadlineA <= now) {{ deadlineA += period * 1000; }}
        paint("nw-entry", Math.max(0, Math.floor((deadlineA - now) / 1000)));
      }}
    }}
    tick();
    setInterval(tick, 1000);
  }})();
  </script>
"""
