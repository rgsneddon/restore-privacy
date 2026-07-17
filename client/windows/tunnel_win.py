"""Windows full-tunnel setup helpers for RPT (admin / wintun when available)."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

from client.full_tunnel import FullTunnelPlan, windows_route_commands


@dataclass
class WindowsTunnelResult:
    ok: bool
    message: str
    applied_commands: list[str]


def is_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def physical_default_gateway() -> Optional[str]:
    try:
        out = subprocess.check_output(
            ["route", "print", "0.0.0.0"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except Exception:
        return None
    for line in out.splitlines():
        parts = line.split()
        # 0.0.0.0  0.0.0.0  gateway  interface  metric
        if len(parts) >= 3 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
            gw = parts[2]
            if gw.count(".") == 3 and not gw.startswith("10.88."):
                return gw
    return None


def apply_full_tunnel_routes(
    plan: FullTunnelPlan,
    server_host: str,
    dry_run: bool = False,
) -> WindowsTunnelResult:
    """Install full-tunnel routes. Requires Administrator for live apply."""
    cmds = windows_route_commands(plan, server_host)
    gw = physical_default_gateway() or "0.0.0.0"
    cmds = [c.replace("PHYSICAL_GW", gw) for c in cmds]
    if dry_run or not is_admin():
        return WindowsTunnelResult(
            ok=False if not is_admin() and not dry_run else True,
            message=(
                "dry-run only"
                if dry_run
                else "Administrator rights required for full system VPN routes"
            ),
            applied_commands=cmds,
        )
    applied: list[str] = []
    for cmd in cmds:
        # route add may return non-zero if exists — continue
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        applied.append(cmd)
    return WindowsTunnelResult(ok=True, message="full-tunnel routes applied", applied_commands=applied)


def dataplane_enabled() -> bool:
    """True when the Windows client is built to wire RPT DATA after connect."""
    return True
