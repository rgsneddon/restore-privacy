"""Residual dual-stack (IPv4 / IPv6) Settings prefs → tunnel policy.

Purpose
-------
- **IPv4 always ON** (product policy, not user-adjustable): residual full-tunnel
  capture always uses dual /1 IPv4 routes into the product TUN so ISP IPv4 is
  not the residual egress path. Legacy ``residual_ipv4=false`` prefs are ignored.
- **IPv6 ON** (default, adjustable): while residual is up, block ISP IPv6 egress
  (``ipv6_leak_policy=block_isp`` — Windows adapter binding / Linux blackhole /
  Android ``::/0``).
- **IPv6 OFF**: do not apply IPv6 ISP block; honesty must not claim IPv6 protected.

Missing durable keys: IPv4 residual always ON; IPv6 residual defaults ON.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from client.full_tunnel import (
    DEFAULT_IPV6_LEAK_POLICY,
    FullTunnelPlan,
    IPV6_LEAK_POLICY_BLOCK_ISP,
    build_full_tunnel_plan,
)

# Durable settings keys (Flutter SharedPreferences / Windows+Linux settings.json)
KEY_RESIDUAL_IPV4 = "residual_ipv4"
KEY_RESIDUAL_IPV6 = "residual_ipv6"

# Plan policy when user turns IPv6 residual protection off
IPV6_LEAK_POLICY_ALLOW_ISP = "allow_isp"


@dataclass(frozen=True)
class ResidualStackPrefs:
    """Residual stack intent. IPv4 is product-forced ON; IPv6 is user-adjustable."""

    ipv4_enabled: bool = True
    ipv6_enabled: bool = True

    def __post_init__(self) -> None:
        # Product policy: residual IPv4 capture is never off.
        if not self.ipv4_enabled:
            object.__setattr__(self, "ipv4_enabled", True)


def _missing_defaults_true(data: Mapping[str, Any], key: str) -> bool:
    """Product default ON when key absent; explicit false stays false (IPv6 only)."""
    if key not in data:
        return True
    return bool(data[key])


def residual_stack_from_mapping(data: Optional[Mapping[str, Any]]) -> ResidualStackPrefs:
    """Parse durable prefs map; residual IPv4 always ON; missing IPv6 → ON."""
    if not data:
        return ResidualStackPrefs()
    return ResidualStackPrefs(
        # Legacy residual_ipv4=false is ignored (always ON).
        ipv4_enabled=True,
        ipv6_enabled=_missing_defaults_true(data, KEY_RESIDUAL_IPV6),
    )


def residual_stack_from_product_settings(settings: Any) -> ResidualStackPrefs:
    """Read residual stack from ProductSettings-like object; IPv4 always ON."""
    if settings is None:
        return ResidualStackPrefs()
    # Prefer explicit attributes; IPv4 forced ON regardless of stored false.
    if hasattr(settings, "residual_ipv4") or hasattr(settings, "residual_ipv6"):
        v6 = getattr(settings, "residual_ipv6", True)
        return ResidualStackPrefs(ipv4_enabled=True, ipv6_enabled=bool(v6))
    # Flutter-style camelCase if ever passed through
    if hasattr(settings, "residualIpv4") or hasattr(settings, "residualIpv6"):
        return ResidualStackPrefs(
            ipv4_enabled=True,
            ipv6_enabled=bool(getattr(settings, "residualIpv6", True)),
        )
    return ResidualStackPrefs()


def apply_residual_stack_to_plan(
    plan: FullTunnelPlan, stack: ResidualStackPrefs
) -> FullTunnelPlan:
    """Return a copy of *plan* with IPv4 residual routes always + IPv6 from *stack*."""
    # Product policy: always apply residual IPv4 catch-all dual /1.
    routes = list(plan.default_routes) if plan.default_routes else []
    if not routes or "0.0.0.0/1" not in routes:
        routes = ["0.0.0.0/1", "128.0.0.0/1"]
    v6_policy = (
        IPV6_LEAK_POLICY_BLOCK_ISP
        if stack.ipv6_enabled
        else IPV6_LEAK_POLICY_ALLOW_ISP
    )
    return FullTunnelPlan(
        tunnel_iface=plan.tunnel_iface,
        tunnel_client_ip=plan.tunnel_client_ip,
        tunnel_prefix=plan.tunnel_prefix,
        tunnel_gateway=plan.tunnel_gateway,
        dns_servers=list(plan.dns_servers),
        default_routes=routes,
        allow_all_apps=plan.allow_all_apps,
        disallowed_apps=list(plan.disallowed_apps),
        mtu=plan.mtu,
        session_name=plan.session_name,
        ipv6_leak_policy=v6_policy,
    )


def build_full_tunnel_plan_for_stack(
    client_vpn_ip: str,
    *,
    stack: ResidualStackPrefs | None = None,
    tunnel_iface: str = "RPT",
    gateway: str | None = None,
    dns_servers: list[str] | None = None,
) -> FullTunnelPlan:
    """Build residual plan honouring dual-stack Settings prefs."""
    from client.full_tunnel import DEFAULT_TUNNEL_GATEWAY

    base = build_full_tunnel_plan(
        client_vpn_ip,
        tunnel_iface=tunnel_iface,
        gateway=gateway if gateway is not None else DEFAULT_TUNNEL_GATEWAY,
        dns_servers=dns_servers,
    )
    return apply_residual_stack_to_plan(base, stack or ResidualStackPrefs())


def honesty_ipv6_protected(
    *,
    stack_ipv6_enabled: bool,
    mitigation_applied: bool,
) -> bool | None:
    """Honesty flag for Connected copy.

    - IPv6 Settings OFF → False (never claim protected)
    - Settings ON + mitigation ok → True
    - Settings ON + mitigation failed → False
    """
    if not stack_ipv6_enabled:
        return False
    return bool(mitigation_applied)


def plan_wants_ipv6_isp_block(plan: FullTunnelPlan | None) -> bool:
    """True when residual plan should install IPv6 ISP-leak mitigation."""
    if plan is None:
        return True  # legacy callers without plan keep product default
    return str(getattr(plan, "ipv6_leak_policy", DEFAULT_IPV6_LEAK_POLICY)) == (
        IPV6_LEAK_POLICY_BLOCK_ISP
    )


class ResidualAttachOutcome:
    """Shipped attach decision for residual Connect (single source of truth).

    - ``RESIDUAL_OK``: dual /1 intended + capture active → residual_capture=True
    - ``SESSION_ONLY_OK``: Settings residual IPv4 OFF + dataplane up → keep session,
      residual_capture=False (no teardown)
    - ``FAIL``: residual IPv4 ON but capture incomplete, or session not up → teardown
    """

    RESIDUAL_OK = "residual_ok"
    SESSION_ONLY_OK = "session_only_ok"
    FAIL = "fail"


def residual_attach_outcome(
    *,
    ok: bool,
    routes_applied: bool,
    system_capture: bool,
    has_dataplane: bool,
    plan: FullTunnelPlan | None,
) -> str:
    """Pure residual attach decision used by Windows ``start_full_tunnel`` and honesty.

    Call sites must not re-implement this table. Settings residual_ipv4 OFF
    (empty dual /1 on *plan*) with a live dataplane is ``SESSION_ONLY_OK`` —
    never ``FAIL`` (do not tear down).
    """
    from client.full_tunnel import plan_wants_ipv4_catchall

    if not ok or not has_dataplane:
        return ResidualAttachOutcome.FAIL

    wants_ipv4 = plan is None or plan_wants_ipv4_catchall(plan)

    if not wants_ipv4:
        # Settings residual IPv4 OFF: session/dataplane success without dual /1
        return ResidualAttachOutcome.SESSION_ONLY_OK

    # Residual IPv4 ON: require system capture + dual /1 applied
    if routes_applied and system_capture:
        return ResidualAttachOutcome.RESIDUAL_OK
    return ResidualAttachOutcome.FAIL


def residual_ip_capture_from_fields(
    *,
    ok: bool,
    routes_applied: bool,
    system_capture: bool,
    has_dataplane: bool,
    plan: FullTunnelPlan | None,
) -> bool:
    """Pure residual-capture honesty gate (Windows/Linux ``residual_ip_capture_active``).

    True only for :attr:`ResidualAttachOutcome.RESIDUAL_OK`.
    """
    return (
        residual_attach_outcome(
            ok=ok,
            routes_applied=routes_applied,
            system_capture=system_capture,
            has_dataplane=has_dataplane,
            plan=plan,
        )
        == ResidualAttachOutcome.RESIDUAL_OK
    )


def session_only_from_fields(
    *,
    ok: bool,
    has_dataplane: bool,
    plan: FullTunnelPlan | None,
) -> bool:
    """True when session/dataplane is up with Settings residual IPv4 intentionally OFF."""
    return (
        residual_attach_outcome(
            ok=ok,
            routes_applied=False,  # unused for SESSION_ONLY_OK path
            system_capture=False,
            has_dataplane=has_dataplane,
            plan=plan,
        )
        == ResidualAttachOutcome.SESSION_ONLY_OK
    )
