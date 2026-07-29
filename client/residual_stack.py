"""Residual dual-stack (IPv4 / IPv6) Settings prefs → tunnel policy.

Purpose
-------
- **IPv4 ON** (default): residual full-tunnel capture uses dual /1 IPv4 routes
  into the product TUN so ISP IPv4 is not the residual egress path.
- **IPv4 OFF**: omit IPv4 catch-all residual routes (no full IPv4 residual claim).
- **IPv6 ON** (default): while residual is up, block ISP IPv6 egress
  (``ipv6_leak_policy=block_isp`` — Windows adapter binding / Linux blackhole /
  Android ``::/0``).
- **IPv6 OFF**: do not apply IPv6 ISP block; honesty must not claim IPv6 protected.

Missing durable keys default **both ON** (product dual-stack residual).
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
    """User dual-stack residual intent (Settings switches)."""

    ipv4_enabled: bool = True
    ipv6_enabled: bool = True


def _missing_defaults_true(data: Mapping[str, Any], key: str) -> bool:
    """Product default ON when key absent; explicit false stays false."""
    if key not in data:
        return True
    return bool(data[key])


def residual_stack_from_mapping(data: Optional[Mapping[str, Any]]) -> ResidualStackPrefs:
    """Parse durable prefs map; missing keys → both ON."""
    if not data:
        return ResidualStackPrefs()
    return ResidualStackPrefs(
        ipv4_enabled=_missing_defaults_true(data, KEY_RESIDUAL_IPV4),
        ipv6_enabled=_missing_defaults_true(data, KEY_RESIDUAL_IPV6),
    )


def residual_stack_from_product_settings(settings: Any) -> ResidualStackPrefs:
    """Read residual_ipv4 / residual_ipv6 attrs from ProductSettings-like object."""
    if settings is None:
        return ResidualStackPrefs()
    # Prefer explicit attributes; fall back to both ON
    if hasattr(settings, "residual_ipv4") or hasattr(settings, "residual_ipv6"):
        v4 = getattr(settings, "residual_ipv4", True)
        v6 = getattr(settings, "residual_ipv6", True)
        return ResidualStackPrefs(ipv4_enabled=bool(v4), ipv6_enabled=bool(v6))
    # Flutter-style camelCase if ever passed through
    if hasattr(settings, "residualIpv4") or hasattr(settings, "residualIpv6"):
        return ResidualStackPrefs(
            ipv4_enabled=bool(getattr(settings, "residualIpv4", True)),
            ipv6_enabled=bool(getattr(settings, "residualIpv6", True)),
        )
    return ResidualStackPrefs()


def apply_residual_stack_to_plan(
    plan: FullTunnelPlan, stack: ResidualStackPrefs
) -> FullTunnelPlan:
    """Return a copy of *plan* with routes / IPv6 leak policy from *stack*."""
    routes = (
        list(plan.default_routes)
        if stack.ipv4_enabled
        else []
    )
    if stack.ipv4_enabled and not routes:
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


def residual_ip_capture_from_fields(
    *,
    ok: bool,
    routes_applied: bool,
    system_capture: bool,
    has_dataplane: bool,
    plan: FullTunnelPlan | None,
) -> bool:
    """Pure residual-capture honesty gate (Windows/Linux ``residual_ip_capture_active``).

    True only when dual /1 residual IPv4 capture is intended (Settings residual_ipv4
    ON → plan.default_routes carry dual /1) **and** routes/system TUN/dataplane
    report success. Pin-only or Settings IPv4 OFF → False (session-only honesty).
    """
    from client.full_tunnel import plan_wants_ipv4_catchall

    if not (ok and routes_applied and system_capture and has_dataplane):
        return False
    if plan is not None and not plan_wants_ipv4_catchall(plan):
        return False
    return True


def session_only_from_fields(
    *,
    ok: bool,
    has_dataplane: bool,
    plan: FullTunnelPlan | None,
) -> bool:
    """True when session/dataplane is up with Settings residual IPv4 intentionally OFF."""
    from client.full_tunnel import plan_wants_ipv4_catchall

    if not ok or not has_dataplane or plan is None:
        return False
    return not plan_wants_ipv4_catchall(plan)
