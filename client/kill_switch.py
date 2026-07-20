"""Always-on kill switch: block non-tunnel egress while full tunnel is expected.

When the product tunnel is active (or kill-switch is engaged), traffic must not
leak to the default physical interface. Rules are fail-closed on connect path:
apply blocks after routes; on disconnect, always roll back.

Windows (critical):
  Explicit unscoped ``Action=Block`` rules **defeat** scoped allows (Defender
  Firewall evaluates block before allow). So we **never** create a global
  outbound block rule. Instead:

  1. Save each profile's ``DefaultOutboundAction`` to ProgramData state file
  2. ``Set-NetFirewallProfile -DefaultOutboundAction Block`` (fail-closed default)
  3. Scoped **Allow** only: node RemoteAddress, tunnel InterfaceAlias, loopback
  4. Optional **scoped** Block for STUN/mDNS (RemotePort only — not global)

  Rollback restores saved DefaultOutboundAction and removes RPT-KS rules.

Linux: iptables OUTPUT chain — ACCEPT lo + tunnel iface + node host; DROP rest.

Android uses ``VpnService.Builder.setBlocking(true)``.
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

# Critical allow rule display names (literal in command text)
WIN_CRITICAL_ALLOW_NODE = f"{WIN_RULE_PREFIX}-allow-node"
WIN_CRITICAL_ALLOW_TUN = f"{WIN_RULE_PREFIX}-allow-tun-if"
# Profile-level fail-closed (not an unscoped New-NetFirewallRule Block)
WIN_PROFILE_DEFAULT_OUTBOUND_BLOCK = "DefaultOutboundAction Block"
# State file for prior profile outbound actions (restored on rollback)
WIN_KS_STATE_FILE = r"$env:ProgramData\RestorePrivacy\ks-outbound-state.json"


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
    """Scoped allows + profile DefaultOutboundAction=Block (no unscoped block rule).

    Requires admin. Uses PowerShell NetSecurity cmdlets.
    """
    pol = policy or default_kill_switch_policy()
    if not pol.enabled or not pol.block_non_tunnel_ipv4:
        return []
    host = _ps_escape_single(server_host.strip())
    iface = _ps_escape_single((tunnel_iface or "RPT").strip())
    n_node = WIN_CRITICAL_ALLOW_NODE
    n_tun = WIN_CRITICAL_ALLOW_TUN
    n_lo = f"{WIN_RULE_PREFIX}-allow-lo"
    n_stun = f"{WIN_RULE_PREFIX}-block-stun"
    n_mdns = f"{WIN_RULE_PREFIX}-block-mdns"
    pfx = WIN_RULE_PREFIX
    state = WIN_KS_STATE_FILE

    # PowerShell: save profile outbound actions → scoped allows → DefaultOutboundAction Block
    script = f"""
$ErrorActionPreference = 'Stop'
$statePath = {state}
$dir = Split-Path -Parent $statePath
if (-not (Test-Path $dir)) {{ New-Item -ItemType Directory -Path $dir -Force | Out-Null }}
# Save prior DefaultOutboundAction per profile for honest rollback
$prior = @{{}}
foreach ($name in @('Domain','Private','Public')) {{
  $p = Get-NetFirewallProfile -Name $name -ErrorAction Stop
  $prior[$name] = [string]$p.DefaultOutboundAction
}}
$prior | ConvertTo-Json | Set-Content -Path $statePath -Encoding UTF8
# Remove prior RPT-KS rules only (not other firewall rules)
Get-NetFirewallRule -ErrorAction SilentlyContinue |
  Where-Object {{ $_.DisplayName -like '{pfx}-*' }} |
  Remove-NetFirewallRule -ErrorAction SilentlyContinue
# Scoped allows only (node RemoteAddress + tunnel InterfaceAlias + loopback)
New-NetFirewallRule -DisplayName '{n_node}' -Direction Outbound -Action Allow -RemoteAddress '{host}' -Enabled True -Profile Any | Out-Null
$if = Get-NetAdapter -Name '{iface}' -ErrorAction SilentlyContinue
if (-not $if) {{ throw 'tunnel adapter not found: {iface}' }}
New-NetFirewallRule -DisplayName '{n_tun}' -Direction Outbound -Action Allow -InterfaceAlias $if.Name -Enabled True -Profile Any | Out-Null
New-NetFirewallRule -DisplayName '{n_lo}' -Direction Outbound -Action Allow -RemoteAddress 127.0.0.0/8 -Enabled True -Profile Any | Out-Null
"""
    if pol.block_stun_mdns:
        # Port-scoped blocks only (RemotePort) — not global unscoped Action Block
        script += f"""
New-NetFirewallRule -DisplayName '{n_stun}' -Direction Outbound -Action Block -Protocol UDP -RemotePort 3478,5349 -Enabled True -Profile Any | Out-Null
New-NetFirewallRule -DisplayName '{n_mdns}' -Direction Outbound -Action Block -Protocol UDP -RemotePort 5353 -Enabled True -Profile Any | Out-Null
"""
    script += f"""
# Fail-closed via profile default (NOT an unscoped New-NetFirewallRule Action Block)
foreach ($name in @('Domain','Private','Public')) {{
  Set-NetFirewallProfile -Name $name -DefaultOutboundAction Block -ErrorAction Stop
}}
# Verify critical allows + profile default
foreach ($n in @('{n_node}', '{n_tun}')) {{
  if (-not (Get-NetFirewallRule -DisplayName $n -ErrorAction SilentlyContinue)) {{
    throw ('missing critical kill-switch allow rule: ' + $n)
  }}
}}
foreach ($name in @('Domain','Private','Public')) {{
  $p = Get-NetFirewallProfile -Name $name
  if ([string]$p.DefaultOutboundAction -ne 'Block') {{
    throw ('DefaultOutboundAction not Block on profile: ' + $name)
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
    """Remove RPT-KS rules and restore prior DefaultOutboundAction from state file."""
    pfx = WIN_RULE_PREFIX
    state = WIN_KS_STATE_FILE
    script = f"""
$ErrorActionPreference = 'Continue'
$statePath = {state}
Get-NetFirewallRule -ErrorAction SilentlyContinue |
  Where-Object {{ $_.DisplayName -like '{pfx}-*' }} |
  Remove-NetFirewallRule -ErrorAction SilentlyContinue
if (Test-Path $statePath) {{
  try {{
    $prior = Get-Content -Path $statePath -Raw | ConvertFrom-Json
    foreach ($name in @('Domain','Private','Public')) {{
      $val = $prior.$name
      if (-not $val) {{ $val = 'Allow' }}
      Set-NetFirewallProfile -Name $name -DefaultOutboundAction $val -ErrorAction SilentlyContinue
    }}
    Remove-Item -Path $statePath -Force -ErrorAction SilentlyContinue
  }} catch {{
    foreach ($name in @('Domain','Private','Public')) {{
      Set-NetFirewallProfile -Name $name -DefaultOutboundAction Allow -ErrorAction SilentlyContinue
    }}
  }}
}} else {{
  foreach ($name in @('Domain','Private','Public')) {{
    Set-NetFirewallProfile -Name $name -DefaultOutboundAction Allow -ErrorAction SilentlyContinue
  }}
}}
exit 0
"""
    one_line = " ".join(line.strip() for line in script.splitlines() if line.strip())
    return [
        f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{one_line}"'
    ]


def assert_windows_ks_commands_safe(cmds: list[str]) -> list[str]:
    """Return violations for unsafe Windows kill-switch command shapes.

    - No unrestricted allow (remoteip=any without InterfaceAlias)
    - No **unscoped** Action=Block New-NetFirewallRule (no RemotePort/RemoteAddress/
      InterfaceAlias) — those blackhole VPN traffic under Defender rule order
    - Must use Set-NetFirewallProfile DefaultOutboundAction Block
    - Must scope allows via InterfaceAlias + RemoteAddress
    - Rollback must restore DefaultOutboundAction
    """
    violations: list[str] = []
    joined = "\n".join(cmds)
    low = joined.lower()

    # netsh-style remoteip=any on an allow rule
    for m in re.finditer(
        r"action\s*=\s*allow[^\"\n]*remoteip\s*=\s*any",
        joined,
        flags=re.IGNORECASE,
    ):
        snippet = m.group(0)
        if "interfacealias" not in snippet.lower():
            violations.append(f"unrestricted allow remoteip=any: {snippet[:80]}")
    if re.search(
        r"remoteip\s*=\s*any.*localip\s*=\s*any|localip\s*=\s*any.*remoteip\s*=\s*any",
        joined,
        re.I,
    ):
        if "InterfaceAlias" not in joined:
            violations.append(
                "allow rule pairs localip=any with remoteip=any without InterfaceAlias"
            )
    if re.search(r'action=allow[^"\n]*#\s*iface=', joined, re.I):
        violations.append("netsh allow rule contains invalid # iface= trailer")

    # Unscoped New-NetFirewallRule Action Block (no port/addr/iface scope)
    # Match PowerShell: New-NetFirewallRule ... -Action Block ... without RemotePort etc.
    for m in re.finditer(
        r"New-NetFirewallRule\b[^;|]*?-Action\s+Block\b[^;|]*",
        joined,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        rule = m.group(0)
        rl = rule.lower()
        scoped = any(
            k in rl
            for k in (
                "-remoteport",
                "-remoteaddress",
                "-localport",
                "-localaddress",
                "-interfacealias",
                "-program",
                "-service",
            )
        )
        if not scoped:
            violations.append(
                "unscoped New-NetFirewallRule Action=Block blackholes VPN "
                f"(use DefaultOutboundAction Block + scoped allows): {rule[:120]}"
            )

    # Legacy RPT-KS-block-out unscoped rule name must not appear
    if f"{WIN_RULE_PREFIX}-block-out" in joined:
        violations.append(
            f"legacy unscoped {WIN_RULE_PREFIX}-block-out rule must not be created"
        )

    if cmds and "InterfaceAlias" not in joined:
        violations.append("missing InterfaceAlias-scoped tunnel allow")
    if cmds and "RemoteAddress" not in joined and "remoteip=" not in low:
        violations.append("missing node RemoteAddress/remoteip allow")
    if cmds and "Set-NetFirewallProfile" not in joined:
        violations.append("missing Set-NetFirewallProfile for DefaultOutboundAction")
    if cmds and "DefaultOutboundAction" not in joined:
        violations.append("missing DefaultOutboundAction Block profile setting")
    if cmds and "Block" not in joined:
        violations.append("missing fail-closed Block default")

    return violations


def assert_windows_ks_rollback_restores_profiles(cmds: list[str]) -> list[str]:
    """Rollback must restore DefaultOutboundAction (from state or Allow fallback)."""
    violations: list[str] = []
    joined = "\n".join(cmds)
    if "Set-NetFirewallProfile" not in joined:
        violations.append("rollback missing Set-NetFirewallProfile restore")
    if "DefaultOutboundAction" not in joined:
        violations.append("rollback missing DefaultOutboundAction restore")
    if "ks-outbound-state" not in joined and "Allow" not in joined:
        violations.append("rollback missing state file or Allow fallback")
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
    **and** (for Windows) stdout contains ``RPT_KS_OK`` — never True merely
    because the plan was non-empty.
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
                low = out.lower()
                if "no such" in low or "not found" in low or "cannot find" in low:
                    applied.append(cmd)
                else:
                    errors.append(
                        f"exit {r.returncode}: {out.strip()[:200] or cmd[:80]}"
                    )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {exc}")
    plat = platform.lower()
    if not cmds:
        return applied, False, errors
    if plat in ("windows", "win32", "win"):
        success = any_zero and saw_ok_marker and not errors
        return applied, success, errors
    if plat in ("linux", "ubuntu", "mint"):
        if any_zero and not errors:
            return applied, True, errors
        joined = "\n".join(applied)
        success = any_zero and "-o " in joined and "-j DROP" in joined
        return applied, success, errors
    return applied, any_zero and not errors, errors
