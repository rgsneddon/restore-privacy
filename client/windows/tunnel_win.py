"""Windows full-tunnel: Wintun adapter + default routes + sealed RPT DATA plane.

Anti-blackhole: full-tunnel catch-all routes are only applied when a real
system-capture TUN exists; routes bind to the adapter IF index; VPN server
host is pinned on the physical gateway before dual /1 routes.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

from client.connect import RptClient
from client.dataplane import RptDataPlane
from client.full_tunnel import (
    FullTunnelPlan,
    routes_would_blackhole_without_system_capture,
    windows_route_commands,
)
from client.windows.tun_win import (
    WindowsTun,
    create_windows_tun,
    dataplane_enabled,
    resolve_interface_index,
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
    routes_applied: bool = False


def is_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def physical_default_gateway() -> Optional[str]:
    """Return the physical LAN default gateway (not the RPT tunnel GW)."""
    try:
        out = subprocess.check_output(
            ["route", "print", "0.0.0.0"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except Exception:
        return None
    candidates: list[tuple[int, str]] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
            gw = parts[2]
            try:
                metric = int(parts[4])
            except ValueError:
                metric = 999
            if gw.count(".") == 3 and not gw.startswith("10.88."):
                candidates.append((metric, gw))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def apply_routes_for_adapter(
    plan: FullTunnelPlan,
    server_host: str,
    if_index: Optional[int] = None,
) -> tuple[list[str], list[str]]:
    """Apply full-tunnel dual /1 routes on TUN IF; pin server on physical GW.

    Returns (commands, errors).
    """
    cmds = windows_route_commands(plan, server_host, if_index=if_index)
    gw = physical_default_gateway()
    if not gw:
        return cmds, ["no physical default gateway — refusing full-tunnel routes (would blackhole)"]
    cmds = [c.replace("PHYSICAL_GW", gw) for c in cmds]
    errors: list[str] = []
    applied: list[str] = []
    for cmd in cmds:
        # Skip dual /1 if we somehow still have PHYSICAL_GW unsubstituted
        if "PHYSICAL_GW" in cmd:
            errors.append("physical gateway not substituted")
            continue
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        applied.append(cmd)
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()[:200]
            if err:
                errors.append(err)
    return applied, errors


def start_full_tunnel(
    client: RptClient,
    plan: FullTunnelPlan,
    server_host: str,
    dry_run: bool = False,
    force_queue: bool = False,
    prefer_system_capture: bool = True,
) -> WindowsTunnelResult:
    """Create OS TUN (Wintun), assign IP, install full-tunnel routes, start DATA plane.

    Never applies dual /1 catch-all routes without system-capture TUN + physical
    server pin — that combination is what blackholes user internet.
    """
    if not client.session:
        return WindowsTunnelResult(False, "no session", [])

    if dry_run:
        cmds = windows_route_commands(plan, server_host, if_index=42)
        return WindowsTunnelResult(
            ok=True,
            message="dry-run full tunnel plan",
            applied_commands=cmds,
            system_capture=False,
            routes_applied=False,
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

    # Address on adapter (/24 + gateway — required for non-blackhole routing)
    try:
        applied.extend(tun.configure_address())
    except Exception as exc:
        tun.close()
        return WindowsTunnelResult(False, f"configure_address failed: {exc}", applied)

    capture = system_capture_ready(tun)
    if_index = None
    if capture:
        if_index = tun.interface_index() if hasattr(tun, "interface_index") else None
        if if_index is None:
            if_index = resolve_interface_index(tun.name)

    # Full-tunnel routes ONLY when OS can actually capture traffic into TUN.
    # Queue-only TUN + default routes = permanent internet blackhole.
    route_msg = "routes skipped"
    routes_applied = False
    if routes_would_blackhole_without_system_capture(capture, apply_default_routes=True):
        # force_queue / test path: dataplane may run, but never install defaults
        route_msg = "no OS TUN capture — full-tunnel routes NOT applied (prevents blackhole)"
    elif is_admin() and capture:
        cmds, errs = apply_routes_for_adapter(plan, server_host, if_index=if_index)
        applied.extend(cmds)
        if any("refusing full-tunnel" in e for e in errs):
            route_msg = "routes refused: " + "; ".join(errs)
            routes_applied = False
        else:
            routes_applied = True
            route_msg = "full-tunnel routes applied (IF-bound, server pinned)"
            if errs:
                route_msg += f" ({len(errs)} warn)"
    elif is_admin():
        route_msg = "admin but no OS TUN — routes not applied (would blackhole)"
    else:
        route_msg = "Administrator required for system-wide routes"

    plane = RptDataPlane(client)
    plane.start(tun)

    if not dataplane_enabled(tun) or not plane.is_running():
        plane.stop()
        tun.close()
        return WindowsTunnelResult(
            False,
            "dataplane failed to start — routes not left active without forward path",
            applied,
            tun=None,
            routes_applied=routes_applied,
        )

    # Honest status: connected session is ok only if we didn't claim full tunnel
    # with dead capture. Session + dataplane running is still "ok" for VPN IP.
    msg = (
        f"TUN mode={tun.mode}; {route_msg}; dataplane running (sealed RPT DATA); "
        f"system_capture={capture}; if_index={if_index}; "
        f"wintun_dll={wintun_dll_available()}"
    )
    if routes_applied and not capture:
        # Should be unreachable by construction
        plane.stop()
        tun.close()
        return WindowsTunnelResult(
            False,
            "refused: full-tunnel routes without system capture would blackhole internet",
            applied,
            routes_applied=False,
        )

    return WindowsTunnelResult(
        ok=True,
        message=msg,
        applied_commands=applied,
        tun=tun,
        dataplane=plane,
        system_capture=capture,
        routes_applied=routes_applied,
    )


def apply_full_tunnel_routes(
    plan: FullTunnelPlan,
    server_host: str,
    dry_run: bool = False,
    if_index: Optional[int] = None,
) -> WindowsTunnelResult:
    """Apply route table only (adapter must already exist)."""
    cmds = windows_route_commands(plan, server_host, if_index=if_index)
    gw = physical_default_gateway() or "0.0.0.0"
    cmds = [c.replace("PHYSICAL_GW", gw) for c in cmds]
    if dry_run or not is_admin():
        return WindowsTunnelResult(
            ok=bool(dry_run),
            message="dry-run or non-admin",
            applied_commands=cmds,
        )
    applied, errs = apply_routes_for_adapter(plan, server_host, if_index=if_index)
    return WindowsTunnelResult(
        ok=True,
        message="routes applied" + (f" warnings={errs}" if errs else ""),
        applied_commands=applied,
        routes_applied=True,
    )
