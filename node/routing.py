"""IP forwarding and NAT/masquerade builders for the RPT relay."""

from __future__ import annotations

from typing import Any

DEFAULT_TUNNEL_IFACE = "rpt0"
DEFAULT_TUNNEL_ADDR = "10.88.0.1"
DEFAULT_TUNNEL_PREFIX = 24
DEFAULT_CLIENT_NET = "10.88.0.0/24"


def build_sysctl_forward_commands() -> list[str]:
    return [
        "sysctl -w net.ipv4.ip_forward=1",
        "sysctl -w net.ipv6.conf.all.forwarding=1",
        # Loose reverse-path filter so client→WAN replies via NAT work on TUN
        "sysctl -w net.ipv4.conf.all.rp_filter=2",
        "sysctl -w net.ipv4.conf.default.rp_filter=2",
    ]


def detect_wan_iface_command() -> str:
    return (
        "ip -4 route show default | awk '{for(i=1;i<=NF;i++) if($i==\"dev\"){print $(i+1); exit}}'"
    )


def build_nat_masquerade_commands(
    tunnel_iface: str = DEFAULT_TUNNEL_IFACE,
    wan_iface: str | None = None,
    client_net: str = DEFAULT_CLIENT_NET,
) -> list[str]:
    wan = wan_iface if wan_iface else "$WAN"
    return [
        f"sysctl -w net.ipv4.conf.{tunnel_iface}.rp_filter=2 2>/dev/null || true",
        f"iptables -t nat -C POSTROUTING -s {client_net} -o {wan} -j MASQUERADE 2>/dev/null "
        f"|| iptables -t nat -A POSTROUTING -s {client_net} -o {wan} -j MASQUERADE",
        # Also MASQUERADE any client-net egress not out the tunnel (covers multi-WAN)
        f"iptables -t nat -C POSTROUTING -s {client_net} ! -o {tunnel_iface} -j MASQUERADE 2>/dev/null "
        f"|| iptables -t nat -A POSTROUTING -s {client_net} ! -o {tunnel_iface} -j MASQUERADE",
        f"iptables -C FORWARD -i {tunnel_iface} -o {wan} -j ACCEPT 2>/dev/null "
        f"|| iptables -I FORWARD 1 -i {tunnel_iface} -o {wan} -j ACCEPT",
        f"iptables -C FORWARD -i {wan} -o {tunnel_iface} -m state --state RELATED,ESTABLISHED "
        f"-j ACCEPT 2>/dev/null "
        f"|| iptables -I FORWARD 1 -i {wan} -o {tunnel_iface} -m state --state RELATED,ESTABLISHED "
        f"-j ACCEPT",
        # Accept forward for client net generally (defensive if WAN name changes)
        f"iptables -C FORWARD -s {client_net} -j ACCEPT 2>/dev/null "
        f"|| iptables -I FORWARD 1 -s {client_net} -j ACCEPT",
        f"iptables -C FORWARD -d {client_net} -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null "
        f"|| iptables -I FORWARD 1 -d {client_net} -m state --state RELATED,ESTABLISHED -j ACCEPT",
    ]


def build_tun_setup_commands(
    iface: str = DEFAULT_TUNNEL_IFACE,
    addr: str = DEFAULT_TUNNEL_ADDR,
    prefix: int = DEFAULT_TUNNEL_PREFIX,
) -> list[str]:
    return [
        f"ip link del {iface} 2>/dev/null || true",
        f"ip tuntap add dev {iface} mode tun",
        f"ip addr add {addr}/{prefix} dev {iface}",
        f"ip link set {iface} up",
    ]


def routing_config_block(
    tunnel_iface: str = DEFAULT_TUNNEL_IFACE,
    tunnel_addr: str = DEFAULT_TUNNEL_ADDR,
    tunnel_prefix: int = DEFAULT_TUNNEL_PREFIX,
    client_net: str = DEFAULT_CLIENT_NET,
) -> dict[str, Any]:
    return {
        "enable_ip_forward": True,
        "nat_masquerade": True,
        "tunnel_iface": tunnel_iface,
        "tunnel_addr": tunnel_addr,
        "tunnel_prefix": tunnel_prefix,
        "client_net": client_net,
        "sysctl_forward": build_sysctl_forward_commands(),
        "nat_commands": build_nat_masquerade_commands(tunnel_iface=tunnel_iface, client_net=client_net),
        "tun_setup": build_tun_setup_commands(tunnel_iface, tunnel_addr, tunnel_prefix),
    }


def assert_routing_enabled(config: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    routing = config.get("routing") or {}
    if not routing.get("enable_ip_forward"):
        violations.append("enable_ip_forward must be True")
    if not routing.get("nat_masquerade"):
        violations.append("nat_masquerade must be True")
    nat_cmds = " ".join(routing.get("nat_commands") or [])
    if "MASQUERADE" not in nat_cmds:
        violations.append("nat_commands must include MASQUERADE")
    return violations
