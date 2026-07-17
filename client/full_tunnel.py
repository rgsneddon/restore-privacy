"""Full-tunnel (all-traffic) VPN setup helpers — not split-only.

These pure builders encode the product intent: once the RPT session is up,
route **all** user traffic into the tunnel interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FullTunnelPlan:
    """Platform-agnostic full VPN plan."""

    tunnel_iface: str
    tunnel_client_ip: str
    tunnel_prefix: int = 32
    tunnel_gateway: str = "10.88.0.1"
    dns_servers: list[str] = field(default_factory=lambda: ["1.1.1.1", "9.9.9.9"])
    # Catch-all routes (full tunnel)
    default_routes: list[str] = field(
        default_factory=lambda: ["0.0.0.0/1", "128.0.0.0/1"]
    )
    # Android VpnService: empty allowed apps => all apps
    allow_all_apps: bool = True
    disallowed_apps: list[str] = field(default_factory=list)
    mtu: int = 1280
    session_name: str = "Restore Privacy"

    def is_full_tunnel(self) -> bool:
        return (
            self.allow_all_apps
            and not self.disallowed_apps
            and "0.0.0.0/1" in self.default_routes
            and "128.0.0.0/1" in self.default_routes
        )


def build_full_tunnel_plan(
    client_vpn_ip: str,
    tunnel_iface: str = "rpt0",
    gateway: str = "10.88.0.1",
) -> FullTunnelPlan:
    return FullTunnelPlan(
        tunnel_iface=tunnel_iface,
        tunnel_client_ip=client_vpn_ip,
        tunnel_gateway=gateway,
        allow_all_apps=True,
        disallowed_apps=[],
        default_routes=["0.0.0.0/1", "128.0.0.0/1"],
    )


def windows_route_commands(plan: FullTunnelPlan, server_host: str) -> list[str]:
    """netsh/route commands for full tunnel on Windows (requires admin).

    Splits default into /1+/1 so the tunnel wins without deleting the physical default;
    also pins the VPN server host via physical gateway (caller substitutes GW).
    """
    cmds = [
        f'netsh interface ip set address name="{plan.tunnel_iface}" static {plan.tunnel_client_ip} 255.255.255.255',
        # Full-tunnel dual /1 routes via tunnel gateway
        f"route add 0.0.0.0 mask 128.0.0.0 {plan.tunnel_gateway} metric 5",
        f"route add 128.0.0.0 mask 128.0.0.0 {plan.tunnel_gateway} metric 5",
        # Keep path to VPN server on physical interface (placeholder PHYSICAL_GW)
        f"route add {server_host} mask 255.255.255.255 PHYSICAL_GW metric 1",
    ]
    for dns in plan.dns_servers:
        cmds.append(
            f'netsh interface ip set dns name="{plan.tunnel_iface}" static {dns} validate=no'
        )
    return cmds


def android_vpn_builder_config(plan: FullTunnelPlan) -> dict[str, Any]:
    """Config dict consumed by Android VpnService.Builder (full tunnel)."""
    return {
        "session": plan.session_name,
        "mtu": plan.mtu,
        "addresses": [{"addr": plan.tunnel_client_ip, "prefix": 32}],
        "routes": [{"addr": "0.0.0.0", "prefix": 0}],  # all traffic
        "dns": list(plan.dns_servers),
        "allowAllApps": plan.allow_all_apps,
        "disallowedApplications": list(plan.disallowed_apps),
        "blocking": True,
    }


def assert_full_tunnel_plan(plan: FullTunnelPlan) -> list[str]:
    violations: list[str] = []
    if not plan.is_full_tunnel():
        violations.append("plan is not full-tunnel")
    if not plan.allow_all_apps:
        violations.append("allow_all_apps must be True")
    cfg = android_vpn_builder_config(plan)
    if cfg.get("routes") != [{"addr": "0.0.0.0", "prefix": 0}]:
        violations.append("android routes must be 0.0.0.0/0")
    cmds = "\n".join(windows_route_commands(plan, "1.2.3.4"))
    if "0.0.0.0 mask 128.0.0.0" not in cmds:
        violations.append("windows routes missing full-tunnel /1")
    return violations
