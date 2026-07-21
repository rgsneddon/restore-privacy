"""Linux full-tunnel: TUN + dual /1 routes + sealed RPT DATA plane.

Mint / Ubuntu-family. Residual public IP only changes when system TUN + dual /1
are active (same honesty as Windows). Requires root for product Connect.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

from client.connect import RptClient
from client.dataplane import RptDataPlane
from client.full_tunnel import (
    FullTunnelPlan,
    linux_ipv6_leak_block_commands,
    linux_ipv6_leak_rollback_commands,
    linux_route_commands,
    linux_route_delete_commands,
)
from client.linux.tun_linux import (
    LinuxTun,
    create_linux_tun,
    is_root,
    resolve_default_route,
    system_capture_ready,
)


@dataclass
class LinuxTunnelResult:
    ok: bool
    message: str
    applied_commands: list[str] = field(default_factory=list)
    tun: Optional[LinuxTun] = None
    dataplane: Optional[RptDataPlane] = None
    system_capture: bool = False
    routes_applied: bool = False
    plan: Optional[FullTunnelPlan] = None
    server_host: Optional[str] = None
    iface: Optional[str] = None
    ipv6_mitigation_applied: bool = False
    kill_switch_applied: bool = False


def product_connect_requires_root() -> bool:
    """Product residual public IP path needs root (TUN + dual /1)."""
    return True


def residual_ip_capture_active(result: Optional[LinuxTunnelResult]) -> bool:
    """True only when residual public IP can change via full tunnel."""
    if result is None:
        return False
    return bool(
        result.ok
        and result.routes_applied
        and result.system_capture
        and result.dataplane is not None
    )


def ipv6_residual_protected(result: Optional[LinuxTunnelResult]) -> bool:
    if not residual_ip_capture_active(result):
        return False
    return bool(result and result.ipv6_mitigation_applied)


def apply_ipv6_leak_mitigation(iface: str = "rpt0") -> tuple[list[str], bool]:
    """Install IPv6 blackhole; ok only if a blackhole default route command succeeded."""
    cmds = linux_ipv6_leak_block_commands(iface=iface)
    applied, _errs = _run_cmds(cmds)
    # linux _run_cmds only appends returncode==0 (or known-idempotent) to applied —
    # never treat mere attempt as success.
    ok = any("blackhole default" in c for c in applied)
    return applied, ok


def rollback_ipv6_leak_mitigation(iface: str = "rpt0") -> list[str]:
    cmds = linux_ipv6_leak_rollback_commands(iface=iface)
    applied, _ = _run_cmds(cmds)
    return applied


def product_tunnel_attach_active(result: Optional[LinuxTunnelResult]) -> bool:
    if result is None or not result.ok:
        return False
    if result.dataplane is None:
        return False
    try:
        return bool(result.dataplane.is_running())
    except Exception:
        return True


def build_linux_route_plan_cmds(
    plan: FullTunnelPlan,
    server_host: str,
    *,
    physical_gw: str,
    physical_dev: str,
    include_catchall: bool = True,
) -> list[str]:
    """Build concrete ``ip`` commands (testable without root)."""
    iface = plan.tunnel_iface if plan.tunnel_iface else "rpt0"
    if iface.upper() == "RPT":
        iface = "rpt0"
        plan.tunnel_iface = iface
    return linux_route_commands(
        plan,
        server_host,
        iface=iface,
        physical_dev=physical_dev,
        physical_gw=physical_gw,
        include_catchall=include_catchall,
    )


def _run_cmds(cmds: list[str]) -> tuple[list[str], list[str]]:
    applied: list[str] = []
    errors: list[str] = []
    for cmd in cmds:
        if "PHYSICAL_" in cmd:
            errors.append(f"placeholder not substituted: {cmd}")
            continue
        try:
            r = subprocess.run(
                shlex.split(cmd),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if r.returncode == 0:
                applied.append(cmd)
            else:
                err = (r.stderr or r.stdout or "").strip() or f"exit {r.returncode}"
                # idempotent deletes
                low = err.lower()
                if "no such" in low or "not found" in low or "cannot find" in low:
                    applied.append(cmd)
                else:
                    errors.append(f"{cmd}: {err}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{cmd}: {exc}")
    return applied, errors


def rollback_full_tunnel_routes(
    plan: FullTunnelPlan,
    server_host: str,
    iface: Optional[str] = None,
) -> list[str]:
    cmds = linux_route_delete_commands(plan, server_host, iface=iface)
    applied, _ = _run_cmds(cmds)
    return applied


def stop_full_tunnel(
    result: Optional[LinuxTunnelResult] = None,
    client: Optional[RptClient] = None,
    *,
    disconnect_session: bool = True,
    preserve_message: bool = False,
) -> list[str]:
    """Idempotent teardown: routes -> dataplane -> TUN -> session."""
    applied: list[str] = []
    res = result
    plane = res.dataplane if res is not None else None
    tun = res.tun if res is not None else None
    routes_were_on = bool(res and res.routes_applied)
    plan_obj = res.plan if res else None
    host = res.server_host if res else None
    iface = res.iface if res else None

    if host and (routes_were_on or plan_obj is not None):
        try:
            p = plan_obj or FullTunnelPlan(
                tunnel_iface=iface or "rpt0", tunnel_client_ip="10.88.0.2"
            )
            applied.extend(rollback_full_tunnel_routes(p, host, iface))
        except Exception:
            pass

    if res is not None and (
        getattr(res, "ipv6_mitigation_applied", False) or routes_were_on
    ):
        try:
            applied.extend(rollback_ipv6_leak_mitigation(iface or "rpt0"))
        except Exception:
            pass
        try:
            res.ipv6_mitigation_applied = False
        except Exception:
            pass

    if routes_were_on or (res is not None and getattr(res, "kill_switch_applied", False)):
        try:
            from client.kill_switch import linux_kill_switch_rollback_commands

            rb, _ = _run_cmds(linux_kill_switch_rollback_commands())
            applied.extend(rb)
            if res is not None:
                res.kill_switch_applied = False
        except Exception:
            pass

    if plane is not None:
        try:
            plane.stop()
        except Exception:
            pass

    if tun is not None:
        try:
            tun.close()
        except Exception:
            pass

    if disconnect_session and client is not None:
        try:
            client.disconnect()
        except Exception:
            pass

    if res is not None:
        res.ok = False
        res.routes_applied = False
        res.dataplane = None
        res.tun = None
        if not preserve_message:
            res.message = "tunnel stopped - full teardown complete"

    return applied


def start_full_tunnel(
    client: RptClient,
    plan: FullTunnelPlan,
    server_host: str,
    *,
    dry_run: bool = False,
    require_system_capture: bool = True,
    prior: "LinuxTunnelResult | None" = None,
    prefetched_default_route: tuple | None = None,
) -> LinuxTunnelResult:
    """Open TUN, apply dual /1 routes, start DATA plane.

    Product residual path (``require_system_capture=True``) refuses success without
    real TUN + dual /1. ``dry_run`` only returns the planned ``ip`` commands.

    If ``prior`` already has residual routes for the same plan IP, return it
    without re-applying routes. ``prefetched_default_route`` is
    ``(gw, phys_dev)`` from resolve_default_route() overlapped with HELLO.
    """
    if not client.session:
        return LinuxTunnelResult(False, "no session", [])

    if (
        prior is not None
        and prior.ok
        and prior.routes_applied
        and prior.system_capture
        and prior.plan is not None
        and prior.plan.tunnel_client_ip == plan.tunnel_client_ip
        and prior.server_host == server_host
        and not dry_run
    ):
        return LinuxTunnelResult(
            True,
            "residual already applied for this session",
            applied_commands=list(prior.applied_commands or []),
            system_capture=True,
            routes_applied=True,
            plan=plan,
            server_host=server_host,
            iface=prior.iface,
            tun=prior.tun,
            dataplane=prior.dataplane,
        )

    iface = (plan.tunnel_iface or "rpt0").strip()
    if not iface or iface.upper() == "RPT":
        iface = "rpt0"
    plan.tunnel_iface = iface

    if (
        prefetched_default_route is not None
        and isinstance(prefetched_default_route, (tuple, list))
        and len(prefetched_default_route) >= 2
    ):
        gw, phys_dev = prefetched_default_route[0], prefetched_default_route[1]
        # Empty prefetch (timeout/failure) must fall back to a live resolve —
        # never stick with (None, None) and fail residual attach.
        if not gw and not phys_dev:
            gw, phys_dev = resolve_default_route()
    else:
        gw, phys_dev = resolve_default_route()
    if dry_run:
        cmds = build_linux_route_plan_cmds(
            plan,
            server_host,
            physical_gw=gw or "192.168.1.1",
            physical_dev=phys_dev or "eth0",
            include_catchall=True,
        )
        return LinuxTunnelResult(
            True,
            "dry_run",
            applied_commands=cmds,
            system_capture=False,
            routes_applied=False,
            plan=plan,
            server_host=server_host,
            iface=iface,
        )

    if sys.platform != "linux":
        return LinuxTunnelResult(
            False,
            "Linux full tunnel only runs on Linux (use Mint/Ubuntu with /dev/net/tun)",
            plan=plan,
            server_host=server_host,
            iface=iface,
        )

    if require_system_capture and not is_root():
        return LinuxTunnelResult(
            False,
            "Root required so residual public IP uses the VPN node "
            "(sudo python -m client.linux, or re-run after approving elevation).",
            plan=plan,
            server_host=server_host,
            iface=iface,
        )

    if require_system_capture and not system_capture_ready():
        return LinuxTunnelResult(
            False,
            "System TUN not ready - ensure /dev/net/tun exists (sudo modprobe tun)",
            plan=plan,
            server_host=server_host,
            iface=iface,
        )

    tun, tun_msg = create_linux_tun(iface, require_system=require_system_capture)
    if tun is None:
        return LinuxTunnelResult(
            False,
            tun_msg,
            plan=plan,
            server_host=server_host,
            iface=iface,
        )

    if not phys_dev:
        try:
            tun.close()
        except Exception:
            pass
        return LinuxTunnelResult(
            False,
            "Could not resolve default route device for server pin "
            "(ip -4 route show default)",
            plan=plan,
            server_host=server_host,
            iface=iface,
        )
    # On-link default (no via): pin with dev only
    pin_gw = gw if gw else "ONLINK"

    cmds = build_linux_route_plan_cmds(
        plan,
        server_host,
        physical_gw=pin_gw,
        physical_dev=phys_dev,
        include_catchall=True,
    )
    applied, errors = _run_cmds(cmds)
    catch_ok = any("0.0.0.0/1" in c for c in applied) and any(
        "128.0.0.0/1" in c for c in applied
    )
    if not catch_ok:
        try:
            rollback_full_tunnel_routes(plan, server_host, iface)
        except Exception:
            pass
        try:
            tun.close()
        except Exception:
            pass
        detail = "; ".join(errors[:3]) if errors else "dual /1 routes not applied"
        return LinuxTunnelResult(
            False,
            f"Full-tunnel routes failed: {detail}",
            applied_commands=applied,
            plan=plan,
            server_host=server_host,
            iface=iface,
            system_capture=True,
            routes_applied=False,
        )

    # DATA plane: RptDataPlane.start requires TunIO (LinuxTun implements it)
    # Product traffic-shape policy (padding/jitter/cover; RPT_TRAFFIC_SHAPE=0 disables)
    try:
        from client.product_policy import product_dataplane_traffic_shape

        plane = RptDataPlane(client, traffic_shape=product_dataplane_traffic_shape())
        plane.start(tun)
    except Exception as exc:  # noqa: BLE001
        rollback_full_tunnel_routes(plan, server_host, iface)
        try:
            tun.close()
        except Exception:
            pass
        return LinuxTunnelResult(
            False,
            f"dataplane failed: {exc}",
            applied_commands=applied,
            plan=plan,
            server_host=server_host,
            iface=iface,
            system_capture=True,
            routes_applied=False,
        )

    ipv6_ok = False
    try:
        v6_cmds, ipv6_ok = apply_ipv6_leak_mitigation(iface)
        applied.extend(v6_cmds)
    except Exception:
        ipv6_ok = False
    msg = f"full tunnel active on {iface} ({tun_msg})"
    if ipv6_ok:
        msg += "; IPv6 ISP path blocked"
    else:
        msg += "; IPv6 leak mitigation incomplete"

    ks_applied = False
    try:
        from client.kill_switch import (
            build_kill_switch_plan,
            product_kill_switch_enabled,
            run_kill_switch_commands,
        )

        if product_kill_switch_enabled():
            ks = build_kill_switch_plan(
                "linux",
                server_host=server_host,
                tunnel_iface=iface or "rpt0",
            )
            ran, ok, errs = run_kill_switch_commands(
                ks.apply, shell=True, platform="linux"
            )
            applied.extend(ran)
            ks_applied = bool(ok)
            if ks_applied:
                msg += "; kill-switch on"
            elif ks.apply:
                detail = errs[0] if errs else "rules not verified"
                msg += f"; kill-switch incomplete ({detail})"
    except Exception:
        ks_applied = False

    return LinuxTunnelResult(
        True,
        msg,
        applied_commands=applied,
        tun=tun,
        dataplane=plane,
        system_capture=True,
        routes_applied=True,
        plan=plan,
        server_host=server_host,
        iface=iface,
        ipv6_mitigation_applied=ipv6_ok,
        kill_switch_applied=ks_applied,
    )
