"""Always-on kill switch: block non-tunnel egress while full tunnel is expected.

When the product tunnel is active (or kill-switch is engaged), traffic must not
leak to the default physical interface. Rules are fail-closed on connect path:
apply blocks after routes; on disconnect, always roll back.

Windows: WFP rules via PowerShell ``New-NetFirewallRule`` — allow **only**
the VPN node remote IP and the tunnel ``InterfaceAlias``; then a global outbound
block. Never emit unrestricted ``remoteip=any`` allow rules.

Linux: iptables OUTPUT chain — ACCEPT lo + tunnel iface + node host; DROP rest.

IPv6 leak blocking remains in ``full_tunnel``; kill-switch complements IPv4
non-tunnel block. Android uses ``VpnService.Builder.setBlocking(true)``.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Optional

# Named rules so rollback is exact
WIN_RULE_PREFIX = "RPT-KS"
LINUX_CHAIN = "RPT_KILLSWITCH"

# Critical rule name fragments that must succeed for kill_switch_applied=True
WIN_CRITICAL_ALLOW_NODE = f"{WIN_RULE_PREFIX}-allow-node"
WIN_CRITICAL_ALLOW_TUN = f"{WIN_RULE_PREFIX}-allow-tun-if"
WIN_CRITICAL_BLOCK_OUT = f"{WIN_RULE_PREFIX}-block-out"


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


def _ps_escape_single(s: str) -> str:
    return s.replace("'", "''")


def windows_kill_switch_block_commands(
    *,
    server_host: str,
    tunnel_iface: str = "RPT",
    policy: Optional[KillSwitchPolicy] = None,
) -> list[str]:
    """Firewall rules: allow node host + tunnel InterfaceAlias only; block rest.

    Requires admin. Uses PowerShell NetSecurity cmdlets so allows are **scoped**
    (RemoteAddress=node or InterfaceAlias=tun). Never uses remoteip=any allows.
    """
    pol = policy or default_kill_switch_policy()
    if not pol.enabled or not pol.block_non_tunnel_ipv4:
        return []
    host = _ps_escape_single(server_host.strip())
    iface = _ps_escape_single((tunnel_iface or "RPT").strip())
    # Literal display names (must appear in command text for audits/tests)
    n_node = WIN_CRITICAL_ALLOW_NODE
    n_tun = WIN_CRITICAL_ALLOW_TUN
    n_block = WIN_CRITICAL_BLOCK_OUT
    n_lo = f"{WIN_RULE_PREFIX}-allow-lo"
    n_stun = f"{WIN_RULE_PREFIX}-block-stun"
    n_mdns = f"{WIN_RULE_PREFIX}-block-mdns"
    pfx = WIN_RULE_PREFIX

    # Single PowerShell script: remove prior rules, add scoped allows, then block.
    # Exit 0 only if allow-node, allow-tun-if, and block-out all exist.
    script = f"""
$ErrorActionPreference = 'Stop'
Get-NetFirewallRule -ErrorAction SilentlyContinue |
  Where-Object {{ $_.DisplayName -like '{pfx}-*' }} |
  Remove-NetFirewallRule -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName '{n_node}' -Direction Outbound -Action Allow -RemoteAddress '{host}' -Enabled True -Profile Any | Out-Null
$if = Get-NetAdapter -Name '{iface}' -ErrorAction SilentlyContinue
if (-not $if) {{ throw 'tunnel adapter not found: {iface}' }}
New-NetFirewallRule -DisplayName '{n_tun}' -Direction Outbound -Action Allow -InterfaceAlias $if.Name -Enabled True -Profile Any | Out-Null
New-NetFirewallRule -DisplayName '{n_lo}' -Direction Outbound -Action Allow -RemoteAddress 127.0.0.0/8 -Enabled True -Profile Any | Out-Null
"""
    if pol.block_stun_mdns:
        script += f"""
New-NetFirewallRule -DisplayName '{n_stun}' -Direction Outbound -Action Block -Protocol UDP -RemotePort 3478,5349 -Enabled True -Profile Any | Out-Null
New-NetFirewallRule -DisplayName '{n_mdns}' -Direction Outbound -Action Block -Protocol UDP -RemotePort 5353 -Enabled True -Profile Any | Out-Null
"""
    script += f"""
New-NetFirewallRule -DisplayName '{n_block}' -Direction Outbound -Action Block -Enabled True -Profile Any | Out-Null
$need = @('{n_node}', '{n_tun}', '{n_block}')
foreach ($n in $need) {{
  if (-not (Get-NetFirewallRule -DisplayName $n -ErrorAction SilentlyContinue)) {{
    throw ('missing critical kill-switch rule: ' + $n)
  }}
}}
Write-Output 'RPT_KS_OK'
exit 0
"""
    one_line = " ".join(line.strip() for line in script.splitlines() if line.strip())
    return [
        f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{one_line}"'
    ]


def windows_kill_switch_rollback_commands() -> list[str]:
    pfx = WIN_RULE_PREFIX
    return [
        "powershell -NoProfile -ExecutionPolicy Bypass -Command \""
        f"Get-NetFirewallRule -ErrorAction SilentlyContinue | "
        f"Where-Object {{ $_.DisplayName -like '{pfx}-*' }} | "
        f"Remove-NetFirewallRule -ErrorAction SilentlyContinue; exit 0\""
    ]


def assert_windows_ks_commands_safe(cmds: list[str]) -> list[str]:
    """Return violations if allow rules are unrestricted (remoteip=any without iface).

    Shipped product path must never emit allow-all outbound rules that defeat
    the kill switch or blackhole alongside a global block.
    """
    violations: list[str] = []
    joined = "\n".join(cmds)
    # netsh-style remoteip=any on an allow rule
    for m in re.finditer(
        r"action\s*=\s*allow[^\"\n]*remoteip\s*=\s*any",
        joined,
        flags=re.IGNORECASE,
    ):
        snippet = m.group(0)
        if "interfacealias" not in snippet.lower() and "interface type" not in snippet.lower():
            violations.append(f"unrestricted allow remoteip=any: {snippet[:80]}")
    # netsh allow with localip=any remoteip=any
    if re.search(r"remoteip\s*=\s*any.*localip\s*=\s*any|localip\s*=\s*any.*remoteip\s*=\s*any", joined, re.I):
        if "InterfaceAlias" not in joined:
            violations.append("allow rule pairs localip=any with remoteip=any without InterfaceAlias")
    # Invalid netsh comment trailers that break parsing
    if re.search(r'action=allow[^"\n]*#\s*iface=', joined, re.I):
        violations.append("netsh allow rule contains invalid # iface= trailer")
    # Must scope tun allow via InterfaceAlias in PowerShell path
    if cmds and "InterfaceAlias" not in joined:
        violations.append("missing InterfaceAlias-scoped tunnel allow")
    if cmds and ("RemoteAddress" not in joined and "remoteip=" not in joined.lower()):
        violations.append("missing node RemoteAddress/remoteip allow")
    # Must have a block-out rule
    if cmds and WIN_CRITICAL_BLOCK_OUT not in joined and "block-out" not in joined.lower():
        violations.append("missing outbound block rule")
    return violations


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
        f"iptables -N {chain} 2>/dev/null || true",
        f"iptables -F {chain}",
        f"iptables -D OUTPUT -j {chain} 2>/dev/null || true",
        f"iptables -I OUTPUT 1 -j {chain}",
        f"iptables -A {chain} -o lo -j ACCEPT",
        f"iptables -A {chain} -o {tunnel_iface} -j ACCEPT",
        f"iptables -A {chain} -d {server_host} -j ACCEPT",
        f"iptables -A {chain} -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT",
    ]
    if pol.block_stun_mdns:
        cmds.append(f"iptables -A {chain} -p udp --dport 3478 -j DROP")
        cmds.append(f"iptables -A {chain} -p udp --dport 5349 -j DROP")
        cmds.append(f"iptables -A {chain} -p udp --dport 5353 -j DROP")
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
        return KillSwitchApplyPlan(apply=[], rollback=[], platform=plat)
    return KillSwitchApplyPlan(platform=plat)


def run_kill_switch_commands(
    cmds: list[str],
    *,
    shell: bool = True,
    timeout: float = 45.0,
    platform: str = "windows",
) -> tuple[list[str], bool, list[str]]:
    """Execute kill-switch commands; return (applied, success, errors).

    ``success`` is True only when at least one command ran with returncode 0
    **and** (for Windows) stdout contains ``RPT_KS_OK`` or critical rule names
    appear in applied output — never True merely because the plan was non-empty.
    """
    applied: list[str] = []
    errors: list[str] = []
    saw_ok_marker = False
    any_zero = False
    for cmd in cmds:
        try:
            r = subprocess.run(
                cmd,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode == 0:
                applied.append(cmd)
                any_zero = True
                if "RPT_KS_OK" in out:
                    saw_ok_marker = True
            else:
                # idempotent deletes / already-exists may still be ok on rollback
                low = out.lower()
                if "no such" in low or "not found" in low or "cannot find" in low:
                    applied.append(cmd)
                else:
                    errors.append(f"exit {r.returncode}: {out.strip()[:200] or cmd[:80]}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {exc}")
    plat = platform.lower()
    if not cmds:
        return applied, False, errors
    if plat in ("windows", "win32", "win"):
        # Require explicit success marker from the PowerShell apply script
        success = any_zero and saw_ok_marker and not errors
        return applied, success, errors
    if plat in ("linux", "ubuntu", "mint"):
        # Need DROP rule and tunnel ACCEPT among applied (or zero errors on apply set)
        joined = "\n".join(applied)
        success = (
            any_zero
            and f"-o " in joined
            and "-j DROP" in joined
            and not any("exit " in e for e in errors if "2>/dev/null" not in e)
        )
        # Soften: if all cmds applied with rc0, success
        if any_zero and not errors:
            success = True
        return applied, success, errors
    return applied, any_zero and not errors, errors
