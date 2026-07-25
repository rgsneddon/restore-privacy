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
from typing import Any, Optional, Sequence  # noqa: F401 — Sequence used by fleet summary

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
HONESTY_EXCLUSIVE = (
    "Fleet wipe/rebuild holds an exclusive rebuild lock for **one peer at a time**. "
    "Never run two node wipe/rebuild instances at once. Sequential order: Iceland "
    "first, then Romania only after Iceland is fully rebuilt, then any new catalog "
    "countries in the same recursive order (node.fleet_wipe)."
)
HONESTY_FAILOVER = (
    "While a peer is draining/down, clients automatically residual-failover to a "
    "healthy catalog peer; when the preferred entry is healthy again they re-prefer "
    "it. Fail closed if no peer is healthy before wipe (do not wipe the last residual "
    "path into a black hole)."
)

# Weekly/fleet timed service: single peer roles (legacy entry = IS first)
WEEKLY_ENTRY_ROLE = "entry"
EXIT_ROLE = "exit"
FORBIDDEN_WEEKLY_ROLES = frozenset({"exit", "both", "all"})

# Shared product reinstall surface (scripts/selfhost_node.sh pipeline)
SELFHOST_SCRIPT = "scripts/selfhost_node.sh"
# Force full product surface after wipe (never skip DNS / host privacy on weekly path)
SELFHOST_FULL_CMD = (
    "sudo env SKIP_DNS=0 SKIP_HOST_PRIVACY=0 SKIP_DISK_ENCRYPTION=1 "
    "bash scripts/selfhost_node.sh"
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
                action="Re-apply product self-host (no-log) — full reinstall",
                detail=(
                    "Mandatory full reinstall: install.sh + tunnel DNS + "
                    "host-privacy via selfhost (SKIP_DNS=0 SKIP_HOST_PRIVACY=0). "
                    "Bare wiped host is not acceptable."
                ),
                destructive=False,
                command=SELFHOST_FULL_CMD,
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


def assert_weekly_entry_role_only(role: str) -> tuple[bool, str]:
    """Refuse bulk multi-node roles; allow single-peer fleet roles.

    Legacy weekly path used role=``entry`` (Iceland first). Fleet sequential
    wipe also allows country codes (``is``, ``ro``, …) one at a time.
    ``exit``/``both``/``all`` remain refused (use sequential planner instead).
    """
    r = (role or "").strip().lower()
    if r in FORBIDDEN_WEEKLY_ROLES:
        return (
            False,
            f"refusing weekly wipe for role={role!r}: entry-only / sequential fleet; "
            f"never rebuild exit/both/all as concurrent bulk — wipe one peer at a time "
            f"(IS complete before RO)",
        )
    if r in ("", "auto", "next", "fleet"):
        return True, ""
    if r == WEEKLY_ENTRY_ROLE or r in ("is", "ro") or (2 <= len(r) <= 3 and r.isalpha()):
        return True, ""
    return (
        False,
        f"weekly/fleet wipe role must be auto|entry|is|ro|<country> (got {role!r})",
    )


def build_fleet_sequential_plan_summary(
    *,
    completed: Sequence[str] | None = None,
    in_progress: str | None = None,
) -> dict[str, Any]:
    """Dry-run fleet wipe state (pure) for operator/timer orchestration."""
    from node.fleet_wipe import (
        assert_sequential_fleet_start,
        fleet_country_codes,
        next_wipe_target,
    )

    done = list(completed or [])
    order = fleet_country_codes()
    nxt = next_wipe_target(completed=done, in_progress=in_progress)
    decisions = {
        code: assert_sequential_fleet_start(
            code, completed=done, in_progress=in_progress
        ).to_dict()
        for code in order
    }
    return {
        "fleet_order": order,
        "completed": done,
        "in_progress": in_progress,
        "next_target": nxt,
        "decisions": decisions,
        "honesty": [HONESTY_EXCLUSIVE, HONESTY_FAILOVER],
    }


@dataclass(frozen=True)
class RoleReinstallRequirement:
    """One mandatory reinstall/check item for a node role after wipe/rebuild."""

    id: str
    description: str
    command: str = ""
    roles: tuple[str, ...] = ("entry", "exit")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "command": self.command,
            "roles": list(self.roles),
        }


def _shared_reinstall_requirements() -> list[RoleReinstallRequirement]:
    """Core product surface both entry and exit must restore after rebuild."""
    return [
        RoleReinstallRequirement(
            id="core_node_install",
            description=(
                "Core node install: keys/venv/systemd/no-log via node/install.sh "
                "(through selfhost_node.sh)"
            ),
            command="bash node/install.sh",
            roles=("entry", "exit"),
        ),
        RoleReinstallRequirement(
            id="tunnel_dns",
            description=(
                "Tunnel-only DNS (Unbound 10.88.0.1) via node/install_dns.sh — "
                "product residual DNS; do not skip on weekly entry path"
            ),
            command="bash node/install_dns.sh",
            roles=("entry", "exit"),
        ),
        RoleReinstallRequirement(
            id="host_privacy",
            description=(
                "Host privacy hardening via node/install_host_privacy.sh "
                "(journal/banners as shipped)"
            ),
            command="bash node/install_host_privacy.sh",
            roles=("entry", "exit"),
        ),
        RoleReinstallRequirement(
            id="selfhost_full",
            description=(
                f"Mandatory full self-host: {SELFHOST_SCRIPT} with DNS + host privacy "
                f"(SKIP_DNS=0 SKIP_HOST_PRIVACY=0)"
            ),
            command=SELFHOST_FULL_CMD,
            roles=("entry", "exit"),
        ),
        RoleReinstallRequirement(
            id="udp_listen_health",
            description="UDP residual listen on product port 44044 after reinstall",
            command="ss -ulnp | grep 44044",
            roles=("entry", "exit"),
        ),
        RoleReinstallRequirement(
            id="status_surface_health",
            description="Local status UI title-only surface after reinstall",
            command="curl -s http://127.0.0.1:8080/api/status || true",
            roles=("entry", "exit"),
        ),
    ]


def entry_reinstall_requirements() -> list[RoleReinstallRequirement]:
    """Mandatory reinstall surface for the **entry** (Iceland product) node."""
    shared = _shared_reinstall_requirements()
    entry_only = [
        RoleReinstallRequirement(
            id="entry_product_pin",
            description=(
                "Entry long-term ElGamal **public** pin product/node_elgamal.pub "
                "(never ship priv); clients pin entry by default"
            ),
            command=(
                "test -f secrets/node_elgamal.pub || "
                "test -f product/node_elgamal.pub"
            ),
            roles=("entry",),
        ),
        RoleReinstallRequirement(
            id="entry_weekly_failover_gates",
            description=(
                "Weekly wipe only: exit residual preflight + entry pre-wipe health "
                "fail closed before drain (clients failover to exit)"
            ),
            command=(
                "python3 -c \"from node.wipe_preflight import run_live_prewipe_gates; "
                "g=run_live_prewipe_gates(); assert g.allow_wipe\""
            ),
            roles=("entry",),
        ),
        RoleReinstallRequirement(
            id="entry_exclusive_rebuild_lock",
            description=(
                "Exclusive rebuild lock role=entry only — refuse concurrent wipe; "
                "never wipe exit from weekly timer"
            ),
            command=(
                "python3 -c \"from node.rebuild_lock import acquire_rebuild_lock; "
                "ok,m,_=acquire_rebuild_lock('entry'); assert ok, m\""
            ),
            roles=("entry",),
        ),
        RoleReinstallRequirement(
            id="entry_client_reentry_preference",
            description=(
                "After entry healthy: clients prefer re-entry residual "
                "(multihop select_residual_endpoint); exit remains failover hop"
            ),
            command="# product client multihop re-entry preference (automatic)",
            roles=("entry",),
        ),
    ]
    return shared + entry_only


def exit_reinstall_requirements() -> list[RoleReinstallRequirement]:
    """Mandatory reinstall surface for the **exit** (Romania hop) node.

    Exit is **not** on the weekly timed wipe service. Operator/manual rebuild
    still needs full product reinstall plus exit-only key/firewall posture.
    """
    shared = _shared_reinstall_requirements()
    exit_only = [
        RoleReinstallRequirement(
            id="exit_only_elgamal_keys",
            description=(
                "Exit uses **distinct** exit ElGamal key material "
                "(product/exit_node_elgamal.pub) — not the entry product pin"
            ),
            command=(
                "test -f secrets/node_elgamal.pub; "
                "# pub must differ from product entry pin"
            ),
            roles=("exit",),
        ),
        RoleReinstallRequirement(
            id="exit_udp_firewall_44044",
            description=(
                "Host/provider allow UDP 44044 for residual exit path "
                "(ufw allow 44044/udp when ufw enabled; FlokiNET panel open)"
            ),
            command="ufw status || true; # confirm 44044/udp allowed when ufw on",
            roles=("exit",),
        ),
        RoleReinstallRequirement(
            id="exit_no_weekly_timer",
            description=(
                "Do **not** install weekly entry wipe timer on exit; "
                "exit stays up for failover during entry drain"
            ),
            command=(
                "# refuse: systemctl enable rpt-ephemeral-rebuild.timer on exit host"
            ),
            roles=("exit",),
        ),
        RoleReinstallRequirement(
            id="exit_hop_identity",
            description=(
                "Exit host monopin Romania PRODUCT_EXIT_HOST (≠ entry Iceland); "
                "see scripts/MULTIHOP_EXIT_HOP_PREP.md"
            ),
            command="# RPT_NODE_HOST / hop env must be exit IP not entry",
            roles=("exit",),
        ),
    ]
    return shared + exit_only


def reinstall_requirements_for_role(role: str) -> list[RoleReinstallRequirement]:
    """Return pure reinstall requirement list for *role* (entry|exit)."""
    r = (role or "").strip().lower()
    if r == WEEKLY_ENTRY_ROLE or r == "entry":
        return entry_reinstall_requirements()
    if r == EXIT_ROLE or r == "exit":
        return exit_reinstall_requirements()
    raise ValueError(f"unknown reinstall role {role!r} (entry|exit)")


def role_reinstall_requirement_ids(role: str) -> list[str]:
    return [req.id for req in reinstall_requirements_for_role(role)]


def assert_role_reinstall_lists_differ() -> tuple[bool, str]:
    """Structural honesty: entry and exit reinstall lists are not identical."""
    e = set(role_reinstall_requirement_ids("entry"))
    x = set(role_reinstall_requirement_ids("exit"))
    if e == x:
        return False, "entry and exit reinstall requirement ids are identical"
    if not (e - x):
        return False, "entry has no unique reinstall requirements"
    if not (x - e):
        return False, "exit has no unique reinstall requirements"
    shared = e & x
    for need in (
        "core_node_install",
        "tunnel_dns",
        "host_privacy",
        "selfhost_full",
    ):
        if need not in shared:
            return False, f"shared requirement missing: {need}"
    return True, f"entry_unique={sorted(e - x)} exit_unique={sorted(x - e)}"


def plan_embeds_mandatory_reinstall(step_ids: Sequence[str]) -> bool:
    """True when plan step ids include mandatory package/selfhost reinstall."""
    ids = set(step_ids or [])
    return "selfhost_reapply" in ids or "selfhost_full" in ids


def build_exit_manual_reinstall_plan(
    *,
    install_root: str = DEFAULT_INSTALL_ROOT,
    dry_run: bool = True,
    rotate_keys: bool = False,
) -> EphemeralPlan:
    """Manual/operator exit-node reinstall plan (not weekly timed).

    Distinct from :func:`build_weekly_entry_rebuild_plan`: no entry exclusive
    weekly lock, no exit-failover preflight (this host *is* the exit), includes
    exit-only key/firewall requirements, and must not schedule weekly entry wipe.
    """
    root = (install_root or DEFAULT_INSTALL_ROOT).rstrip("/") or DEFAULT_INSTALL_ROOT
    steps: list[PlanStep] = [
        PlanStep(
            id="role_guard",
            action="Exit role reinstall (manual — not weekly entry timer)",
            detail=(
                "Exit hop rebuild is **operator/manual**. Weekly timed wipe must "
                "never target exit so entry can failover during its own drain."
            ),
            command="# role=exit manual reinstall only",
        ),
        PlanStep(
            id="exit_requirements_preflight",
            action="Exit-only reinstall requirements checklist",
            detail="; ".join(
                f"{r.id}: {r.description}" for r in exit_reinstall_requirements()
            ),
            command="# see node.ephemeral_node.exit_reinstall_requirements()",
        ),
        PlanStep(
            id="stop_runtime",
            action="Stop exit node + best-effort runtime wipe",
            detail="systemctl stop rpt-node; runtime wipe only (not provider snapshot).",
            command=(
                "systemctl stop rpt-node 2>/dev/null || true; "
                f"INSTALL_ROOT={root} bash {root}/node/rpt_shutdown_wipe.sh "
                f"2>/dev/null || true"
            ),
        ),
        PlanStep(
            id="rebuild_host",
            action="Rebuild / reimage exit host (operator)",
            detail=(
                "Provider reimage or wipe install tree. Destructive live needs "
                "RPT_EPHEMERAL_CONFIRM=yes. Exit keys should remain exit-only."
            ),
            destructive=True,
            command=(
                "# provider reimage OR keep OS and reinstall software "
                "(set RPT_REBUILD_CMD for live hook)"
            ),
        ),
        PlanStep(
            id="selfhost_reapply",
            action="Package reinstall / full product self-host on exit",
            detail=(
                "Mandatory: install.sh + DNS + host-privacy via selfhost "
                "(SKIP_DNS=0 SKIP_HOST_PRIVACY=0). Bare wiped host is not acceptable."
            ),
            command=SELFHOST_FULL_CMD,
        ),
        PlanStep(
            id="exit_key_and_firewall",
            action="Confirm exit ElGamal + UDP 44044 posture",
            detail=(
                "Exit pub must differ from entry product pin; ensure 44044/udp "
                "allowed (host ufw + FlokiNET panel)."
            ),
            command=(
                "test -f secrets/node_elgamal.pub; "
                "ss -ulnp | grep 44044 || true"
            ),
        ),
        PlanStep(
            id="health_check",
            action="Health check after exit reinstall",
            detail="UDP listen + optional local status UI; residual exit ready for failover.",
            command=(
                "ss -ulnp | grep 44044 || true; "
                "curl -s http://127.0.0.1:8080/api/status || true"
            ),
        ),
        PlanStep(
            id="no_weekly_timer",
            action="Do not enable weekly entry wipe timer on exit",
            detail=(
                "Exit must stay available during entry weekly drain. "
                "Never enable rpt-ephemeral-rebuild.timer / weekly_entry_rebuild on exit."
            ),
            command=(
                "# systemctl disable --now rpt-ephemeral-rebuild.timer 2>/dev/null || true"
            ),
        ),
    ]
    if rotate_keys:
        steps.insert(
            5,
            PlanStep(
                id="rotate_keys",
                action="Optional exit long-term key rotation",
                detail=(
                    "Rotate exit keys only; re-ship product/exit_node_elgamal.pub — "
                    "never confuse with entry pin."
                ),
                destructive=True,
                command=(
                    f"python scripts/rotate_node_keys.py --secrets-dir {root}/secrets"
                ),
            ),
        )
    honesty = (
        HONESTY_PROVIDER,
        HONESTY_RESIDUAL,
        HONESTY_KEYS,
        HONESTY_NOLOG,
        HONESTY_EXCLUSIVE,
        HONESTY_FAILOVER,
        "Manual exit-host reinstall remains available; fleet weekly path now "
        "wipes RO sequentially after IS is complete (node.fleet_wipe).",
    )
    return EphemeralPlan(
        mode="exit_manual_reinstall",
        period_spec="manual",
        period_seconds=0,
        install_root=root,
        steps=steps,
        dry_run=dry_run,
        honesty=honesty,
    )


def build_weekly_entry_rebuild_plan(
    *,
    period: str = DEFAULT_PERIOD,
    install_root: str = DEFAULT_INSTALL_ROOT,
    dry_run: bool = True,
    rotate_keys: bool = False,
    role: str = "auto",
    exit_healthy: bool = True,
    entry_healthy: bool = True,
    provider_snapshot_cmd: str = "",
    provider_rebuild_cmd: str = "",
    completed: Sequence[str] | None = None,
    in_progress: str | None = None,
    peer_health: dict[str, bool] | None = None,
) -> EphemeralPlan:
    """Sequential fleet wipe plan (IS → RO → new peers) with exclusive lock.

    Pure planner (no side effects). Live execution still requires
    ``RPT_EPHEMERAL_CONFIRM`` and exclusive rebuild lock.

    Target country comes from :func:`node.fleet_wipe.resolve_weekly_target`
    (``role=auto`` picks next incomplete peer; ``role=is|ro|entry`` validates order).

    Fail closed: if peer residual or local node health is False, abort without
    destructive rebuild. Concurrent / out-of-order targets are refused.
    """
    from node.fleet_wipe import (
        assert_raw_wipe_role_allowed,
        evaluate_peer_prewipe_gate,
        resolve_weekly_target,
        role_for_country_code,
    )

    # Refuse bulk roles before any country mapping (exit must not become RO)
    ok_raw, raw_msg = assert_raw_wipe_role_allowed(role)
    if not ok_raw:
        raise ValueError(raw_msg)
    ok_role0, role_msg0 = assert_weekly_entry_role_only(role)
    if not ok_role0:
        raise ValueError(role_msg0)

    period_sec = parse_period_seconds(period)
    root = (install_root or DEFAULT_INSTALL_ROOT).rstrip("/") or DEFAULT_INSTALL_ROOT
    done_in = list(completed or [])
    decision = resolve_weekly_target(
        completed=done_in, in_progress=in_progress, role_hint=role
    )
    if not decision.allow or not decision.target_code:
        raise ValueError(
            decision.reason
            or "fleet wipe refused (cycle complete or invalid target)"
        )
    # Authoritative completed list for this plan (auto cycle-roll clears to [])
    done = list(decision.completed)
    target = decision.target_code
    lock_role = role_for_country_code(target)
    ok_role, role_msg = assert_weekly_entry_role_only(lock_role)
    if not ok_role:
        raise ValueError(role_msg)

    # Peer map: default other peers healthy when exit_healthy True
    from node.fleet_wipe import fleet_country_codes

    all_codes = fleet_country_codes()
    ph: dict[str, bool] = {}
    if peer_health is not None:
        ph = {str(k).upper(): bool(v) for k, v in peer_health.items()}
    else:
        for c in all_codes:
            if c == target:
                ph[c] = bool(entry_healthy)
            else:
                ph[c] = bool(exit_healthy)
    peer_gate = evaluate_peer_prewipe_gate(target, ph)
    peer_ok = bool(peer_gate.allow_wipe) and bool(exit_healthy)
    local_ok = bool(entry_healthy)

    steps: list[PlanStep] = []
    steps.append(
        PlanStep(
            id="fleet_target_resolve",
            action=f"Fleet wipe target = {target} (sequential IS→RO→new)",
            detail=(
                f"next_wipe_target / resolve_weekly_target → {target}. "
                f"completed={list(done)} in_progress={in_progress!r}. "
                f"{decision.reason}"
            ),
            command=(
                f"# target={target} lock_role={lock_role} "
                f"next_after={decision.next_after_complete!r}"
            ),
        )
    )
    steps.append(
        PlanStep(
            id="role_guard",
            action=f"Single-peer role guard ({lock_role}) — refuse bulk concurrent",
            detail=(
                "Sequential fleet wipe: one catalog peer at a time. "
                "Refuse exit|both|all bulk roles; RO only after IS complete."
            ),
            command=(
                f"# role={lock_role}; refuse exit|both|all concurrent multi-node wipe"
            ),
        )
    )
    steps.append(
        PlanStep(
            id="exclusive_lock_acquire",
            action=f"Acquire exclusive rebuild lock ({lock_role})",
            detail=(
                "Single-instance mutual exclusion via var/rpt-rebuild.lock. "
                "Second concurrent start fails closed (never two wipe instances)."
            ),
            command=(
                f"python3 -c \"from node.rebuild_lock import acquire_rebuild_lock; "
                f"ok,m,s=acquire_rebuild_lock({lock_role!r},install_root={root!r},"
                f"state='draining'); assert ok, m; print(m)\""
            ),
        )
    )
    steps.append(
        PlanStep(
            id="peer_failover_preflight",
            action="Catalog peer health preflight (≥1 healthy peer required)",
            detail=(
                f"Before draining {target}, confirm ≥1 other catalog peer residual is "
                f"healthy for client failover. Healthy peers: "
                f"{list(peer_gate.healthy_peers)}. Fail closed if none."
            ),
            command=(
                (
                    f"python3 -c \"from node.wipe_preflight import "
                    f"evaluate_catalog_peer_prewipe; "
                    f"g=evaluate_catalog_peer_prewipe({target!r},{ph!r}); "
                    f"assert g.allow_wipe, g.reasons; print(g.reasons)\""
                )
                if peer_ok
                else f"# ABORT: peer residual unhealthy — refuse wipe of {target}"
            ),
            destructive=not peer_ok,
        )
    )
    steps.append(
        PlanStep(
            id="entry_node_preflight",
            action=f"Local node pre-wipe health for {target}",
            detail=(
                "Confirm product surface is healthy before wipe so rebuild + "
                "package reinstall restore a known-good posture."
            ),
            command=(
                "python3 -c \"from node.wipe_preflight import check_entry_node_health; "
                "r=check_entry_node_health(); assert r.ok, r.detail; print(r.detail)\""
                if local_ok
                else f"# ABORT: local health failed — refuse wipe of {target}"
            ),
            destructive=not local_ok,
        )
    )

    if not peer_ok or not local_ok:
        abort_id = (
            "abort_peer_unhealthy" if not peer_ok else "abort_local_unhealthy"
        )
        abort_action = (
            f"Abort: no healthy peer for failover while wiping {target}"
            if not peer_ok
            else f"Abort: local pre-wipe health failed for {target}"
        )
        steps.append(
            PlanStep(
                id=abort_id,
                action=abort_action,
                detail=(
                    "Peer wipe cancelled. Retain current node for clients. "
                    "Fix health first, then re-run fleet plan. Exclusive lock released."
                ),
                command=(
                    f"python3 -c \"from node.rebuild_lock import release_rebuild_lock; "
                    f"print(release_rebuild_lock(install_root={root!r}))\""
                ),
            )
        )
        steps.append(
            PlanStep(
                id="schedule_next",
                action="Schedule next periodic fleet cycle",
                detail=(
                    f"Retry every {format_period(period_sec)} once pre-wipe gates pass. "
                    f"Target remains {target} until complete."
                ),
                command=(
                    f"# periodic: OnUnitActiveSec={period_sec} / cron for {format_period(period_sec)}"
                ),
            )
        )
        honesty = (
            HONESTY_PROVIDER,
            HONESTY_RESIDUAL,
            HONESTY_KEYS,
            HONESTY_NOLOG,
            HONESTY_EXCLUSIVE,
            HONESTY_FAILOVER,
        )
        return EphemeralPlan(
            mode="weekly_fleet_rebuild_aborted",
            period_spec=period,
            period_seconds=period_sec,
            install_root=root,
            steps=steps,
            dry_run=dry_run,
            honesty=honesty,
        )

    # Healthy peer + local: full drain + rebuild for this fleet target
    base = build_ephemeral_plan(
        mode="snapshot_then_rebuild",
        period=period,
        install_root=root,
        dry_run=dry_run,
        rotate_keys=rotate_keys,
        provider_snapshot_cmd=provider_snapshot_cmd,
        provider_rebuild_cmd=provider_rebuild_cmd,
    )
    steps.append(
        PlanStep(
            id="mark_entry_draining",
            action=f"Mark {target} draining for client peer failover",
            detail=(
                "Lock state=draining/rebuilding so clients treat preferred entry as "
                "unavailable and residual-failover to a healthy catalog peer."
            ),
            command=(
                f"python3 -c \"from node.rebuild_lock import update_rebuild_lock_state; "
                f"from node.fleet_wipe import save_fleet_wipe_state; "
                f"print(update_rebuild_lock_state('draining',install_root={root!r})); "
                f"print(save_fleet_wipe_state(completed={done!r},"
                f"in_progress={target!r},install_root={root!r}))\""
            ),
        )
    )
    for s in base.steps:
        if s.id in ("preflight", "schedule_next"):
            continue
        if s.id == "stop_runtime":
            steps.append(
                PlanStep(
                    id="mark_rebuilding",
                    action="Advance lock state to rebuilding",
                    detail="Exclusive lock remains held; no second wipe may start.",
                    command=(
                        f"python3 -c \"from node.rebuild_lock import update_rebuild_lock_state; "
                        f"print(update_rebuild_lock_state('rebuilding',install_root={root!r}))\""
                    ),
                )
            )
        # Rename clarity: selfhost is mandatory package reinstall on live path
        if s.id == "selfhost_reapply":
            entry_req_detail = "; ".join(
                f"{r.id}" for r in entry_reinstall_requirements()
            )
            steps.append(
                PlanStep(
                    id="selfhost_reapply",
                    action="Package reinstall / full product self-host (no-log)",
                    detail=(
                        "Mandatory after rebuild: full reinstall via selfhost_node.sh "
                        "(install.sh + DNS + host-privacy + no-log; "
                        "SKIP_DNS=0 SKIP_HOST_PRIVACY=0). Bare wiped host is not "
                        f"acceptable. Entry requirements: {entry_req_detail}"
                    ),
                    destructive=False,
                    command=SELFHOST_FULL_CMD,
                )
            )
            # Explicit component checks after selfhost (entry role)
            steps.append(
                PlanStep(
                    id="reinstall_core_dns_privacy_verify",
                    action="Verify core install + tunnel DNS + host privacy surface",
                    detail=(
                        "Confirm product node install tree, residual DNS default, "
                        "and host-privacy scripts were re-applied (entry requirements)."
                    ),
                    command=(
                        f"test -f {root}/node/nolog.py; "
                        f"test -f {root}/node/install.sh || test -f scripts/selfhost_node.sh; "
                        f"test -f {root}/node/install_dns.sh || true; "
                        f"test -f {root}/node/install_host_privacy.sh || true"
                    ),
                )
            )
            steps.append(
                PlanStep(
                    id="entry_product_pin_check",
                    action="Confirm entry public pin present (no priv shipping)",
                    detail=(
                        "Entry ElGamal public pin must exist after reinstall; "
                        "never distribute node_elgamal.priv."
                    ),
                    command=(
                        f"test -f {root}/secrets/node_elgamal.pub || "
                        f"test -f product/node_elgamal.pub"
                    ),
                )
            )
            continue
        steps.append(s)

    steps.append(
        PlanStep(
            id="mark_fleet_peer_complete",
            action=f"Mark fleet wipe complete for {target}; unlock next peer",
            detail=(
                f"After health_check, record {target} complete so next_wipe_target "
                f"advances (e.g. IS complete → RO). Recursive for new catalog countries."
            ),
            command=(
                f"python3 -c \"from node.fleet_wipe import mark_wipe_complete, "
                f"save_fleet_wipe_state; "
                f"done,nxt=mark_wipe_complete({target!r},completed={done!r}); "
                f"print(save_fleet_wipe_state(completed=done,in_progress=None,"
                f"install_root={root!r})); print('next',nxt)\""
            ),
        )
    )
    steps.append(
        PlanStep(
            id="exclusive_lock_release",
            action="Release exclusive rebuild lock",
            detail=(
                "Peer healthy again → clients may re-prefer this country as entry. "
                "Only release after health_check so failover ends cleanly. "
                "Next fleet peer wipe may then start (never concurrent)."
            ),
            command=(
                f"python3 -c \"from node.rebuild_lock import release_rebuild_lock; "
                f"print(release_rebuild_lock(install_root={root!r}))\""
            ),
        )
    )
    steps.append(
        PlanStep(
            id="schedule_next",
            action="Schedule next sequential fleet wipe cycle",
            detail=(
                f"Repeat every {format_period(period_sec)} via systemd timer "
                f"(install_ephemeral_timer.sh / weekly_entry_rebuild). "
                f"Next target after {target}: {decision.next_after_complete or 'cycle complete'}. "
                f"Never concurrent multi-node wipe."
            ),
            command=(
                f"# periodic: OnUnitActiveSec={period_sec} for {format_period(period_sec)} "
                f"sequential fleet wipe target={target}"
            ),
        )
    )

    honesty = (
        HONESTY_PROVIDER,
        HONESTY_RESIDUAL,
        HONESTY_KEYS,
        HONESTY_NOLOG,
        HONESTY_EXCLUSIVE,
        HONESTY_FAILOVER,
    )
    return EphemeralPlan(
        mode="weekly_fleet_rebuild",
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
    weekly_entry: bool = True,
) -> str:
    """Render oneshot service invoked by the periodic timer.

    Default ``weekly_entry=True`` runs the entry-only weekly wipe planner
    (exclusive lock; never exit/both). Set False for legacy generic ephemeral.
    """
    confirm = "" if dry_run else "Environment=RPT_EPHEMERAL_CONFIRM=yes\n"
    mode_flag = "--dry-run" if dry_run else "--live"
    if weekly_entry:
        exec_line = (
            f"/usr/bin/env python3 {install_root}/scripts/weekly_entry_rebuild.py "
            f"{mode_flag} --period 7d"
        )
        desc = "RPT weekly entry-only wipe/rebuild (exclusive lock; exit failover)"
    else:
        exec_line = (
            f"/usr/bin/env python3 {install_root}/scripts/ephemeral_node.py "
            f"{mode_flag} --mode snapshot_then_rebuild"
        )
        desc = "RPT ephemeral short-lived node snapshot/rebuild cycle"
    return f"""# Restore Privacy — ephemeral / weekly entry rebuild oneshot
[Unit]
Description={desc}
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory={install_root}
Environment=INSTALL_ROOT={install_root}
Environment=PYTHONPATH={install_root}
{confirm}ExecStart={exec_line}
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
