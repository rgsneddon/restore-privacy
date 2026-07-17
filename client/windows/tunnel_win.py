"""Windows full-tunnel setup: TUN + routes + start RPT DATA plane."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

from client.connect import RptClient
from client.dataplane import RptDataPlane
from client.full_tunnel import FullTunnelPlan, windows_route_commands
from client.windows.tun_win import WindowsTun, create_windows_tun, dataplane_enabled


@dataclass
class WindowsTunnelResult:
    ok: bool
    message: str
    applied_commands: list[str]
    tun: Optional[WindowsTun] = None
    dataplane: Optional[RptDataPlane] = None


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
        if len(parts) >= 3 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
            gw = parts[2]
            if gw.count(".") == 3 and not gw.startswith("10.88."):
                return gw
    return None


def start_full_tunnel(
    client: RptClient,
    plan: FullTunnelPlan,
    server_host: str,
    dry_run: bool = False,
) -> WindowsTunnelResult:
    """Create TUN, apply full-tunnel routes, start sealed RPT DATA plane IO."""
    if not client.session:
        return WindowsTunnelResult(False, "no session", [])

    tun = create_windows_tun(client_ip=plan.tunnel_client_ip, name=plan.tunnel_iface or "RPT")
    # Keep plan iface name consistent with what we create
    plan.tunnel_iface = tun.name

    addr_cmds = tun.configure_address()
    cmds = windows_route_commands(plan, server_host)
    gw = physical_default_gateway() or "0.0.0.0"
    cmds = [c.replace("PHYSICAL_GW", gw) for c in cmds]
    all_cmds = addr_cmds + cmds

    if dry_run:
        return WindowsTunnelResult(
            ok=True,
            message=f"dry-run full tunnel (tun_mode={tun.mode})",
            applied_commands=all_cmds,
            tun=tun,
        )

    applied: list[str] = []
    if is_admin() and tun.mode == "wintun":
        for cmd in all_cmds:
            subprocess.run(cmd, shell=True, capture_output=True, text=True)
            applied.append(cmd)
        route_msg = "full-tunnel routes applied"
    else:
        applied = all_cmds
        route_msg = (
            "TUN+dataplane started"
            + (f" (mode={tun.mode})" )
            + ("" if is_admin() else "; admin required for system-wide routes")
        )

    # ALWAYS start sealed DATA plane (criterion: seal/open on real path)
    plane = RptDataPlane(client)
    plane.start(tun)

    if not dataplane_enabled(tun) or not plane.is_running():
        plane.stop()
        tun.close()
        return WindowsTunnelResult(False, "dataplane failed to start", applied)

    return WindowsTunnelResult(
        ok=True,
        message=route_msg + f"; dataplane running (sealed RPT DATA)",
        applied_commands=applied,
        tun=tun,
        dataplane=plane,
    )


def apply_full_tunnel_routes(
    plan: FullTunnelPlan,
    server_host: str,
    dry_run: bool = False,
) -> WindowsTunnelResult:
    """Legacy helper — prefer start_full_tunnel with a live client."""
    cmds = windows_route_commands(plan, server_host)
    gw = physical_default_gateway() or "0.0.0.0"
    cmds = [c.replace("PHYSICAL_GW", gw) for c in cmds]
    return WindowsTunnelResult(
        ok=bool(dry_run or is_admin()),
        message="routes only (no dataplane) — use start_full_tunnel",
        applied_commands=cmds,
    )
