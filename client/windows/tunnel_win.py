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


# Continuity constraint ∇_μ(ρ_t u^μ)=0 on residual attach: no fixed sleep "density"
# backlog after Wintun create — poll IF index and return as soon as flux is ready.
# Max wait ≥ legacy sleep(0.4)+sleep(0.5) so late-registering adapters still succeed;
# poll interval keeps cold path returning ASAP when the index is already queryable.
LEGACY_ADAPTER_SETTLE_TOTAL_SEC = 0.9  # historical fixed 0.4s + 0.5s
DEFAULT_ADAPTER_SETTLE_MAX_SEC = LEGACY_ADAPTER_SETTLE_TOTAL_SEC
DEFAULT_ADAPTER_SETTLE_POLL_SEC = 0.05


def adapter_settle_budget(
    *,
    max_sec: float | None = None,
    poll_sec: float | None = None,
) -> tuple[float, float]:
    """Pure budget for Wintun IF settle: (max_wait, poll_interval).

    Max wait is at least the legacy total (~0.9s) so adapters that only become
    queryable mid-window still resolve. Poll + early return removes fixed ρ
    when the IF index is ready immediately or early in the window.
    """
    mx = DEFAULT_ADAPTER_SETTLE_MAX_SEC if max_sec is None else float(max_sec)
    pl = DEFAULT_ADAPTER_SETTLE_POLL_SEC if poll_sec is None else float(poll_sec)
    if mx < 0:
        mx = 0.0
    if pl <= 0:
        pl = DEFAULT_ADAPTER_SETTLE_POLL_SEC
    if pl > mx and mx > 0:
        pl = mx
    return mx, pl


def wait_for_wintun_if_index(
    tun: "WindowsTun",
    *,
    max_sec: float | None = None,
    poll_sec: float | None = None,
    sleep_fn=None,
    monotonic_fn=None,
) -> Optional[int]:
    """Resolve Wintun IF index ASAP — poll instead of fixed multi-sleep backlog.

    Continuity: ρ (wait mass) does not accumulate past readiness; returns on first
    successful index. One resolve per poll only (``interface_index`` already wraps
    ``resolve_interface_index`` on WindowsTun — do not double-call).

    ``sleep_fn`` / ``monotonic_fn`` injectables for unit tests.
    """
    max_wait, poll = adapter_settle_budget(max_sec=max_sec, poll_sec=poll_sec)
    sleeper = time.sleep if sleep_fn is None else sleep_fn
    clock = time.monotonic if monotonic_fn is None else monotonic_fn
    deadline = clock() + max_wait
    name = getattr(tun, "name", None) or "RPT"

    def _try() -> Optional[int]:
        # Single resolve path per poll. WindowsTun.interface_index → resolve once.
        if hasattr(tun, "interface_index") and callable(tun.interface_index):
            try:
                return tun.interface_index()
            except Exception:
                return None
        return resolve_interface_index(name)

    idx = _try()
    if idx is not None:
        return idx
    while clock() < deadline:
        sleeper(poll)
        idx = _try()
        if idx is not None:
            return idx
    return _try()


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
    physical_gw: Optional[str] = None,
) -> tuple[list[str], list[str], bool]:
    """Apply address/DNS, server pin, then dual /1 only if pin succeeded.

    Returns ``(applied_cmds, errors, full_tunnel_ok)``.

    **Critical:** dual /1 catch-alls are **not** installed if the server pin
    fails — otherwise UDP to the node is trapped inside the tunnel (recursive
    blackhole) while the UI still claims "server pinned".

    ``physical_gw`` may be prefetched while HELLO runs (overlap cold attach).
    """
    cmds = windows_route_commands(
        plan, server_host, if_index=if_index, include_catchall=include_catchall
    )
    gw = physical_gw or physical_default_gateway()
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


# Shell timeout for idempotent residual teardown cmds (route delete / KS no-ops).
# Was 20s — hung Disconnect/Quit when netsh/PowerShell stalled; 5s is enough to fail soft.
RESIDUAL_RESTORE_CMD_TIMEOUT_S = 5.0


def residual_restore_cmd_timeout_s() -> float:
    """Bounded timeout for residual restore shell commands (Disconnect/Quit)."""
    return float(RESIDUAL_RESTORE_CMD_TIMEOUT_S)


def restore_windows_residual_path(
    *,
    server_host: Optional[str] = None,
    plan: Optional[FullTunnelPlan] = None,
    if_index: Optional[int] = None,
    run_kill_switch_rollback: bool = True,
    run_ipv6_rollback: bool = True,
    reapply_fw_allows: bool = True,
) -> list[str]:
    """Always attempt residual restore so Disconnect/Quit never leave a blackhole.

    Does **not** depend on ``routes_applied`` / ``kill_switch_applied`` flags.
    Safe and idempotent when residual was never applied (route delete no-ops).

    *reapply_fw_allows*: when False, skip RPT-FW re-apply (use on post-TUN race
    second pass after a full restore already re-applied allows).
    """
    applied: list[str] = []
    try:
        from client.endpoint import PRODUCT_NODE_HOST
        from client.full_tunnel import windows_residual_restore_route_commands
    except Exception:
        PRODUCT_NODE_HOST = "82.221.101.241"  # type: ignore[misc,assignment]
        windows_residual_restore_route_commands = None  # type: ignore[assignment]

    host = (server_host or "").strip() or str(PRODUCT_NODE_HOST)
    cmd_timeout = residual_restore_cmd_timeout_s()

    # 1) Dual /1 + server pin (use plan-aware builder when available, else product defaults)
    try:
        if plan is not None:
            applied.extend(rollback_full_tunnel_routes(plan, host, if_index))
        elif windows_residual_restore_route_commands is not None:
            cmds = windows_residual_restore_route_commands(host)
            ran, _errs = _run_cmds(cmds)
            applied.extend(ran)
        else:
            p = build_placeholder_plan()
            applied.extend(rollback_full_tunnel_routes(p, host, if_index))
    except Exception:
        try:
            # Second chance: bare product residual deletes
            from client.full_tunnel import windows_residual_restore_route_commands as _wrr

            ran, _ = _run_cmds(_wrr(host))
            applied.extend(ran)
        except Exception:
            pass

    # 2) IPv6 bindings re-enabled (session may have disabled ms_tcpip6 on adapters)
    if run_ipv6_rollback:
        try:
            applied.extend(rollback_ipv6_leak_mitigation(plan))
        except Exception:
            pass

    # 3) Kill-switch: always roll back RPT-KS rules + DefaultOutboundAction
    if run_kill_switch_rollback:
        try:
            from client.kill_switch import windows_kill_switch_rollback_commands

            for cmd in windows_kill_switch_rollback_commands():
                try:
                    subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        timeout=cmd_timeout,
                    )
                    applied.append(cmd)
                except Exception:
                    pass
        except Exception:
            pass

    # 4) Re-apply scoped product Defender Firewall allows (RPT-FW-*) so residual
    # Connect is not left blocked after KS rollback / first install.
    if reapply_fw_allows:
        try:
            from client.windows.firewall_allow import apply_windows_fw_allows

            _ran, _ok, _errs = apply_windows_fw_allows(server_host=host)
            applied.extend(_ran)
        except Exception:
            pass

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
    """Idempotent full teardown: residual restore → dataplane → TUN → RPT session.

    Order restores the physical path first (delete dual /1 + server pin + KS +
    IPv6 undo), then stops the DATA plane and closes Wintun so the machine
    reverts to the real device IP path.

    Residual restore **always** runs (even when ``result`` is None or flags are
    incomplete) so Disconnect/Quit never leave dual ``/1`` or profile Block
    after the TUN is gone.

    When ``preserve_message`` is True (cleanup after a failed Connect attach),
    do not overwrite ``result.message`` with the teardown success string so the
    original attach failure can still be shown to the user.
    """
    applied: list[str] = []
    res = result
    plane = res.dataplane if res is not None else None
    tun = res.tun if res is not None else None
    plan_obj = plan or (res.plan if res else None)
    host = server_host or (res.server_host if res else None)
    idx = if_index if if_index is not None else (res.if_index if res else None)

    # 1) Full residual restore first (routes / KS / IPv6 / FW) — flag-independent.
    try:
        applied.extend(
            restore_windows_residual_path(
                server_host=host,
                plan=plan_obj,
                if_index=idx,
                run_kill_switch_rollback=True,
                run_ipv6_rollback=True,
                reapply_fw_allows=True,
            )
        )
    except Exception:
        pass
    if res is not None:
        try:
            res.ipv6_mitigation_applied = False
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

    # 3b) Route deletes only after TUN close (race: dual /1 may reappear briefly).
    # Do **not** re-run KS rollback or FW re-apply — already done in pass 1.
    try:
        applied.extend(
            restore_windows_residual_path(
                server_host=host,
                plan=plan_obj,
                if_index=idx,
                run_kill_switch_rollback=False,
                run_ipv6_rollback=False,
                reapply_fw_allows=False,
            )
        )
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
    prior: Optional[WindowsTunnelResult] = None,
    physical_gw: Optional[str] = None,
) -> WindowsTunnelResult:
    """Create OS TUN (Wintun), install safe full-tunnel routes, start DATA plane.

    Never applies dual /1 without system-capture TUN + valid IF index.

    Product residual-IP path (``require_system_capture=True``): refuses queue-only
    fallback — residual public IP only changes with real Wintun + dual /1.
    When False, Wintun is preferred but queue TUN may start session dataplane
    without changing residual public IP.

    If ``prior`` already has residual routes for the same plan IP, return it
    without re-installing dual /1. ``physical_gw`` may be prefetched during HELLO
    to shorten the residual attach path.
    """
    if not client.session:
        return WindowsTunnelResult(False, "no session", [])

    # Residual already applied for this session/plan (idempotent re-attach)
    if (
        prior is not None
        and prior.ok
        and prior.routes_applied
        and prior.system_capture
        and prior.plan is not None
        and prior.plan.tunnel_client_ip == plan.tunnel_client_ip
        and prior.server_host == server_host
        and not dry_run
        and not force_queue
    ):
        return WindowsTunnelResult(
            ok=True,
            message="residual already applied for this session",
            applied_commands=list(prior.applied_commands or []),
            tun=prior.tun,
            dataplane=prior.dataplane,
            system_capture=True,
            routes_applied=True,
            plan=plan,
            server_host=server_host,
            if_index=prior.if_index,
            ipv6_mitigation_applied=prior.ipv6_mitigation_applied,
            kill_switch_applied=prior.kill_switch_applied,
        )

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

    # Best-effort: scoped Defender Firewall allows for residual UDP + product exe
    # (does not enable kill-switch; safe Allow rules only).
    if is_admin():
        try:
            from client.windows.firewall_allow import apply_windows_fw_allows

            apply_windows_fw_allows(server_host=server_host)
        except Exception:
            pass

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

    # Continuity: poll for IF index ASAP (no fixed 0.4s + 0.5s sleep backlog).
    capture = system_capture_ready(tun)
    if_index: Optional[int] = None
    if capture:
        if_index = wait_for_wintun_if_index(tun)

    route_msg = "routes skipped"
    routes_applied = False

    if routes_would_blackhole_without_system_capture(capture, True):
        route_msg = "no OS TUN capture — full-tunnel routes NOT applied (prevents blackhole)"
    elif routes_would_blackhole_without_if_index(if_index, True):
        # Server pin only (keep UDP path); no dual /1
        if is_admin():
            cmds, errs, _pin_ok = apply_routes_for_adapter(
                plan,
                server_host,
                if_index=None,
                include_catchall=False,
                physical_gw=physical_gw,
            )
            applied.extend(cmds)
        route_msg = (
            "refused dual /1: no Wintun IF index (would ARP-blackhole via 10.88.0.1); "
            "session up but not full-tunnel — check adapter name / admin"
        )
        routes_applied = False
    elif is_admin() and capture and if_index is not None:
        cmds, errs, full_ok = apply_routes_for_adapter(
            plan,
            server_host,
            if_index=if_index,
            include_catchall=True,
            physical_gw=physical_gw,
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

    # Build provisional result *before* kill-switch. KS must only arm after
    # residual capture is proven — otherwise DefaultOutboundAction Block can
    # blackhole all internet if attach fails or residual is incomplete.
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
        kill_switch_applied=False,
    )

    # Product residual-IP path: refuse queue/session-only success (ISP IP unchanged)
    if require_system_capture and not residual_ip_capture_active(result):
        plane.stop()
        # Full residual restore (routes + KS rollback + re-apply RPT-FW allows).
        # Never leave dual /1 or profile DefaultOutboundAction=Block after fail.
        try:
            restore_windows_residual_path(
                server_host=server_host,
                plan=plan,
                if_index=if_index,
                run_kill_switch_rollback=True,
                run_ipv6_rollback=True,
            )
        except Exception:
            if routes_applied:
                try:
                    rollback_full_tunnel_routes(plan, server_host, if_index)
                except Exception:
                    pass
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
            kill_switch_applied=False,
        )

    # Kill-switch: PARKED for this build stage (product_kill_switch_enabled is
    # always False). Block retained for later un-park; never arms residual KS now.
    ks_applied = False
    if routes_applied and capture and residual_ip_capture_active(result):
        try:
            from client.kill_switch import (
                build_kill_switch_plan,
                product_kill_switch_enabled,
                run_kill_switch_commands,
            )

            if product_kill_switch_enabled():  # always False while parked
                ks = build_kill_switch_plan(
                    "windows",
                    server_host=server_host,
                    tunnel_iface=plan.tunnel_iface or "RPT",
                )
                ran, ok, errs = run_kill_switch_commands(
                    ks.apply, shell=True, platform="windows"
                )
                applied.extend(ran)
                result.applied_commands = list(applied)
                # Only claim kill-switch on when critical rules actually installed
                ks_applied = bool(ok)
                result.kill_switch_applied = ks_applied
                if ks_applied:
                    result.message = (result.message or msg) + "; kill-switch on"
                    # Re-assert product RPT-FW allows under profile Block defaults
                    try:
                        from client.windows.firewall_allow import apply_windows_fw_allows

                        apply_windows_fw_allows(server_host=server_host)
                    except Exception:
                        pass
                elif ks.apply:
                    detail = errs[0] if errs else "rules not verified"
                    result.message = (
                        (result.message or msg) + f"; kill-switch incomplete ({detail})"
                    )
                    # Incomplete KS may leave profiles blocked — roll back
                    try:
                        restore_windows_residual_path(
                            server_host=server_host,
                            plan=plan,
                            if_index=if_index,
                            run_kill_switch_rollback=True,
                            run_ipv6_rollback=False,
                        )
                    except Exception:
                        pass
        except Exception as exc:
            result.message = (result.message or msg) + f"; kill-switch incomplete: {exc}"
            ks_applied = False
            result.kill_switch_applied = False

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
