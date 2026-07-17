"""Full-tunnel (all-traffic) VPN setup helpers — not split-only.

These pure builders encode the product intent: once the RPT session is up,
route **all** user traffic into the tunnel interface **without blackholing**
(server host stays on the physical gateway; Windows routes bind to the TUN IF).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


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


def windows_route_commands(
    plan: FullTunnelPlan,
    server_host: str,
    if_index: Optional[int] = None,
) -> list[str]:
    """netsh/route commands for full tunnel on Windows (requires admin).

    Critical anti-blackhole rules:
    1. Pin the VPN **server host** on the physical gateway **before** catch-all
       routes so RPT UDP is not trapped inside the tunnel.
    2. Dual /1 routes must target the **Wintun interface** (IF index) with
       on-link next-hop 0.0.0.0 — NOT a bare ``route … 10.88.0.1`` with no
       on-link path to that gateway (that blackholes all internet traffic).
    3. When ``if_index`` is missing, still emit the safer IF-placeholder form
       only if the caller substitutes; otherwise use gateway + require
       configure_address to put gateway on-link.
    """
    cmds: list[str] = [
        # Address: /24 + gateway so 10.88.0.1 is on-link (Windows needs this)
        f'netsh interface ip set address name="{plan.tunnel_iface}" '
        f"static {plan.tunnel_client_ip} 255.255.255.0 {plan.tunnel_gateway}",
        # Server pin FIRST (physical path) — placeholder PHYSICAL_GW
        f"route add {server_host} mask 255.255.255.255 PHYSICAL_GW metric 1",
    ]

    if if_index is not None and int(if_index) > 0:
        idx = int(if_index)
        # On-link dual /1 into the TUN adapter (WireGuard/Wintun-style)
        cmds.append(f"route add 0.0.0.0 mask 128.0.0.0 0.0.0.0 IF {idx} metric 5")
        cmds.append(f"route add 128.0.0.0 mask 128.0.0.0 0.0.0.0 IF {idx} metric 5")
    else:
        # Fallback: next-hop tunnel gateway (only safe after /24+gw address set)
        cmds.append(
            f"route add 0.0.0.0 mask 128.0.0.0 {plan.tunnel_gateway} metric 5"
        )
        cmds.append(
            f"route add 128.0.0.0 mask 128.0.0.0 {plan.tunnel_gateway} metric 5"
        )

    for dns in plan.dns_servers:
        cmds.append(
            f'netsh interface ip set dns name="{plan.tunnel_iface}" static {dns} validate=no'
        )
    return cmds


def routes_would_blackhole_without_system_capture(
    system_capture: bool,
    apply_default_routes: bool,
) -> bool:
    """True if applying full-tunnel defaults without a working OS TUN is a blackhole."""
    return apply_default_routes and not system_capture


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
        # protect UDP socket + disallowed self package required (node path)
        "protectNodeSocket": True,
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
    cmds = "\n".join(windows_route_commands(plan, "1.2.3.4", if_index=12))
    if "0.0.0.0 mask 128.0.0.0" not in cmds:
        violations.append("windows routes missing full-tunnel /1")
    if "IF 12" not in cmds:
        violations.append("windows full-tunnel routes must bind to interface index")
    if "PHYSICAL_GW" not in cmds and "1.2.3.4" not in cmds:
        violations.append("server host pin missing")
    # Server pin must appear before dual /1 in the command list
    pin_i = cmds.find("1.2.3.4")
    catch_i = cmds.find("0.0.0.0 mask 128.0.0.0")
    if pin_i < 0 or catch_i < 0 or pin_i > catch_i:
        violations.append("server pin must be ordered before dual /1 catch-all routes")
    return violations
