"""Scoped Windows Defender Firewall allows for product residual Connect.

Windows Defender Firewall (and leftover RPT-KS profile Block) can drop UDP HELLO
to the product node so Connect times out while the node is healthy.

Product policy:
  - Emit **scoped allows only** (program path + node RemoteAddress/UDP port).
  - Never unscoped ``Action=Block`` and never remote allow-any without Program.
  - Product kill-switch remains **opt-in** (``RPT_KILL_SWITCH=1``) in kill_switch.py.
  - Rule names use ``RPT-FW-*`` so KS rollback (``RPT-KS-*``) does not remove them.

Builders are pure (PowerShell bodies / EncodedCommand); apply is best-effort when elevated.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from client.endpoint import PRODUCT_NODE_HOST, PRODUCT_NODE_PORT
from client.kill_switch import (
    powershell_encoded_command,
    decode_powershell_encoded_command,
)

# Stable prefix — distinct from kill-switch RPT-KS so restore/uninstall are exact
WIN_FW_PREFIX = "RPT-FW"
WIN_FW_ALLOW_NODE = f"{WIN_FW_PREFIX}-allow-node-udp"
WIN_FW_ALLOW_PROGRAM = f"{WIN_FW_PREFIX}-allow-program"
WIN_FW_ALLOW_PROGRAM_IN = f"{WIN_FW_PREFIX}-allow-program-in"


def _ps_escape_single(s: str) -> str:
    return s.replace("'", "''")


def resolve_product_exe_path(explicit: Optional[str] = None) -> str:
    """Best-effort path to the product GUI exe for -Program scoped rules."""
    if explicit and explicit.strip():
        return str(Path(explicit.strip()).expanduser())
    if getattr(sys, "frozen", False):
        try:
            return str(Path(sys.executable).resolve())
        except Exception:
            pass
    # Dev / non-frozen: no reliable single exe — leave empty (node allow still applies)
    env = os.environ.get("RPT_PRODUCT_EXE", "").strip()
    return env


def windows_fw_allow_script(
    *,
    server_host: str | None = None,
    server_port: int | None = None,
    program_path: str | None = None,
) -> str:
    """Multi-line PowerShell body: scoped product allows for residual Connect."""
    host = _ps_escape_single((server_host or PRODUCT_NODE_HOST).strip())
    port = int(server_port if server_port is not None else PRODUCT_NODE_PORT)
    prog = (program_path if program_path is not None else resolve_product_exe_path()).strip()
    prog_esc = _ps_escape_single(prog) if prog else ""

    lines = [
        "$ErrorActionPreference = 'Continue'",
        f"$pfx = '{WIN_FW_PREFIX}'",
        # Remove prior product allows only (never touch RPT-KS or unrelated rules)
        "Get-NetFirewallRule -ErrorAction SilentlyContinue |",
        "  Where-Object { $_.DisplayName -like ($pfx + '-*') } |",
        "  Remove-NetFirewallRule -ErrorAction SilentlyContinue",
        # Outbound UDP to product node (HELLO + residual DATA)
        (
            f"New-NetFirewallRule -DisplayName '{WIN_FW_ALLOW_NODE}' -Direction Outbound "
            f"-Action Allow -Protocol UDP -RemoteAddress '{host}' -RemotePort {port} "
            f"-Enabled True -Profile Any -ErrorAction Stop | Out-Null"
        ),
        # Also allow any outbound to the node host for residual TCP diagnostics (scoped RemoteAddress)
        (
            f"New-NetFirewallRule -DisplayName '{WIN_FW_PREFIX}-allow-node-any' -Direction Outbound "
            f"-Action Allow -RemoteAddress '{host}' -Enabled True -Profile Any "
            f"-ErrorAction SilentlyContinue | Out-Null"
        ),
    ]
    if prog_esc:
        lines.extend(
            [
                f"$prog = '{prog_esc}'",
                "if (Test-Path -LiteralPath $prog) {",
                (
                    f"  New-NetFirewallRule -DisplayName '{WIN_FW_ALLOW_PROGRAM}' "
                    f"-Direction Outbound -Action Allow -Program $prog "
                    f"-Enabled True -Profile Any -ErrorAction SilentlyContinue | Out-Null"
                ),
                (
                    f"  New-NetFirewallRule -DisplayName '{WIN_FW_ALLOW_PROGRAM_IN}' "
                    f"-Direction Inbound -Action Allow -Program $prog "
                    f"-Enabled True -Profile Any -ErrorAction SilentlyContinue | Out-Null"
                ),
                "}",
            ]
        )
    lines.extend(
        [
            f"if (-not (Get-NetFirewallRule -DisplayName '{WIN_FW_ALLOW_NODE}' -ErrorAction SilentlyContinue)) {{",
            f"  throw 'missing critical firewall allow: {WIN_FW_ALLOW_NODE}'",
            "}",
            "Write-Output 'RPT_FW_ALLOW_OK'",
            "exit 0",
        ]
    )
    return "\n".join(lines) + "\n"


def windows_fw_allow_commands(
    *,
    server_host: str | None = None,
    server_port: int | None = None,
    program_path: str | None = None,
) -> list[str]:
    """Executable argv: EncodedCommand wrapping :func:`windows_fw_allow_script`."""
    body = windows_fw_allow_script(
        server_host=server_host,
        server_port=server_port,
        program_path=program_path,
    )
    return [powershell_encoded_command(body)]


def windows_fw_remove_script() -> str:
    """Remove product RPT-FW-* rules only (uninstall / repair)."""
    pfx = WIN_FW_PREFIX
    return (
        "$ErrorActionPreference = 'Continue'\n"
        "Get-NetFirewallRule -ErrorAction SilentlyContinue |\n"
        f"  Where-Object {{ $_.DisplayName -like '{pfx}-*' }} |\n"
        "  Remove-NetFirewallRule -ErrorAction SilentlyContinue\n"
        "Write-Output 'RPT_FW_REMOVED'\n"
        "exit 0\n"
    )


def windows_fw_remove_commands() -> list[str]:
    return [powershell_encoded_command(windows_fw_remove_script())]


def assert_windows_fw_allow_script_safe(script_body: str) -> list[str]:
    """Safety: scoped allows only; no unscoped Block; no unrestricted allow-any."""
    violations: list[str] = []
    joined = script_body
    low = joined.lower()

    if "Action Block" in joined or re.search(r"-Action\s+Block\b", joined, re.I):
        violations.append("product allow script must not create Action=Block rules")
    if "DefaultOutboundAction" in joined and "Block" in joined:
        violations.append("product allow script must not set DefaultOutboundAction Block")
    if WIN_FW_ALLOW_NODE not in joined:
        violations.append(f"missing critical allow name {WIN_FW_ALLOW_NODE}")
    if "RemoteAddress" not in joined and "remoteaddress" not in low:
        violations.append("missing node RemoteAddress scope")
    if "UDP" not in joined and "udp" not in low:
        violations.append("missing UDP protocol on node allow")
    # Unrestricted allow any without Program is unsafe
    for m in re.finditer(
        r"New-NetFirewallRule\b[^\n]*",
        joined,
        flags=re.IGNORECASE,
    ):
        rule = m.group(0)
        rl = rule.lower()
        if "-action" in rl and "allow" in rl:
            has_scope = any(
                k in rl
                for k in (
                    "-remoteaddress",
                    "-remoteport",
                    "-localport",
                    "-program",
                    "-interfacealias",
                    "-service",
                )
            )
            if not has_scope:
                violations.append(f"unscoped Allow rule: {rule[:120]}")
            if "remoteaddress 'any'" in rl or 'remoteaddress "any"' in rl:
                if "-program" not in rl:
                    violations.append(f"RemoteAddress Any without Program: {rule[:120]}")
    if f"{WIN_FW_PREFIX}-block" in low:
        violations.append("product allow prefix must not create block-* rules")
    return violations


def assert_windows_fw_allow_commands_safe(cmds: list[str]) -> list[str]:
    if not cmds:
        return ["empty allow command list"]
    violations: list[str] = []
    for c in cmds:
        if "-EncodedCommand" not in c:
            violations.append("allow command must use -EncodedCommand")
            continue
        try:
            body = decode_powershell_encoded_command(c)
        except Exception as exc:
            violations.append(f"decode failed: {exc}")
            continue
        violations.extend(assert_windows_fw_allow_script_safe(body))
    return violations


def apply_windows_fw_allows(
    *,
    server_host: str | None = None,
    server_port: int | None = None,
    program_path: str | None = None,
    timeout: float = 45.0,
) -> tuple[list[str], bool, list[str]]:
    """Best-effort apply product firewall allows. Returns (ran_cmds, ok, errors)."""
    cmds = windows_fw_allow_commands(
        server_host=server_host,
        server_port=server_port,
        program_path=program_path,
    )
    safe = assert_windows_fw_allow_commands_safe(cmds)
    if safe:
        return cmds, False, list(safe)
    ran: list[str] = []
    errors: list[str] = []
    ok = False
    for cmd in cmds:
        try:
            r = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            ran.append(cmd)
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode == 0 and "RPT_FW_ALLOW_OK" in out:
                ok = True
            elif r.returncode != 0:
                errors.append((out or f"exit {r.returncode}").strip()[:200])
        except Exception as exc:
            errors.append(str(exc)[:200])
    return ran, ok, errors


def windows_firewall_connect_hint() -> str:
    """User-facing hint when residual HELLO may be blocked by Defender Firewall."""
    return (
        "Windows Defender Firewall may block residual UDP to the VPN node. "
        "Approve elevation if prompted, run AllowFirewall.bat (or reinstall), "
        "or use Restore Internet (if stuck) then Connect again — "
        "a timeout is not always a down node."
    )
