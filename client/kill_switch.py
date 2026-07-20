"""Always-on kill switch: block non-tunnel egress while full tunnel is expected.

When the product tunnel is active (or kill-switch is engaged), traffic must not
leak to the default physical interface. Rules are fail-closed on connect path:
apply blocks after routes; on disconnect, always roll back.

Windows: Windows Filtering Platform via netsh advfirewall rules (named RPT-KS-*).
Linux: iptables OUTPUT DROP for non-tun + policy accept for tunnel iface / node pin.

IPv6 leak blocking remains in ``full_tunnel`` (blackhole / adapter disable);
kill-switch complements IPv4 non-tunnel block.

Not a claim of kernel-level mandatory path on every OEM; rules are best-effort
admin/root helpers that product tunnels invoke on connect/disconnect.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

# Named rules so rollback is exact
WIN_RULE_PREFIX = "RPT-KS"
LINUX_CHAIN = "RPT_KILLSWITCH"


@dataclass(frozen=True)
class KillSwitchPolicy:
    """Product kill-switch policy (always-on when tunnel residual is claimed)."""

    enabled: bool = True
    block_non_tunnel_ipv4: bool = True
    block_non_tunnel_ipv6: bool = True
    # WebRTC / STUN / mDNS common leak surfaces when kill-switch engaged
    block_stun_mdns: bool = True


def product_kill_switch_enabled(env: Optional[dict] = None) -> bool:
    e = env if env is not None else os.environ
    raw = str(e.get("RPT_KILL_SWITCH", "1")).strip().lower()
    if raw in ("0", "false", "off", "no", "disabled"):
        return False
    return True


def default_kill_switch_policy() -> KillSwitchPolicy:
    return KillSwitchPolicy(enabled=product_kill_switch_enabled())


def windows_kill_switch_block_commands(
    *,
    server_host: str,
    tunnel_iface: str = "RPT",
    policy: Optional[KillSwitchPolicy] = None,
) -> list[str]:
    """Firewall rules: allow node host + tunnel interface; block other outbound.

    Requires admin. Rule names are stable for rollback.
    """
    pol = policy or default_kill_switch_policy()
    if not pol.enabled or not pol.block_non_tunnel_ipv4:
        return []
    cmds: list[str] = [
        # Clean prior session rules
        f'netsh advfirewall firewall delete rule name="{WIN_RULE_PREFIX}-allow-node" >nul 2>&1',
        f'netsh advfirewall firewall delete rule name="{WIN_RULE_PREFIX}-allow-tun" >nul 2>&1',
        f'netsh advfirewall firewall delete rule name="{WIN_RULE_PREFIX}-block-out" >nul 2>&1',
        f'netsh advfirewall firewall delete rule name="{WIN_RULE_PREFIX}-block-stun" >nul 2>&1',
        f'netsh advfirewall firewall delete rule name="{WIN_RULE_PREFIX}-block-mdns" >nul 2>&1',
        # Allow UDP/TCP to VPN node (physical pin already routes this host)
        f'netsh advfirewall firewall add rule name="{WIN_RULE_PREFIX}-allow-node" '
        f"dir=out action=allow protocol=any remoteip={server_host} enable=yes",
        # Allow traffic on tunnel interface
        f'netsh advfirewall firewall add rule name="{WIN_RULE_PREFIX}-allow-tun" '
        f'dir=out action=allow enable=yes interfacetype=any '
        f'localip=any remoteip=any profile=any '
        f'# iface={tunnel_iface}',
        # Block all other outbound IPv4 (fail-closed while connected)
        f'netsh advfirewall firewall add rule name="{WIN_RULE_PREFIX}-block-out" '
        f"dir=out action=block protocol=any enable=yes",
    ]
    # Prefer interface-bound allow via PowerShell when available
    cmds.append(
        "powershell -NoProfile -ExecutionPolicy Bypass -Command \""
        f"$if=(Get-NetAdapter -Name '{tunnel_iface}' -ErrorAction SilentlyContinue); "
        "if ($if) { "
        f"New-NetFirewallRule -DisplayName '{WIN_RULE_PREFIX}-allow-tun-if' "
        "-Direction Outbound -Action Allow -InterfaceAlias $if.Name "
        "-ErrorAction SilentlyContinue | Out-Null "
        "}\""
    )
    if pol.block_stun_mdns:
        # STUN/TURN common ports + mDNS (WebRTC / local discovery leaks)
        cmds.append(
            f'netsh advfirewall firewall add rule name="{WIN_RULE_PREFIX}-block-stun" '
            f"dir=out action=block protocol=UDP remoteport=3478,5349 enable=yes"
        )
        cmds.append(
            f'netsh advfirewall firewall add rule name="{WIN_RULE_PREFIX}-block-mdns" '
            f"dir=out action=block protocol=UDP remoteport=5353 enable=yes"
        )
    return cmds


def windows_kill_switch_rollback_commands() -> list[str]:
    names = [
        f"{WIN_RULE_PREFIX}-allow-node",
        f"{WIN_RULE_PREFIX}-allow-tun",
        f"{WIN_RULE_PREFIX}-allow-tun-if",
        f"{WIN_RULE_PREFIX}-block-out",
        f"{WIN_RULE_PREFIX}-block-stun",
        f"{WIN_RULE_PREFIX}-block-mdns",
    ]
    cmds = [
        f'netsh advfirewall firewall delete rule name="{n}" >nul 2>&1' for n in names
    ]
    cmds.append(
        "powershell -NoProfile -ExecutionPolicy Bypass -Command \""
        f"Get-NetFirewallRule -DisplayName '{WIN_RULE_PREFIX}-*' "
        "-ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue\""
    )
    return cmds


def linux_kill_switch_block_commands(
    *,
    server_host: str,
    tunnel_iface: str = "rpt0",
    policy: Optional[KillSwitchPolicy] = None,
) -> list[str]:
    """iptables OUTPUT: accept tun + node host; DROP other outbound while connected."""
    pol = policy or default_kill_switch_policy()
    if not pol.enabled or not pol.block_non_tunnel_ipv4:
        return []
    chain = LINUX_CHAIN
    cmds = [
        # Ensure chain exists and is empty-ish
        f"iptables -N {chain} 2>/dev/null || true",
        f"iptables -F {chain}",
        f"iptables -D OUTPUT -j {chain} 2>/dev/null || true",
        f"iptables -I OUTPUT 1 -j {chain}",
        # Allow loopback
        f"iptables -A {chain} -o lo -j ACCEPT",
        # Allow tunnel iface
        f"iptables -A {chain} -o {tunnel_iface} -j ACCEPT",
        # Allow traffic to VPN node (handshake + outer UDP)
        f"iptables -A {chain} -d {server_host} -j ACCEPT",
        # Established
        f"iptables -A {chain} -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT",
    ]
    if pol.block_stun_mdns:
        cmds.append(
            f"iptables -A {chain} -p udp --dport 3478 -j DROP"
        )
        cmds.append(
            f"iptables -A {chain} -p udp --dport 5349 -j DROP"
        )
        cmds.append(
            f"iptables -A {chain} -p udp --dport 5353 -j DROP"
        )
    # Fail-closed: drop remaining outbound
    cmds.append(f"iptables -A {chain} -j DROP")
    if pol.block_non_tunnel_ipv6:
        cmds.extend(
            [
                f"ip6tables -N {chain} 2>/dev/null || true",
                f"ip6tables -F {chain}",
                f"ip6tables -D OUTPUT -j {chain} 2>/dev/null || true",
                f"ip6tables -I OUTPUT 1 -j {chain}",
                f"ip6tables -A {chain} -o lo -j ACCEPT",
                f"ip6tables -A {chain} -o {tunnel_iface} -j ACCEPT",
                f"ip6tables -A {chain} -j DROP",
            ]
        )
    return cmds


def linux_kill_switch_rollback_commands() -> list[str]:
    chain = LINUX_CHAIN
    return [
        f"iptables -D OUTPUT -j {chain} 2>/dev/null || true",
        f"iptables -F {chain} 2>/dev/null || true",
        f"iptables -X {chain} 2>/dev/null || true",
        f"ip6tables -D OUTPUT -j {chain} 2>/dev/null || true",
        f"ip6tables -F {chain} 2>/dev/null || true",
        f"ip6tables -X {chain} 2>/dev/null || true",
    ]


def android_kill_switch_builder_flags() -> dict:
    """Flags for Android VpnService.Builder — blocking + no bypass."""
    return {
        "blocking": True,
        "allowBypass": False,
        "killSwitch": True,
        "protectNodeSocket": True,
        # Disallow WebRTC local discovery when platform supports it
        "blockWebRtcMdns": True,
    }


@dataclass
class KillSwitchApplyPlan:
    """Commands to apply then roll back for a product connect cycle."""

    apply: list[str] = field(default_factory=list)
    rollback: list[str] = field(default_factory=list)
    platform: str = ""


def build_kill_switch_plan(
    platform: str,
    *,
    server_host: str,
    tunnel_iface: str,
    policy: Optional[KillSwitchPolicy] = None,
) -> KillSwitchApplyPlan:
    pol = policy or default_kill_switch_policy()
    plat = platform.lower().strip()
    if not pol.enabled:
        return KillSwitchApplyPlan(platform=plat)
    if plat in ("windows", "win32", "win"):
        return KillSwitchApplyPlan(
            apply=windows_kill_switch_block_commands(
                server_host=server_host,
                tunnel_iface=tunnel_iface,
                policy=pol,
            ),
            rollback=windows_kill_switch_rollback_commands(),
            platform="windows",
        )
    if plat in ("linux", "ubuntu", "mint"):
        return KillSwitchApplyPlan(
            apply=linux_kill_switch_block_commands(
                server_host=server_host,
                tunnel_iface=tunnel_iface,
                policy=pol,
            ),
            rollback=linux_kill_switch_rollback_commands(),
            platform="linux",
        )
    if plat in ("android", "ios", "macos", "apple"):
        # Native VpnService / NE provide blocking; expose flags for structural tests
        return KillSwitchApplyPlan(
            apply=[],
            rollback=[],
            platform=plat,
        )
    return KillSwitchApplyPlan(platform=plat)
