"""Windows full-tunnel: Wintun adapter + default routes + sealed RPT DATA plane.

Anti-blackhole:
- Dual /1 only with real Wintun + valid IF index + on-link next-hop 0.0.0.0
- Never next-hop 10.88.0.1 (ARP blackhole on Wintun)
- Server host pinned on physical GW before catch-alls
- Rollback catch-alls if setup fails or if_index missing
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional

from client.connect import RptClient
from client.dataplane import RptDataPlane
from client.full_tunnel import (
    FullTunnelPlan,
    routes_would_blackhole_without_if_index,
    routes_would_blackhole_without_system_capture,
    windows_ipv6_leak_block_commands,
    windows_ipv6_leak_rollback_commands,
    windows_route_commands,
    windows_route_delete_commands,
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
    plan: Optional[FullTunnelPlan] = None
    server_host: Optional[str] = None
    if_index: Optional[int] = None
    ipv6_mitigation_applied: bool = False
    kill_switch_applied: bool = False


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


def _route_cmd_succeeded(returncode: int, stderr: str, stdout: str) -> bool:
    """Windows ``route add`` often returns non-zero if the route already exists."""
    if returncode == 0:
        return True
    text = f"{stderr or ''}{stdout or ''}".lower()
    return (
        "already exists" in text
        or "object already exists" in text
        or "the route already exists" in text
    )


def _is_server_pin_cmd(cmd: str, server_host: str) -> bool:
    return (
        "route add" in cmd
        and server_host in cmd
        and "mask 255.255.255.255" in cmd
    )


def _is_catchall_cmd(cmd: str) -> bool:
    return "route add" in cmd and "mask 128.0.0.0" in cmd


def _run_cmds(cmds: list[str]) -> tuple[list[str], list[str]]:
    """Run shell cmds; treat 'already exists' as success for route add."""
    applied: list[str] = []
    errors: list[str] = []
    for cmd in cmds:
        if "PHYSICAL_GW" in cmd:
            errors.append("physical gateway not substituted")
            continue
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        applied.append(cmd)
        if not _route_cmd_succeeded(
            r.returncode, r.stderr or "", r.stdout or ""
        ):
            err = (r.stderr or r.stdout or f"exit {r.returncode}").strip()[:200]
            errors.append(err or f"command failed: {cmd[:80]}")
    return applied, errors


def apply_routes_for_adapter(
    plan: FullTunnelPlan,
    server_host: str,
    if_index: Optional[int] = None,
    *,
    include_catchall: bool = True,
) -> tuple[list[str], list[str], bool]:
    """Apply address/DNS, server pin, then dual /1 only if pin succeeded.

    Returns ``(applied_cmds, errors, full_tunnel_ok)``.

    **Critical:** dual /1 catch-alls are **not** installed if the server pin
    fails — otherwise UDP to the node is trapped inside the tunnel (recursive
    blackhole) while the UI still claims "server pinned".
    """
    cmds = windows_route_commands(
        plan, server_host, if_index=if_index, include_catchall=include_catchall
    )
    gw = physical_default_gateway()
    if not gw:
        return (
            cmds,
            [
                "no physical default gateway — refusing full-tunnel routes (would blackhole)"
            ],
            False,
        )
    cmds = [c.replace("PHYSICAL_GW", gw) for c in cmds]

    applied: list[str] = []
    errors: list[str] = []
    pin_ok = False
    catchall_applied = 0
    catchall_wanted = include_catchall and if_index is not None and int(if_index) > 0

    for cmd in cmds:
        if "PHYSICAL_GW" in cmd:
            errors.append(
                "physical gateway not substituted — refusing full-tunnel (would blackhole)"
            )
            return applied, errors, False

        is_pin = _is_server_pin_cmd(cmd, server_host)
        is_catch = _is_catchall_cmd(cmd)

        # Never install dual /1 unless server pin already succeeded
        if is_catch and not pin_ok:
            errors.append(
                "server pin failed or missing — refusing dual /1 "
                "(would blackhole UDP to node via TUN)"
            )
            # Do not run this or further catch-alls
            continue

        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        applied.append(cmd)
        ok = _route_cmd_succeeded(r.returncode, r.stderr or "", r.stdout or "")
        if not ok:
            err = (r.stderr or r.stdout or f"exit {r.returncode}").strip()[:200]
            label = err or f"command failed: {cmd[:80]}"
            if is_pin:
                errors.append(f"server pin failed: {label}")
                pin_ok = False
            elif is_catch:
                errors.append(f"catchall route failed: {label}")
            else:
                # netsh address/dns — warn but do not block pin/catchall alone
                errors.append(f"setup warn: {label}")
            continue

        if is_pin:
            pin_ok = True
        if is_catch:
            catchall_applied += 1

    if catchall_wanted:
        full_ok = pin_ok and catchall_applied >= 2 and not any(
            "refusing dual /1" in e or "server pin failed" in e for e in errors
        )
        if pin_ok and catchall_applied < 2:
            errors.append(
                "dual /1 incomplete — refusing full-tunnel (would blackhole)"
            )
            full_ok = False
        if not full_ok:
            # Roll back anything we installed so internet is not left broken
            rollback_full_tunnel_routes(plan, server_host, if_index)
        return applied, errors, full_ok

    # Pin-only path (no catch-alls requested)
    return applied, errors, pin_ok


def rollback_full_tunnel_routes(
    plan: FullTunnelPlan,
    server_host: str,
    if_index: Optional[int] = None,
) -> list[str]:
    """Best-effort remove dual /1 + server pin so internet works again offline VPN."""
    cmds = windows_route_delete_commands(plan, server_host, if_index=if_index)
    applied, _ = _run_cmds(cmds)
    return applied


def stop_full_tunnel(
    result: Optional[WindowsTunnelResult] = None,
    client: Optional[RptClient] = None,
    plan: Optional[FullTunnelPlan] = None,
    server_host: Optional[str] = None,
    if_index: Optional[int] = None,
    *,
    disconnect_session: bool = True,
    preserve_message: bool = False,
) -> list[str]:
    """Idempotent full teardown: routes → dataplane → TUN → RPT session.

    Order restores the physical path first (delete dual /1 + server pin), then
    stops the DATA plane and closes Wintun so the machine reverts to the real
    device IP path. Safe when already stopped or never connected.

    When ``preserve_message`` is True (cleanup after a failed Connect attach),
    do not overwrite ``result.message`` with the teardown success string so the
    original attach failure can still be shown to the user.
    """
    applied: list[str] = []
    res = result
    plane = res.dataplane if res is not None else None
    tun = res.tun if res is not None else None
    routes_were_on = bool(res and res.routes_applied)
    plan_obj = plan or (res.plan if res else None)
    host = server_host or (res.server_host if res else None)
    idx = if_index if if_index is not None else (res.if_index if res else None)

    # 1) Remove full-tunnel routes first so traffic leaves the VPN immediately.
    if host and (routes_were_on or plan_obj is not None):
        try:
            p = plan_obj or build_placeholder_plan()
            applied.extend(rollback_full_tunnel_routes(p, host, idx))
        except Exception:
            # Best-effort: still continue teardown
            try:
                cmds = windows_route_delete_commands(
                    plan_obj or build_placeholder_plan(), host, idx
                )
                applied.extend(cmds)
            except Exception:
                pass

    # 1b) Restore IPv6 on physical adapters (undo session leak mitigation)
    if res is not None and (
        getattr(res, "ipv6_mitigation_applied", False) or routes_were_on
    ):
        try:
            applied.extend(rollback_ipv6_leak_mitigation(plan_obj))
        except Exception:
            pass
        try:
            res.ipv6_mitigation_applied = False
        except Exception:
            pass

    # 1c) Kill-switch firewall rollback (non-tunnel block)
    if routes_were_on or (res is not None and getattr(res, "kill_switch_applied", False)):
        try:
            from client.kill_switch import windows_kill_switch_rollback_commands

            for cmd in windows_kill_switch_rollback_commands():
                try:
                    # best-effort shell
                    import subprocess

                    subprocess.run(cmd, shell=True, capture_output=True, timeout=15)
                    applied.append(cmd)
                except Exception:
                    pass
            if res is not None:
                res.kill_switch_applied = False
        except Exception:
            pass

    # 2) Stop sealed DATA plane (also closes TUN if bound)
    if plane is not None:
        try:
            plane.stop()
        except Exception:
            pass

    # 3) Close TUN adapter if still open
    if tun is not None:
        try:
            tun.close()
        except Exception:
            pass

    # 4) End RPT session / UDP socket
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
            res.message = "tunnel stopped — full teardown complete"

    return applied


def build_placeholder_plan() -> FullTunnelPlan:
    """Minimal plan for route-delete when only host is known."""
    return FullTunnelPlan(
        tunnel_iface="RPT",
        tunnel_client_ip="10.88.0.2",
    )


def product_tunnel_attach_active(result: Optional[WindowsTunnelResult]) -> bool:
    """True when session dataplane is bound to a TUN (queue or Wintun).

    Residual public IP may still use the ISP path unless residual_ip_capture_active.
    """
    if result is None or not result.ok:
        return False
    if result.dataplane is None:
        return False
    try:
        return bool(result.dataplane.is_running())
    except Exception:
        return True


def residual_ip_capture_active(result: Optional[WindowsTunnelResult]) -> bool:
    """True only when device residual public IP can change via full tunnel.

    Requires system-capture TUN + dual /1 routes applied + dataplane — not
    handshake-only or in-process queue dataplane.
    """
    if result is None:
        return False
    return bool(
        result.ok
        and result.routes_applied
        and result.system_capture
        and result.dataplane is not None
    )


def ipv6_residual_protected(result: Optional[WindowsTunnelResult]) -> bool:
    """True when residual full tunnel also blocked ISP IPv6 egress for the session."""
    if not residual_ip_capture_active(result):
        return False
    return bool(result and result.ipv6_mitigation_applied)


def _cmd_exit_ok(returncode: int, stderr: str, stdout: str) -> bool:
    """True only when the process succeeded (or route 'already exists' benign)."""
    return _route_cmd_succeeded(returncode, stderr, stdout)


def apply_ipv6_leak_mitigation(plan: FullTunnelPlan) -> tuple[list[str], bool]:
    """Run IPv6 ISP-block commands; return (successful_cmds, mitigation_ok).

    ``mitigation_ok`` is True only when the **critical** verified PowerShell
    disable reports ``RPT_IPV6_DISABLED>=1`` and exit 0 (see
    ``parse_windows_ipv6_disable_result``). Zero-effect runs (SilentlyContinue /
    empty ForEach / all disables failed) yield ``ok=False`` even if process
    exit were 0 without a positive count. Transition tech is best-effort only.
    """
    from client.full_tunnel import (
        parse_windows_ipv6_disable_result,
        windows_ipv6_disable_powershell,
    )

    cmds = windows_ipv6_leak_block_commands(tunnel_iface=plan.tunnel_iface or "RPT")
    critical_ps = windows_ipv6_disable_powershell(
        tunnel_iface=plan.tunnel_iface or "RPT"
    )
    successful: list[str] = []
    critical_ok = False
    for cmd in cmds:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        is_critical = cmd.strip() == critical_ps.strip() or (
            "Disable-NetAdapterBinding" in cmd and "RPT_IPV6_DISABLED" in cmd
        )
        if is_critical:
            ok, _count = parse_windows_ipv6_disable_result(
                r.returncode, r.stdout or "", r.stderr or ""
            )
            if ok:
                successful.append(cmd)
                critical_ok = True
            # failed critical: do not append as success, leave critical_ok False
            continue
        if not _cmd_exit_ok(r.returncode, r.stderr or "", r.stdout or ""):
            continue
        successful.append(cmd)
    return successful, critical_ok


def rollback_ipv6_leak_mitigation(plan: Optional[FullTunnelPlan] = None) -> list[str]:
    """Restore IPv6 bindings after Disconnect (best-effort; only list successes)."""
    iface = (plan.tunnel_iface if plan else None) or "RPT"
    cmds = windows_ipv6_leak_rollback_commands(tunnel_iface=iface)
    successful: list[str] = []
    for cmd in cmds:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if _cmd_exit_ok(r.returncode, r.stderr or "", r.stdout or ""):
            successful.append(cmd)
    return successful


def start_full_tunnel(
    client: RptClient,
    plan: FullTunnelPlan,
    server_host: str,
    dry_run: bool = False,
    force_queue: bool = False,
    prefer_system_capture: bool = True,
    *,
    require_system_capture: bool = False,
) -> WindowsTunnelResult:
    """Create OS TUN (Wintun), install safe full-tunnel routes, start DATA plane.

    Never applies dual /1 without system-capture TUN + valid IF index.

    Product residual-IP path (``require_system_capture=True``): refuses queue-only
    fallback — residual public IP only changes with real Wintun + dual /1.
    When False, Wintun is preferred but queue TUN may start session dataplane
    without changing residual public IP.
    """
    if not client.session:
        return WindowsTunnelResult(False, "no session", [])

    # Normalize Windows adapter name (avoid Linux-style rpt0)
    if not plan.tunnel_iface or plan.tunnel_iface.lower().startswith("rpt0"):
        plan.tunnel_iface = "RPT"

    if dry_run:
        cmds = windows_route_commands(plan, server_host, if_index=42)
        return WindowsTunnelResult(
            ok=True,
            message="dry-run full tunnel plan",
            applied_commands=cmds,
            system_capture=False,
            routes_applied=False,
            plan=plan,
            server_host=server_host,
            if_index=42,
        )

    # Residual public IP needs admin for Wintun + dual /1
    if require_system_capture and not force_queue and not is_admin():
        return WindowsTunnelResult(
            False,
            "Administrator required so device traffic uses the VPN node "
            "(Wintun + dual /1 routes). Approve UAC when prompted.",
            [],
            plan=plan,
            server_host=server_host,
        )

    wintun_note = ""
    try:
        tun = create_windows_tun(
            client_ip=plan.tunnel_client_ip,
            name=plan.tunnel_iface or "RPT",
            force_queue=force_queue,
            prefer_system_capture=prefer_system_capture and not force_queue,
        )
    except Exception as exc:
        # Queue fallback only when residual capture is not required
        if force_queue or not require_system_capture:
            try:
                tun = create_windows_tun(
                    client_ip=plan.tunnel_client_ip,
                    name=plan.tunnel_iface or "RPT",
                    force_queue=True,
                )
                wintun_note = f" (Wintun unavailable: {exc}; using in-process dataplane)"
            except Exception as e2:
                return WindowsTunnelResult(
                    False,
                    f"TUN failed: {exc}; queue fallback also failed: {e2}",
                    [],
                    plan=plan,
                    server_host=server_host,
                )
        else:
            return WindowsTunnelResult(
                False,
                f"Wintun TUN failed: {exc}. Residual public IP change needs "
                "Administrator and a working Wintun adapter.",
                [],
                plan=plan,
                server_host=server_host,
            )

    plan.tunnel_iface = tun.name
    applied: list[str] = []

    try:
        applied.extend(tun.configure_address())
    except Exception as exc:
        tun.close()
        return WindowsTunnelResult(False, f"configure_address failed: {exc}", applied)

    # Allow Windows to register the adapter before IF index query
    time.sleep(0.4)

    capture = system_capture_ready(tun)
    if_index: Optional[int] = None
    if capture:
        if_index = tun.interface_index() if hasattr(tun, "interface_index") else None
        if if_index is None:
            if_index = resolve_interface_index(tun.name)
        # Retry IF lookup once
        if if_index is None:
            time.sleep(0.5)
            if_index = resolve_interface_index(tun.name)

    route_msg = "routes skipped"
    routes_applied = False

    if routes_would_blackhole_without_system_capture(capture, True):
        route_msg = "no OS TUN capture — full-tunnel routes NOT applied (prevents blackhole)"
    elif routes_would_blackhole_without_if_index(if_index, True):
        # Server pin only (keep UDP path); no dual /1
        if is_admin():
            cmds, errs, _pin_ok = apply_routes_for_adapter(
                plan, server_host, if_index=None, include_catchall=False
            )
            applied.extend(cmds)
        route_msg = (
            "refused dual /1: no Wintun IF index (would ARP-blackhole via 10.88.0.1); "
            "session up but not full-tunnel — check adapter name / admin"
        )
        routes_applied = False
    elif is_admin() and capture and if_index is not None:
        cmds, errs, full_ok = apply_routes_for_adapter(
            plan, server_host, if_index=if_index, include_catchall=True
        )
        applied.extend(cmds)
        if full_ok:
            routes_applied = True
            route_msg = f"full-tunnel routes applied (IF={if_index}, server pinned)"
            # Non-critical netsh warnings only
            warns = [e for e in errs if e.startswith("setup warn:")]
            if warns:
                route_msg += f" ({len(warns)} warn)"
        else:
            routes_applied = False
            route_msg = "routes refused (pin/catchall failed; rolled back): " + (
                "; ".join(errs) if errs else "unknown"
            )
            # apply_routes_for_adapter already rolls back on full_ok=False
    elif is_admin():
        route_msg = "admin but no OS TUN — routes not applied (would blackhole)"
    else:
        route_msg = (
            "standard user — system-wide dual /1 skipped "
            "(session + dataplane start without Administrator)"
        )

    from client.product_policy import product_dataplane_traffic_shape

    plane = RptDataPlane(client, traffic_shape=product_dataplane_traffic_shape())
    try:
        plane.start(tun)
    except Exception as exc:
        if routes_applied:
            rollback_full_tunnel_routes(plan, server_host, if_index)
        tun.close()
        return WindowsTunnelResult(
            False, f"dataplane start failed: {exc}", applied, routes_applied=False
        )

    if not dataplane_enabled(tun) or not plane.is_running():
        plane.stop()
        if routes_applied:
            rollback_full_tunnel_routes(plan, server_host, if_index)
        tun.close()
        return WindowsTunnelResult(
            False,
            "dataplane failed — full-tunnel routes rolled back (prevents blackhole)",
            applied,
            tun=None,
            routes_applied=False,
        )

    msg = (
        f"TUN mode={tun.mode}; {route_msg}; dataplane running (sealed RPT DATA); "
        f"system_capture={capture}; if_index={if_index}; "
        f"wintun_dll={wintun_dll_available()}"
        f"{wintun_note}"
    )
    if routes_applied and (
        not capture or routes_would_blackhole_without_if_index(if_index, True)
    ):
        plane.stop()
        rollback_full_tunnel_routes(plan, server_host, if_index)
        tun.close()
        return WindowsTunnelResult(
            False,
            "refused: full-tunnel routes without IF-bound capture would blackhole internet",
            applied,
            routes_applied=False,
        )

    ipv6_ok = False
    if routes_applied and capture:
        try:
            v6_cmds, ipv6_ok = apply_ipv6_leak_mitigation(plan)
            applied.extend(v6_cmds)
            if ipv6_ok:
                msg += "; IPv6 ISP path blocked"
            else:
                msg += "; IPv6 leak mitigation incomplete"
        except Exception as exc:
            msg += f"; IPv6 mitigation error: {exc}"
            ipv6_ok = False

    ks_applied = False
    if routes_applied and capture:
        try:
            from client.kill_switch import (
                build_kill_switch_plan,
                product_kill_switch_enabled,
                run_kill_switch_commands,
            )

            if product_kill_switch_enabled():
                ks = build_kill_switch_plan(
                    "windows",
                    server_host=server_host,
                    tunnel_iface=plan.tunnel_iface or "RPT",
                )
                ran, ok, errs = run_kill_switch_commands(
                    ks.apply, shell=True, platform="windows"
                )
                applied.extend(ran)
                # Only claim kill-switch on when critical rules actually installed
                ks_applied = bool(ok)
                if ks_applied:
                    msg += "; kill-switch on"
                elif ks.apply:
                    detail = (errs[0] if errs else "rules not verified")
                    msg += f"; kill-switch incomplete ({detail})"
        except Exception as exc:
            msg += f"; kill-switch incomplete: {exc}"
            ks_applied = False

    result = WindowsTunnelResult(
        ok=True,
        message=msg,
        applied_commands=applied,
        tun=tun,
        dataplane=plane,
        system_capture=capture,
        routes_applied=routes_applied,
        plan=plan,
        server_host=server_host,
        if_index=if_index,
        ipv6_mitigation_applied=ipv6_ok,
        kill_switch_applied=ks_applied,
    )

    # Product residual-IP path: refuse queue/session-only success (ISP IP unchanged)
    if require_system_capture and not residual_ip_capture_active(result):
        plane.stop()
        if routes_applied:
            rollback_full_tunnel_routes(plan, server_host, if_index)
        if ipv6_ok:
            try:
                rollback_ipv6_leak_mitigation(plan)
            except Exception:
                pass
        try:
            tun.close()
        except Exception:
            pass
        return WindowsTunnelResult(
            False,
            "Could not route device traffic via the VPN node "
            f"(need Wintun + dual /1; system_capture={capture}, "
            f"routes_applied={routes_applied}, if_index={if_index}). {route_msg}",
            applied,
            routes_applied=False,
            plan=plan,
            server_host=server_host,
            if_index=if_index,
            ipv6_mitigation_applied=False,
        )

    return result


def apply_full_tunnel_routes(
    plan: FullTunnelPlan,
    server_host: str,
    dry_run: bool = False,
    if_index: Optional[int] = None,
) -> WindowsTunnelResult:
    """Apply route table only (adapter must already exist)."""
    if routes_would_blackhole_without_if_index(if_index, True):
        return WindowsTunnelResult(
            False,
            "refused: if_index required for dual /1 (ARP blackhole otherwise)",
            windows_route_commands(plan, server_host, if_index=None, include_catchall=False),
            routes_applied=False,
        )
    cmds = windows_route_commands(plan, server_host, if_index=if_index)
    gw = physical_default_gateway() or "0.0.0.0"
    cmds = [c.replace("PHYSICAL_GW", gw) for c in cmds]
    if dry_run or not is_admin():
        return WindowsTunnelResult(
            ok=bool(dry_run),
            message="dry-run or non-admin",
            applied_commands=cmds,
        )
    applied, errs, full_ok = apply_routes_for_adapter(
        plan, server_host, if_index=if_index
    )
    return WindowsTunnelResult(
        ok=full_ok,
        message=(
            "routes applied"
            if full_ok
            else "routes refused (pin/catchall): " + "; ".join(errs)
        )
        + (f" warnings={errs}" if full_ok and errs else ""),
        applied_commands=applied,
        routes_applied=full_ok,
    )
