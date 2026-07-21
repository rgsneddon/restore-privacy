"""Flyclient-style fast path for full residual connection (restore_privacy).

Maps the *tip-then-full* idea to residual VPN: pure, unit-testable decisions that
skip redundant work on the full-connect critical path (HELLO → plan → TUN →
routes / DNS / kill-switch) without weakening product wire (pin, PFS, outer obfs).

Not blockchain FlyClient (PoW header sampling).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Sequence

from client.full_tunnel import FullTunnelPlan, assert_full_tunnel_plan, build_full_tunnel_plan


class FullConnectStep(str, Enum):
    """Ordered phases of a product full residual connection."""

    PREPARE_SECRETS = "prepare_secrets"
    BUILD_HELLO = "build_hello"
    HELLO_EXCHANGE = "hello_exchange"
    BUILD_TUNNEL_PLAN = "build_tunnel_plan"
    ATTACH_TUN = "attach_tun"
    APPLY_ROUTES = "apply_routes"
    APPLY_DNS_KILL_SWITCH = "apply_dns_kill_switch"


# Critical path for a cold full residual connect (document for operators/tests).
FULL_CONNECT_CRITICAL_PATH: tuple[FullConnectStep, ...] = (
    FullConnectStep.PREPARE_SECRETS,
    FullConnectStep.BUILD_HELLO,
    FullConnectStep.HELLO_EXCHANGE,
    FullConnectStep.BUILD_TUNNEL_PLAN,
    FullConnectStep.ATTACH_TUN,
    FullConnectStep.APPLY_ROUTES,
    FullConnectStep.APPLY_DNS_KILL_SWITCH,
)


@dataclass(frozen=True)
class FlyclientConnectState:
    """Snapshot used to decide which full-connect work is still needed."""

    session_connected: bool = False
    session_vpn_ip: str = ""
    residual_routes_applied: bool = False
    residual_tun_up: bool = False
    has_if_index_or_iface: bool = False
    tunnel_plan_vpn_ip: str = ""
    force_reconnect: bool = False


@dataclass
class FlyclientStepPlan:
    """Ordered remaining steps + pure notes for a flyclient-style full connect."""

    steps: list[FullConnectStep] = field(default_factory=list)
    skipped: list[FullConnectStep] = field(default_factory=list)
    early_exit: bool = False
    reason: str = ""

    def needs_hello(self) -> bool:
        return FullConnectStep.HELLO_EXCHANGE in self.steps

    def needs_residual_attach(self) -> bool:
        return any(
            s
            in (
                FullConnectStep.ATTACH_TUN,
                FullConnectStep.APPLY_ROUTES,
                FullConnectStep.APPLY_DNS_KILL_SWITCH,
            )
            for s in self.steps
        )


def flyclient_decide_full_connect_work(state: FlyclientConnectState) -> FlyclientStepPlan:
    """Return remaining full-connect steps; skip work already done (flyclient tip).

    Early exit when residual is already up for the live session (no re-HELLO, no
    re-route). When session is live but residual is not, only attach/routes/DNS
    remain. Cold path runs the full critical path.
    """
    plan = FlyclientStepPlan()
    remaining = list(FULL_CONNECT_CRITICAL_PATH)

    if state.force_reconnect:
        plan.steps = remaining
        plan.reason = "force_reconnect"
        return plan

    # Tip: already residual-ready for this session — skip entire critical path.
    if (
        state.session_connected
        and state.session_vpn_ip
        and state.residual_tun_up
        and state.residual_routes_applied
        and not state.force_reconnect
    ):
        plan.early_exit = True
        plan.skipped = remaining
        plan.reason = "already_residual_ready"
        return plan

    if state.session_connected and state.session_vpn_ip and not state.force_reconnect:
        # Session tip is warm: skip HELLO rebuild / exchange / secrets.
        skip_hello = {
            FullConnectStep.PREPARE_SECRETS,
            FullConnectStep.BUILD_HELLO,
            FullConnectStep.HELLO_EXCHANGE,
        }
        plan.skipped.extend([s for s in remaining if s in skip_hello])
        remaining = [s for s in remaining if s not in skip_hello]

        plan_ok = (
            state.tunnel_plan_vpn_ip
            and state.tunnel_plan_vpn_ip == state.session_vpn_ip
        )
        if plan_ok:
            plan.skipped.append(FullConnectStep.BUILD_TUNNEL_PLAN)
            remaining = [
                s for s in remaining if s != FullConnectStep.BUILD_TUNNEL_PLAN
            ]

        if state.residual_tun_up:
            plan.skipped.append(FullConnectStep.ATTACH_TUN)
            remaining = [s for s in remaining if s != FullConnectStep.ATTACH_TUN]

        if state.residual_routes_applied:
            for s in (
                FullConnectStep.APPLY_ROUTES,
                FullConnectStep.APPLY_DNS_KILL_SWITCH,
            ):
                if s in remaining:
                    plan.skipped.append(s)
            remaining = [
                s
                for s in remaining
                if s
                not in (
                    FullConnectStep.APPLY_ROUTES,
                    FullConnectStep.APPLY_DNS_KILL_SWITCH,
                )
            ]
        elif not state.has_if_index_or_iface:
            # Cannot apply dual /1 without adapter identity — still need TUN first.
            plan.reason = "need_tun_if_index_before_routes"

        plan.steps = remaining
        plan.reason = plan.reason or "warm_session_residual_attach"
        return plan

    # Cold connect: all critical steps
    plan.steps = remaining
    plan.reason = "cold_full_connect"
    return plan


def flyclient_reuse_tunnel_plan(
    existing: FullTunnelPlan | None, vpn_ip: str
) -> FullTunnelPlan:
    """Reuse existing full-tunnel plan when VPN IP matches (skip rebuild)."""
    ip = (vpn_ip or "").strip()
    if (
        existing is not None
        and existing.tunnel_client_ip == ip
        and existing.is_full_tunnel()
        and not assert_full_tunnel_plan(existing)
    ):
        return existing
    return build_full_tunnel_plan(ip)


def flyclient_ordered_steps(steps: Sequence[FullConnectStep]) -> list[FullConnectStep]:
    """Stable order matching FULL_CONNECT_CRITICAL_PATH (drop unknowns)."""
    order = {s: i for i, s in enumerate(FULL_CONNECT_CRITICAL_PATH)}
    known = [s for s in steps if s in order]
    return sorted(known, key=lambda s: order[s])


def flyclient_critical_path_names() -> list[str]:
    return [s.value for s in FULL_CONNECT_CRITICAL_PATH]
