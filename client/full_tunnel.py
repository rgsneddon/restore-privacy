"""Full-tunnel (all-traffic) VPN setup helpers — not split-only.

Windows anti-blackhole rules (Wintun):
- Dual /1 catch-alls MUST use ``0.0.0.0 IF <if_index>`` (on-link to the adapter).
- NEVER use next-hop ``10.88.0.1`` on the client — nothing answers ARP on Wintun,
  so Windows blackholes all internet while the session still looks "Connected".
- Pin the VPN server host on the physical gateway BEFORE dual /1 routes.
- If ``if_index`` is unknown, do not emit dual /1 at all (caller must refuse).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# Tunnel address plan (must match node/routing.py DEFAULT_TUNNEL_ADDR / CLIENT_NET).
DEFAULT_TUNNEL_GATEWAY = "10.88.0.1"
# Product full-tunnel DNS: node-local recursive resolver on the tunnel gateway.
# Not Cloudflare/Quad9 — queries stay on the operator node when full tunnel is up.
# Requires Unbound (or equivalent) on the node; see node/install_dns.sh.
DEFAULT_TUNNEL_DNS_SERVERS: tuple[str, ...] = (DEFAULT_TUNNEL_GATEWAY,)


def default_tunnel_dns_servers() -> list[str]:
    """Shipped product DNS list for full-tunnel plans (copy, not shared mutable)."""
    return list(DEFAULT_TUNNEL_DNS_SERVERS)


# Product residual full tunnel must address IPv6 ISP leaks (IPv4 dual /1 alone is not enough).
IPV6_LEAK_POLICY_BLOCK_ISP = "block_isp"
DEFAULT_IPV6_LEAK_POLICY = IPV6_LEAK_POLICY_BLOCK_ISP


@dataclass
class FullTunnelPlan:
    """Platform-agnostic full VPN plan."""

    tunnel_iface: str
    tunnel_client_ip: str
    tunnel_prefix: int = 32
    tunnel_gateway: str = DEFAULT_TUNNEL_GATEWAY
    dns_servers: list[str] = field(default_factory=default_tunnel_dns_servers)
    default_routes: list[str] = field(
        default_factory=lambda: ["0.0.0.0/1", "128.0.0.0/1"]
    )
    allow_all_apps: bool = True
    disallowed_apps: list[str] = field(default_factory=list)
    mtu: int = 1280
    session_name: str = "Restore Privacy"
    # When residual IPv4 capture is up, also block ISP IPv6 egress (privacy).
    ipv6_leak_policy: str = DEFAULT_IPV6_LEAK_POLICY

    def is_full_tunnel(self) -> bool:
        return (
            self.allow_all_apps
            and not self.disallowed_apps
            and "0.0.0.0/1" in self.default_routes
            and "128.0.0.0/1" in self.default_routes
        )


def build_full_tunnel_plan(
    client_vpn_ip: str,
    tunnel_iface: str = "RPT",
    gateway: str = DEFAULT_TUNNEL_GATEWAY,
    dns_servers: list[str] | None = None,
) -> FullTunnelPlan:
    return FullTunnelPlan(
        tunnel_iface=tunnel_iface,
        tunnel_client_ip=client_vpn_ip,
        tunnel_gateway=gateway,
        dns_servers=list(dns_servers) if dns_servers is not None else default_tunnel_dns_servers(),
        allow_all_apps=True,
        disallowed_apps=[],
        default_routes=["0.0.0.0/1", "128.0.0.0/1"],
    )


def windows_route_commands(
    plan: FullTunnelPlan,
    server_host: str,
    if_index: Optional[int] = None,
    *,
    include_catchall: bool = True,
) -> list[str]:
    """netsh/route commands for full tunnel on Windows (requires admin).

    When ``if_index`` is missing, only server-pin + address/DNS cmds are emitted
    (no dual /1). Callers must treat missing if_index as "cannot full-tunnel".
    """
    cmds: list[str] = [
        # /32 only — no fake gateway 10.88.0.1 (Wintun cannot ARP that host)
        f'netsh interface ip set address name="{plan.tunnel_iface}" '
        f"static {plan.tunnel_client_ip} 255.255.255.255",
        # Server pin FIRST (physical path) — placeholder PHYSICAL_GW
        f"route add {server_host} mask 255.255.255.255 PHYSICAL_GW metric 1",
    ]

    if include_catchall and if_index is not None and int(if_index) > 0:
        idx = int(if_index)
        # On-link dual /1 into the TUN adapter (WireGuard/Wintun-style)
        cmds.append(f"route add 0.0.0.0 mask 128.0.0.0 0.0.0.0 IF {idx} metric 5")
        cmds.append(f"route add 128.0.0.0 mask 128.0.0.0 0.0.0.0 IF {idx} metric 5")
    # else: intentionally omit catch-alls (prevents ARP blackhole via 10.88.0.1)

    for i, dns in enumerate(plan.dns_servers, start=1):
        if i == 1:
            cmds.append(
                f'netsh interface ip set dns name="{plan.tunnel_iface}" '
                f"static {dns} validate=no"
            )
        else:
            cmds.append(
                f'netsh interface ip add dns name="{plan.tunnel_iface}" '
                f"addr={dns} index={i} validate=no"
            )
    return cmds


def windows_route_delete_commands(
    plan: FullTunnelPlan,
    server_host: str,
    if_index: Optional[int] = None,
) -> list[str]:
    """Commands to tear down full-tunnel routes (rollback on failure)."""
    cmds = [
        f"route delete {server_host} mask 255.255.255.255",
        "route delete 0.0.0.0 mask 128.0.0.0",
        "route delete 128.0.0.0 mask 128.0.0.0",
    ]
    return cmds


def linux_route_commands(
    plan: FullTunnelPlan,
    server_host: str,
    *,
    iface: Optional[str] = None,
    physical_dev: str = "PHYSICAL_DEV",
    physical_gw: str = "PHYSICAL_GW",
    include_catchall: bool = True,
) -> list[str]:
    """``ip`` commands for full tunnel on Linux (Ubuntu / Mint; needs root).

    Order: assign TUN address, pin VPN server on the physical path, then dual
    ``/1`` catch-alls into the TUN so residual public IP can use the node.
    Without ``include_catchall``, only address + server pin (no residual capture).

    When ``physical_gw`` is empty or ``ONLINK``, pin uses ``dev`` only (on-link
    default route style seen on some Ubuntu setups).
    """
    tun = (iface or plan.tunnel_iface or "rpt0").strip() or "rpt0"
    ip = plan.tunnel_client_ip
    cmds: list[str] = [
        f"ip link set dev {tun} up",
        f"ip addr replace {ip}/32 dev {tun}",
    ]
    gw = (physical_gw or "").strip()
    if not gw or gw.upper() == "ONLINK" or gw == "PHYSICAL_GW":
        if gw == "PHYSICAL_GW":
            # Placeholder kept for dry-run / tests that substitute later
            cmds.append(
                f"ip route replace {server_host}/32 via {physical_gw} dev {physical_dev}"
            )
        else:
            # On-link pin (no next-hop)
            cmds.append(f"ip route replace {server_host}/32 dev {physical_dev}")
    else:
        cmds.append(
            f"ip route replace {server_host}/32 via {gw} dev {physical_dev}"
        )
    if include_catchall:
        cmds.append(f"ip route replace 0.0.0.0/1 dev {tun}")
        cmds.append(f"ip route replace 128.0.0.0/1 dev {tun}")
    # Point interface DNS at the node tunnel resolver (default 10.88.0.1)
    if plan.dns_servers:
        dns_args = " ".join(plan.dns_servers)
        cmds.append(f"resolvectl dns {tun} {dns_args}")
        cmds.append(f"resolvectl domain {tun} '~.'")
    return cmds


def linux_route_delete_commands(
    plan: FullTunnelPlan,
    server_host: str,
    *,
    iface: Optional[str] = None,
) -> list[str]:
    """Commands to tear down Linux full-tunnel routes and TUN addressing."""
    tun = (iface or plan.tunnel_iface or "rpt0").strip() or "rpt0"
    return [
        f"ip route del 0.0.0.0/1 dev {tun}",
        f"ip route del 128.0.0.0/1 dev {tun}",
        f"ip route del {server_host}/32",
        f"resolvectl revert {tun}",
        f"ip link set dev {tun} down",
    ]


def routes_would_blackhole_without_system_capture(
    system_capture: bool,
    apply_default_routes: bool,
) -> bool:
    """True if applying full-tunnel defaults without a working OS TUN is a blackhole."""
    return apply_default_routes and not system_capture


def routes_would_blackhole_without_if_index(
    if_index: Optional[int],
    apply_default_routes: bool,
) -> bool:
    """True if dual /1 would be applied without a Wintun IF index (unsafe)."""
    return apply_default_routes and (if_index is None or int(if_index) <= 0)


# Marker emitted by the critical PowerShell IPv6-disable step (parsed by apply path).
RPT_IPV6_DISABLED_PREFIX = "RPT_IPV6_DISABLED="


def windows_ipv6_disable_powershell(*, tunnel_iface: str = "RPT") -> str:
    """Critical PowerShell: disable ms_tcpip6 on non-tunnel adapters and verify.

    - Does **not** use ``-ErrorAction SilentlyContinue`` on Disable-NetAdapterBinding
      (that would exit 0 with zero effect).
    - Prints ``RPT_IPV6_DISABLED=<n>`` where n is adapters verified disabled.
    - Exits **1** when n==0 (no adapter protected) so callers cannot claim success.
    """
    tun = (tunnel_iface or "RPT").replace("'", "''")
    # Keep as one -Command string; single-quoted PS blocks avoid shell expansion.
    return (
        "powershell -NoProfile -ExecutionPolicy Bypass -Command \""
        f"$tun='{tun}'; "
        "$disabled=0; "
        "$adapters=@(Get-NetAdapter -ErrorAction Stop | "
        "Where-Object { $_.Status -eq 'Up' -and $_.Name -ne $tun }); "
        "foreach ($a in $adapters) { "
        "  try { "
        "    Disable-NetAdapterBinding -Name $a.Name -ComponentID ms_tcpip6 "
        "      -Confirm:$false -ErrorAction Stop; "
        "    $b=Get-NetAdapterBinding -Name $a.Name -ComponentID ms_tcpip6 "
        "      -ErrorAction Stop; "
        "    if (-not $b.Enabled) { $disabled++ } "
        "  } catch { } "
        "}; "
        f"Write-Output ('{RPT_IPV6_DISABLED_PREFIX}' + $disabled); "
        "if ($disabled -lt 1) { exit 1 } else { exit 0 }"
        "\""
    )


def parse_windows_ipv6_disable_result(
    returncode: int,
    stdout: str,
    stderr: str = "",
) -> tuple[bool, int]:
    """Interpret critical PS IPv6-disable process result.

    Returns ``(mitigation_ok, disabled_count)``.
    ``mitigation_ok`` is True only when exit code is 0 **and**
    ``RPT_IPV6_DISABLED`` reports a positive count (zero-effect cannot pass).
    """
    _ = stderr
    text = stdout or ""
    count = 0
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(RPT_IPV6_DISABLED_PREFIX):
            try:
                count = int(line[len(RPT_IPV6_DISABLED_PREFIX) :].strip())
            except ValueError:
                count = 0
            break
    ok = (returncode == 0) and (count >= 1)
    return ok, count


def windows_ipv6_leak_block_commands(*, tunnel_iface: str = "RPT") -> list[str]:
    """Commands to stop residual IPv6 using the ISP while full tunnel is up.

    Transition tech is best-effort; the last command is the **critical** verified
    Disable-NetAdapterBinding step (see ``windows_ipv6_disable_powershell``).
    """
    return [
        "netsh interface teredo set state disabled",
        "netsh interface 6to4 set state state=disabled",
        "netsh interface isatap set state disabled",
        windows_ipv6_disable_powershell(tunnel_iface=tunnel_iface),
    ]


def windows_ipv6_leak_rollback_commands(*, tunnel_iface: str = "RPT") -> list[str]:
    """Restore IPv6 bindings after product Disconnect (best-effort, all adapters)."""
    _ = tunnel_iface  # reserved for future per-adapter snapshots
    ps = (
        "Get-NetAdapter -ErrorAction SilentlyContinue | "
        "ForEach-Object { "
        "Enable-NetAdapterBinding -Name $_.Name -ComponentID ms_tcpip6 "
        "-Confirm:$false -ErrorAction SilentlyContinue "
        "}"
    )
    return [
        f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{ps}"',
        "netsh interface teredo set state default",
        "netsh interface 6to4 set state state=default",
        "netsh interface isatap set state default",
    ]


def linux_ipv6_leak_block_commands(*, iface: str = "rpt0") -> list[str]:
    """Blackhole default IPv6 so residual IPv6 does not use the ISP path.

    Does not permanently disable host IPv6 via sysctl (restored by delete).
    """
    _ = iface
    return [
        "ip -6 route replace blackhole default metric 1",
        "ip -6 route replace blackhole default proto static metric 1 table main",
    ]


def linux_ipv6_leak_rollback_commands(*, iface: str = "rpt0") -> list[str]:
    """Remove IPv6 blackhole defaults installed for the session."""
    _ = iface
    return [
        "ip -6 route del blackhole default metric 1",
        "ip -6 route del blackhole default table main",
        "ip -6 route del blackhole default",
    ]


def android_vpn_builder_config(plan: FullTunnelPlan) -> dict[str, Any]:
    """Config dict consumed by Android VpnService.Builder (full tunnel)."""
    # IPv6 ::/0 into the VPN so residual IPv6 is not left on the ISP (may blackhole
    # until the node carries IPv6 — privacy preference over silent leak).
    routes: list[dict[str, Any]] = [{"addr": "0.0.0.0", "prefix": 0}]
    if plan.ipv6_leak_policy == IPV6_LEAK_POLICY_BLOCK_ISP:
        routes.append({"addr": "::", "prefix": 0})
    return {
        "session": plan.session_name,
        "mtu": plan.mtu,
        "addresses": [{"addr": plan.tunnel_client_ip, "prefix": 32}],
        "routes": routes,
        "dns": list(plan.dns_servers),
        "allowAllApps": plan.allow_all_apps,
        "disallowedApplications": list(plan.disallowed_apps),
        "blocking": True,
        "protectNodeSocket": True,
        "ipv6LeakPolicy": plan.ipv6_leak_policy,
        "ipv6Protected": plan.ipv6_leak_policy == IPV6_LEAK_POLICY_BLOCK_ISP,
    }


def assert_full_tunnel_plan(plan: FullTunnelPlan) -> list[str]:
    violations: list[str] = []
    if not plan.is_full_tunnel():
        violations.append("plan is not full-tunnel")
    if not plan.allow_all_apps:
        violations.append("allow_all_apps must be True")
    cfg = android_vpn_builder_config(plan)
    routes = cfg.get("routes") or []
    if {"addr": "0.0.0.0", "prefix": 0} not in routes:
        violations.append("android routes must include 0.0.0.0/0")
    if plan.ipv6_leak_policy == IPV6_LEAK_POLICY_BLOCK_ISP:
        if {"addr": "::", "prefix": 0} not in routes:
            violations.append("android routes must include ::/0 for IPv6 leak policy")
    cmds = "\n".join(windows_route_commands(plan, "1.2.3.4", if_index=12))
    if "0.0.0.0 mask 128.0.0.0 0.0.0.0 IF 12" not in cmds:
        violations.append("windows routes must be on-link IF-bound dual /1")
    if "10.88.0.1" in cmds and "mask 128.0.0.0 10.88.0.1" in cmds:
        violations.append("windows must not use ARP gateway 10.88.0.1 for dual /1")
    if "PHYSICAL_GW" not in cmds and "1.2.3.4" not in cmds:
        violations.append("server host pin missing")
    pin_i = cmds.find("1.2.3.4")
    catch_i = cmds.find("0.0.0.0 mask 128.0.0.0")
    if pin_i < 0 or catch_i < 0 or pin_i > catch_i:
        violations.append("server pin must be ordered before dual /1 catch-all routes")
    # Without if_index, no catch-all
    no_if = "\n".join(windows_route_commands(plan, "1.2.3.4", if_index=None))
    if "mask 128.0.0.0" in no_if:
        violations.append("without if_index must not emit dual /1 catch-alls")
    # Linux dual /1 into TUN + server pin before catch-alls
    lcmds = "\n".join(
        linux_route_commands(
            plan, "1.2.3.4", iface="rpt0", physical_dev="eth0", physical_gw="192.168.1.1"
        )
    )
    if "0.0.0.0/1 dev rpt0" not in lcmds or "128.0.0.0/1 dev rpt0" not in lcmds:
        violations.append("linux routes must include dual /1 into TUN")
    if "1.2.3.4/32" not in lcmds:
        violations.append("linux server pin missing")
    lpin = lcmds.find("1.2.3.4/32")
    lcatch = lcmds.find("0.0.0.0/1")
    if lpin < 0 or lcatch < 0 or lpin > lcatch:
        violations.append("linux server pin must be ordered before dual /1")
    no_catch = "\n".join(
        linux_route_commands(plan, "1.2.3.4", include_catchall=False)
    )
    if "0.0.0.0/1" in no_catch:
        violations.append("linux without include_catchall must not emit dual /1")
    return violations
