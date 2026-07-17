"""Windows full-tunnel: Wintun adapter + default routes + sealed RPT DATA plane."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

from client.connect import RptClient
from client.dataplane import RptDataPlane
from client.full_tunnel import FullTunnelPlan, windows_route_commands
from client.windows.tun_win import (
    WindowsTun,
    create_windows_tun,
    dataplane_enabled,
    system_capture_ready,
    wintun_dll_available,
)


@dataclass
class WindowsTunnelResult:
    ok: bool
    message: str
    applied_commands: list[str]
    tun: Optional[WindowsTun] = None
    dataplane: Optional[RptDataPlane] = None
    system_capture: bool = False


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


def apply_routes_for_adapter(plan: FullTunnelPlan, server_host: str) -> tuple[list[str], list[str]]:
    """Apply full-tunnel dual /1 routes via tunnel gateway; pin server on physical GW.

    Returns (commands, errors).
    """
    cmds = windows_route_commands(plan, server_host)
    gw = physical_default_gateway() or "0.0.0.0"
    cmds = [c.replace("PHYSICAL_GW", gw) for c in cmds]
    errors: list[str] = []
    for cmd in cmds:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if r.returncode != 0 and r.stderr:
            errors.append(r.stderr.strip()[:200])
    return cmds, errors


def start_full_tunnel(
    client: RptClient,
    plan: FullTunnelPlan,
    server_host: str,
    dry_run: bool = False,
    force_queue: bool = False,
    prefer_system_capture: bool = True,
) -> WindowsTunnelResult:
    """Create OS TUN (Wintun), assign IP, install full-tunnel routes, start DATA plane."""
    if not client.session:
        return WindowsTunnelResult(False, "no session", [])

    if dry_run:
        cmds = windows_route_commands(plan, server_host)
        return WindowsTunnelResult(
            ok=True,
            message="dry-run full tunnel plan",
            applied_commands=cmds,
            system_capture=False,
        )

    # Prefer real Wintun so OS routes can deliver traffic into seal_packet
    try:
        tun = create_windows_tun(
            client_ip=plan.tunnel_client_ip,
            name=plan.tunnel_iface or "RPT",
            force_queue=force_queue,
            prefer_system_capture=prefer_system_capture and not force_queue,
        )
    except Exception as exc:
        # Last resort for unit tests only
        if force_queue or not prefer_system_capture:
            tun = create_windows_tun(
                client_ip=plan.tunnel_client_ip,
                name=plan.tunnel_iface or "RPT",
                force_queue=True,
            )
        else:
            return WindowsTunnelResult(
                False,
                f"Wintun TUN failed: {exc}. Run as Administrator; wintun.dll must load.",
                [],
            )

    plan.tunnel_iface = tun.name
    applied: list[str] = []

    # Address on adapter
    try:
        applied.extend(tun.configure_address())
    except Exception as exc:
        tun.close()
        return WindowsTunnelResult(False, f"configure_address failed: {exc}", applied)

    # Full-tunnel routes whenever we have a real Wintun adapter and admin rights.
    # Also attempt routes when admin even if name-based netsh might work.
    route_msg = "routes skipped"
    if is_admin() and system_capture_ready(tun):
        cmds, errs = apply_routes_for_adapter(plan, server_host)
        applied.extend(cmds)
        route_msg = "full-tunnel routes applied" + (f" ({len(errs)} warn)" if errs else "")
    elif is_admin() and tun.mode == "wintun":
        cmds, errs = apply_routes_for_adapter(plan, server_host)
        applied.extend(cmds)
        route_msg = "full-tunnel routes applied"
    elif is_admin():
        # Admin but only queue TUN — routes would blackhole; skip
        route_msg = "admin but no OS TUN — routes not applied (would blackhole)"
    else:
        route_msg = "Administrator required for system-wide routes"

    plane = RptDataPlane(client)
    plane.start(tun)

    if not dataplane_enabled(tun) or not plane.is_running():
        plane.stop()
        tun.close()
        return WindowsTunnelResult(False, "dataplane failed to start", applied, tun=None)

    capture = system_capture_ready(tun)
    msg = (
        f"TUN mode={tun.mode}; {route_msg}; dataplane running (sealed RPT DATA); "
        f"system_capture={capture}; wintun_dll={wintun_dll_available()}"
    )
    return WindowsTunnelResult(
        ok=True,
        message=msg,
        applied_commands=applied,
        tun=tun,
        dataplane=plane,
        system_capture=capture,
    )


def apply_full_tunnel_routes(
    plan: FullTunnelPlan,
    server_host: str,
    dry_run: bool = False,
) -> WindowsTunnelResult:
    """Apply route table only (adapter must already exist)."""
    cmds = windows_route_commands(plan, server_host)
    gw = physical_default_gateway() or "0.0.0.0"
    cmds = [c.replace("PHYSICAL_GW", gw) for c in cmds]
    if dry_run or not is_admin():
        return WindowsTunnelResult(
            ok=bool(dry_run),
            message="dry-run or non-admin",
            applied_commands=cmds,
        )
    applied, errs = apply_routes_for_adapter(plan, server_host)
    return WindowsTunnelResult(
        ok=True,
        message="routes applied" + (f" warnings={errs}" if errs else ""),
        applied_commands=applied,
    )
