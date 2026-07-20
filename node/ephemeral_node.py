"""Ephemeral / short-lived RPT node planning (pure helpers).

Operators use periodic **snapshot** and/or **rebuild** cycles so the VPS does
not accumulate durable on-host state. Live reimage is never the default —
:func:`assert_live_confirm` gates destructive modes.

Honesty:
- Periodic rebuild does **not** erase provider off-box backups or netflow.
- Does **not** replace client residual-tunnel guarantees.
- If long-term node keys are regenerated on rebuild, **public** pins must be
  re-shipped to clients (``product/node_elgamal.pub``).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

DEFAULT_PERIOD = "7d"
DEFAULT_INSTALL_ROOT = "/opt/restore-privacy"

HONESTY_PROVIDER = (
    "Periodic snapshot/rebuild does **not** erase VPS provider off-box backups, "
    "snapshots retained by the hoster, or network/netflow logs."
)
HONESTY_RESIDUAL = (
    "Ephemeral nodes do **not** replace client residual full-tunnel guarantees "
    "(OS VPN / dual /1 still required on the device)."
)
HONESTY_KEYS = (
    "If rebuild regenerates long-term node keys, re-ship the **public** "
    "node_elgamal.pub pin to clients; never distribute node_elgamal.priv."
)
HONESTY_NOLOG = (
    "Rebuild re-applies product no-log + host-privacy defaults "
    "(no connection/session/user-info log sinks)."
)

_INTERVAL_RE = re.compile(
    r"^\s*(\d+)\s*([smhdw]|sec|secs|second|seconds|min|mins|minute|minutes|"
    r"h|hr|hrs|hour|hours|d|day|days|w|wk|wks|week|weeks)?\s*$",
    re.IGNORECASE,
)


def parse_period_seconds(spec: str, *, default: str = DEFAULT_PERIOD) -> int:
    """Parse a periodic interval like ``7d``, ``24h``, ``30m`` into seconds."""
    raw = (spec or default or DEFAULT_PERIOD).strip() or default
    m = _INTERVAL_RE.match(raw)
    if not m:
        raise ValueError(f"invalid period {spec!r} (examples: 7d, 24h, 30m)")
    n = int(m.group(1))
    if n <= 0:
        raise ValueError("period must be positive")
    unit = (m.group(2) or "d").lower()
    if unit in ("s", "sec", "secs", "second", "seconds"):
        mult = 1
    elif unit in ("m", "min", "mins", "minute", "minutes"):
        mult = 60
    elif unit in ("h", "hr", "hrs", "hour", "hours"):
        mult = 3600
    elif unit in ("d", "day", "days"):
        mult = 86400
    elif unit in ("w", "wk", "wks", "week", "weeks"):
        mult = 7 * 86400
    else:
        mult = 86400
    return n * mult


def format_period(seconds: int) -> str:
    """Human-readable period for docs/cron comments."""
    if seconds % (7 * 86400) == 0:
        return f"{seconds // (7 * 86400)}w"
    if seconds % 86400 == 0:
        return f"{seconds // 86400}d"
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def live_confirm_env_name() -> str:
    return "RPT_EPHEMERAL_CONFIRM"


def is_live_confirmed(env: Optional[dict] = None) -> bool:
    e = env if env is not None else os.environ
    return str(e.get(live_confirm_env_name(), "")).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
        "rebuild",
    )


def assert_live_confirm(env: Optional[dict] = None) -> tuple[bool, str]:
    """Gate destructive live rebuild/snapshot. Dry-run never needs this."""
    if is_live_confirmed(env):
        return True, ""
    return (
        False,
        f"refusing live ephemeral action without {live_confirm_env_name()}=yes "
        f"(use --dry-run for a safe plan)",
    )


@dataclass(frozen=True)
class PlanStep:
    """One ordered action in a snapshot/rebuild cycle."""

    id: str
    action: str
    detail: str
    destructive: bool = False
    command: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "detail": self.detail,
            "destructive": self.destructive,
            "command": self.command,
        }


@dataclass
class EphemeralPlan:
    """Full dry-run / live plan for a short-lived node cycle."""

    mode: str  # snapshot | rebuild | snapshot_then_rebuild
    period_spec: str
    period_seconds: int
    install_root: str = DEFAULT_INSTALL_ROOT
    steps: list[PlanStep] = field(default_factory=list)
    dry_run: bool = True
    honesty: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "period_spec": self.period_spec,
            "period_seconds": self.period_seconds,
            "period_label": format_period(self.period_seconds),
            "install_root": self.install_root,
            "dry_run": self.dry_run,
            "steps": [s.to_dict() for s in self.steps],
            "honesty": list(self.honesty),
            "step_ids": [s.id for s in self.steps],
        }

    def format_text(self) -> str:
        lines = [
            f"# Ephemeral / short-lived RPT node plan",
            f"# mode={self.mode} period={self.period_spec} "
            f"({self.period_seconds}s) dry_run={self.dry_run}",
            f"# install_root={self.install_root}",
            "#",
        ]
        for i, step in enumerate(self.steps, 1):
            flag = " [DESTRUCTIVE]" if step.destructive else ""
            lines.append(f"## {i}. {step.id}: {step.action}{flag}")
            lines.append(f"#    {step.detail}")
            if step.command:
                lines.append(step.command)
            lines.append("")
        lines.append("# Honesty:")
        for h in self.honesty:
            lines.append(f"#  - {h}")
        return "\n".join(lines) + "\n"


def build_ephemeral_plan(
    *,
    mode: str = "snapshot_then_rebuild",
    period: str = DEFAULT_PERIOD,
    install_root: str = DEFAULT_INSTALL_ROOT,
    dry_run: bool = True,
    rotate_keys: bool = False,
    provider_snapshot_cmd: str = "",
    provider_rebuild_cmd: str = "",
) -> EphemeralPlan:
    """Construct ordered snapshot/rebuild steps (pure — no side effects)."""
    m = (mode or "snapshot_then_rebuild").strip().lower().replace("-", "_")
    if m in ("both", "all", "snapshot+rebuild", "snapshot_rebuild"):
        m = "snapshot_then_rebuild"
    if m not in ("snapshot", "rebuild", "snapshot_then_rebuild"):
        raise ValueError(
            f"mode must be snapshot|rebuild|snapshot_then_rebuild (got {mode!r})"
        )
    period_sec = parse_period_seconds(period)
    root = (install_root or DEFAULT_INSTALL_ROOT).rstrip("/") or DEFAULT_INSTALL_ROOT
    steps: list[PlanStep] = []

    steps.append(
        PlanStep(
            id="preflight",
            action="Preflight no-log + tooling",
            detail=(
                "Confirm cryptsetup/selfhost scripts present; remind no connection/"
                "session/user-info logs (node/nolog.py)."
            ),
            command=(
                f"test -f {root}/node/nolog.py; "
                f"test -f {root}/node/install.sh || "
                f"test -f scripts/selfhost_node.sh"
            ),
        )
    )

    if m in ("snapshot", "snapshot_then_rebuild"):
        snap_cmd = (
            provider_snapshot_cmd.strip()
            or "# provider-specific: create VPS snapshot via console/API "
            "(set RPT_SNAPSHOT_CMD for live hook)"
        )
        steps.append(
            PlanStep(
                id="snapshot",
                action="VPS snapshot (point-in-time)",
                detail=(
                    "Create a provider **snapshot** of the node disk/VM before rebuild. "
                    "Optional; keeps a rollback image under hoster policy."
                ),
                destructive=False,
                command=snap_cmd,
            )
        )

    if m in ("rebuild", "snapshot_then_rebuild"):
        steps.append(
            PlanStep(
                id="stop_runtime",
                action="Stop node + best-effort runtime wipe",
                detail="systemctl stop rpt-node; run rpt_shutdown_wipe.sh (runtime only).",
                destructive=False,
                command=(
                    "systemctl stop rpt-node 2>/dev/null || true; "
                    f"INSTALL_ROOT={root} bash {root}/node/rpt_shutdown_wipe.sh "
                    f"2>/dev/null || true"
                ),
            )
        )
        reb_cmd = (
            provider_rebuild_cmd.strip()
            or "# provider-specific reimage/rebuild OR keep OS and reinstall software "
            "(set RPT_REBUILD_CMD for live hook; default path re-runs selfhost)"
        )
        steps.append(
            PlanStep(
                id="rebuild_host",
                action="Automated rebuild (reimage or reinstall)",
                detail=(
                    "Provider reimage **or** wipe install tree and re-run selfhost. "
                    "Destructive live mode requires RPT_EPHEMERAL_CONFIRM=yes."
                ),
                destructive=True,
                command=reb_cmd,
            )
        )
        steps.append(
            PlanStep(
                id="selfhost_reapply",
                action="Re-apply product self-host (no-log)",
                detail=(
                    "sudo bash scripts/selfhost_node.sh — install.sh + DNS + "
                    "host-privacy + optional FDE check/wipe wiring."
                ),
                destructive=False,
                command="sudo bash scripts/selfhost_node.sh",
            )
        )
        if rotate_keys:
            steps.append(
                PlanStep(
                    id="rotate_keys",
                    action="Optional long-term key rotation",
                    detail=(
                        "python scripts/rotate_node_keys.py — then publish new "
                        "node_elgamal.pub pin only."
                    ),
                    destructive=True,
                    command=(
                        f"python scripts/rotate_node_keys.py "
                        f"--secrets-dir {root}/secrets"
                    ),
                )
            )
        steps.append(
            PlanStep(
                id="health_check",
                action="Health check after rebuild",
                detail="UDP listen + status UI title-only; no public client count.",
                command=(
                    "ss -ulnp | grep 44044 || true; "
                    "curl -s http://127.0.0.1:8080/api/status || true"
                ),
            )
        )

    steps.append(
        PlanStep(
            id="schedule_next",
            action="Schedule next periodic cycle",
            detail=(
                f"Repeat every {format_period(period_sec)} via systemd timer "
                f"or cron (see ephemeral-node.timer / install_ephemeral_timer.sh)."
            ),
            command=(
                f"# periodic: OnCalendar / cron equivalent for {format_period(period_sec)}"
            ),
        )
    )

    honesty = (HONESTY_PROVIDER, HONESTY_RESIDUAL, HONESTY_KEYS, HONESTY_NOLOG)
    return EphemeralPlan(
        mode=m,
        period_spec=period,
        period_seconds=period_sec,
        install_root=root,
        steps=steps,
        dry_run=dry_run,
        honesty=honesty,
    )


def systemd_timer_unit(
    *,
    period: str = DEFAULT_PERIOD,
    service_name: str = "rpt-ephemeral-rebuild.service",
) -> str:
    """Render a systemd timer unit for periodic ephemeral rebuild dry-run/live."""
    sec = parse_period_seconds(period)
    # Prefer OnUnitActiveSec for simple periodic cadence
    return f"""# Restore Privacy — periodic ephemeral / short-lived node cycle
# Install: install_ephemeral_timer.sh
# Default service should run dry-run unless RPT_EPHEMERAL_CONFIRM=yes
[Unit]
Description=Periodic RPT ephemeral node snapshot/rebuild timer
Documentation=https://github.com/rgsneddon/restore-privacy

[Timer]
OnBootSec=15min
OnUnitActiveSec={sec}
AccuracySec=5min
Persistent=true
Unit={service_name}

[Install]
WantedBy=timers.target
"""


def systemd_service_unit(
    *,
    dry_run: bool = True,
    install_root: str = DEFAULT_INSTALL_ROOT,
) -> str:
    """Render oneshot service invoked by the periodic timer."""
    confirm = "" if dry_run else "Environment=RPT_EPHEMERAL_CONFIRM=yes\n"
    mode_flag = "--dry-run" if dry_run else "--live"
    return f"""# Restore Privacy — ephemeral node rebuild oneshot
[Unit]
Description=RPT ephemeral short-lived node snapshot/rebuild cycle
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory={install_root}
Environment=INSTALL_ROOT={install_root}
Environment=PYTHONPATH={install_root}
{confirm}ExecStart=/usr/bin/env python3 {install_root}/scripts/ephemeral_node.py {mode_flag} --mode snapshot_then_rebuild
Nice=10

[Install]
WantedBy=multi-user.target
"""


def cron_line(
    *,
    period: str = DEFAULT_PERIOD,
    dry_run: bool = True,
    script: str = "/opt/restore-privacy/scripts/ephemeral_node.py",
) -> str:
    """Approximate cron schedule comment + weekly default for 7d."""
    sec = parse_period_seconds(period)
    flag = "--dry-run" if dry_run else "--live"
    if sec >= 7 * 86400 and sec % (7 * 86400) == 0:
        # weekly Monday 04:00
        return (
            f"0 4 * * 1 root /usr/bin/env python3 {script} {flag} "
            f"--mode snapshot_then_rebuild  # periodic every {format_period(sec)}"
        )
    if sec >= 86400 and sec % 86400 == 0:
        days = sec // 86400
        return (
            f"0 4 */{days} * * root /usr/bin/env python3 {script} {flag} "
            f"--mode snapshot_then_rebuild  # periodic every {format_period(sec)}"
        )
    return (
        f"# periodic every {format_period(sec)} — prefer systemd timer "
        f"(OnUnitActiveSec={sec})\n"
        f"0 4 * * * root /usr/bin/env python3 {script} {flag} "
        f"--mode snapshot_then_rebuild"
    )
