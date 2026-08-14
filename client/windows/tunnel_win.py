"""Windows full-tunnel: Wintun adapter + default routes + sealed RPT DATA plane.

Anti-blackhole:
- Dual /1 only with real Wintun + valid IF index + on-link next-hop 0.0.0.0
- Never next-hop 10.88.0.1 (ARP blackhole on Wintun)
- Server host pinned on physical GW before catch-alls
- Rollback catch-alls if setup fails or if_index missing
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
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
    windows_probe_host_route_commands,
    windows_probe_host_route_delete_commands,
    windows_route_commands,
    windows_route_delete_commands,
)
from client.windows.hidden_subprocess import (
    check_output_hidden,
    residual_shell_run,
    run_hidden,
)
from client.windows.tun_win import (
    WINDOWS_TUNNEL_DNS_PUBLIC as WINDOWS_TUNNEL_DNS_FALLBACK,
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
# Connect was 30–40s after HELLO because every netsh/route/PS used 30–45s
# timeouts and ran twice. Fail-fast; commands that work return in <2s.
RESIDUAL_ROUTE_CMD_TIMEOUT_S = 8.0
RESIDUAL_IPV6_CMD_TIMEOUT_S = 8.0


def residual_route_cmd_timeout_s() -> float:
    """Bounded timeout for route add / pin / catch-all shell commands."""
    return float(RESIDUAL_ROUTE_CMD_TIMEOUT_S)


def residual_ipv6_cmd_timeout_s() -> float:
    """Bounded timeout for IPv6 leak-mitigation shell commands."""
    return float(RESIDUAL_IPV6_CMD_TIMEOUT_S)


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
        out = check_output_hidden(
            ["route", "print", "0.0.0.0"],
            text=True,
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


def _is_tunnel_dns_dest_cmd(cmd: str, server_host: str) -> bool:
    """True for dest-on-link ``10.88.0.1/32 IF n`` (not the physical server pin)."""
    if "route add" not in cmd or "mask 255.255.255.255" not in cmd:
        return False
    if "IF " not in cmd:
        return False
    host = (server_host or "").strip()
    if host and host in cmd:
        return False
    return True


def _run_cmds(cmds: list[str]) -> tuple[list[str], list[str]]:
    """Run shell cmds; treat 'already exists' as success for route add."""
    applied: list[str] = []
    errors: list[str] = []
    for cmd in cmds:
        if "PHYSICAL_GW" in cmd:
            errors.append("physical gateway not substituted")
            continue
        r = residual_shell_run(cmd, timeout=residual_route_cmd_timeout_s(), text=True)
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
    from client.full_tunnel import plan_wants_ipv4_catchall

    # Honour Settings residual IPv4: empty plan.default_routes → no dual /1.
    effective_catchall = include_catchall and plan_wants_ipv4_catchall(plan)
    cmds = windows_route_commands(
        plan, server_host, if_index=if_index, include_catchall=effective_catchall
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
    catchall_wanted = (
        effective_catchall and if_index is not None and int(if_index) > 0
    )

    for cmd in cmds:
        if "PHYSICAL_GW" in cmd:
            errors.append(
                "physical gateway not substituted — refusing full-tunnel (would blackhole)"
            )
            return applied, errors, False

        is_pin = _is_server_pin_cmd(cmd, server_host)
        is_catch = _is_catchall_cmd(cmd)
        is_dns_dest = _is_tunnel_dns_dest_cmd(cmd, server_host)

        # Never install dual /1 / tunnel-DNS dest unless server pin already succeeded
        if (is_catch or is_dns_dest) and not pin_ok:
            errors.append(
                "server pin failed or missing — refusing dual /1 "
                "(would blackhole UDP to node via TUN)"
            )
            # Do not run this or further catch-alls
            continue

        r = residual_shell_run(cmd, timeout=residual_route_cmd_timeout_s(), text=True)
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
                    residual_shell_run(cmd, timeout=cmd_timeout, text=True)
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


def dataplane_is_live(plane: Optional[RptDataPlane]) -> bool:
    """True when residual dataplane object exists and reports running."""
    if plane is None:
        return False
    try:
        return bool(plane.is_running())
    except Exception:
        return False


def may_install_dual_slash1_catchalls(
    *,
    dataplane_running: bool,
    system_capture: bool,
    if_index: Optional[int],
    want_ipv4_catchall: bool,
) -> bool:
    """Pure gate: dual /1 only when live dataplane can forward + IF-bound capture.

    Installing dual /1 *before* the dataplane runs blackholes all host traffic into
    a TUN with no packet processor — the classic post-Connect “no internet” bug.
    """
    if not want_ipv4_catchall:
        return False
    if not dataplane_running:
        return False
    if not system_capture:
        return False
    if routes_would_blackhole_without_if_index(if_index, True):
        return False
    return True


def apply_windows_unicast_if(sock: object, if_index: Optional[int]) -> bool:
    """Bind *sock* to a Windows IF index (IP_UNICAST_IF). False if not applied."""
    if if_index is None:
        return False
    try:
        idx = int(if_index)
    except (TypeError, ValueError):
        return False
    if idx <= 0:
        return False
    import socket
    import struct

    opt = getattr(socket, "IP_UNICAST_IF", 31)
    try:
        sock.setsockopt(socket.IPPROTO_IP, opt, struct.pack("!I", idx))  # type: ignore[attr-defined]
        return True
    except Exception:
        return False


def residual_forward_udp_smoke(
    *,
    host: str = "1.1.1.1",
    port: int = 53,
    timeout: float = 1.5,
    bind_ip: Optional[str] = None,
    sock_factory: Optional[Callable[[], object]] = None,
) -> bool:
    """True when a UDP probe to a public IP gets any reply (NAT/forward check).

    TCP 443 through a brand-new Wintun /32 often times out even when DATA
    packets flow (``tun_to_udp`` high). UDP/53 is one packet each way.
    """
    import socket

    factory = sock_factory or (
        lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    )
    try:
        s = factory()
        try:
            bip = (bind_ip or "").strip()
            if bip:
                s.bind((bip, 0))
            s.settimeout(float(timeout))
            # Minimal DNS A query — any UDP reply (even SERVFAIL) proves NAT.
            s.sendto(b"\x00\x01\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00", (host, int(port)))
            data, _addr = s.recvfrom(512)
            return bool(data)
        finally:
            try:
                s.close()
            except Exception:
                pass
    except OSError:
        return False
    except Exception:
        return False


def residual_forward_path_smoke(
    *,
    host: str = "1.1.1.1",
    port: int = 443,
    timeout: float = 3.0,
    connect_fn: Optional[Callable[..., object]] = None,
    bind_ip: Optional[str] = None,
    if_index: Optional[int] = None,
    socket_cls: Optional[Callable[..., object]] = None,
    mode: str = "tcp",
) -> bool:
    """True when general IPv4 can leave the host to a public IP (post dual /1).

    Pure-IP TCP (no DNS) so a dead tunnel DNS resolver is not required. After dual
    /1 + dataplane, a working residual path must reach a public address through
    the tunnel NAT. Failure means dual /1 is a blackhole — callers must roll back
    and must not claim residual Connected / protected.

    When *bind_ip* / *if_index* are set, the probe is sourced on the Wintun
    address so node ``on_tun`` can map the reply to the residual session
    (unbound ``create_connection`` often uses the physical NIC source on a /32).
    """
    import socket

    if str(mode or "tcp").strip().lower() == "udp" and connect_fn is None:
        udp_port = 53 if int(port) == 443 else int(port)
        return residual_forward_udp_smoke(
            host=str(host),
            port=udp_port,
            timeout=float(timeout),
            bind_ip=bind_ip,
        )

    if connect_fn is not None:
        open_tcp = connect_fn
        try:
            sock = open_tcp((host, int(port)), float(timeout))
            try:
                close = getattr(sock, "close", None)
                if callable(close):
                    close()
            except Exception:
                pass
            return True
        except OSError:
            return False
        except Exception:
            return False

    factory = socket_cls or socket.socket
    try:
        sock = factory(socket.AF_INET, socket.SOCK_STREAM)
        try:
            bip = (bind_ip or "").strip()
            if bip:
                sock.bind((bip, 0))
            else:
                apply_windows_unicast_if(sock, if_index)
            sock.settimeout(float(timeout))
            sock.connect((str(host), int(port)))
            return True
        finally:
            try:
                sock.close()
            except Exception:
                pass
    except OSError:
        return False
    except Exception:
        return False


def residual_tunnel_dns_smoke(
    *,
    dns_host: str = "10.88.0.1",
    qname: str = "example.com",
    timeout: float = 3.0,
    sock_factory: Optional[Callable[[], object]] = None,
    bind_ip: Optional[str] = None,
    if_index: Optional[int] = None,
) -> bool:
    """True when tunnel DNS (product default 10.88.0.1) answers an A query.

    Dual /1 + live dataplane can still leave the user with “no internet” when
    Unbound on the residual node refuses tunnel clients. Post-attach must not
    claim residual capture without working tunnel DNS.
    """
    import socket
    import struct

    name = (qname or "example.com").strip().rstrip(".")
    if not name or not (dns_host or "").strip():
        return False
    # Minimal recursive A query
    tid = 0xA11C  # fixed non-zero transaction id
    header = struct.pack("!HHHHHH", tid, 0x0100, 1, 0, 0, 0)
    q = b""
    for label in name.split("."):
        try:
            raw = label.encode("ascii")
        except UnicodeEncodeError:
            try:
                raw = label.encode("idna")
            except Exception:
                return False
        if not raw or len(raw) > 63:
            return False
        q += bytes([len(raw)]) + raw
    q += b"\x00" + struct.pack("!HH", 1, 1)
    packet = header + q
    factory = sock_factory or (lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
    try:
        s = factory()
        try:
            bip = (bind_ip or "").strip()
            if bip:
                s.bind((bip, 0))
            else:
                apply_windows_unicast_if(s, if_index)
            s.settimeout(float(timeout))
            s.sendto(packet, (str(dns_host).strip(), 53))
            data, _addr = s.recvfrom(512)
        finally:
            try:
                s.close()
            except Exception:
                pass
        if not data or len(data) < 12:
            return False
        # RCODE 0 = NOERROR; require at least one question echoed
        rcode = data[3] & 0x0F
        qd = int.from_bytes(data[4:6], "big")
        an = int.from_bytes(data[6:8], "big")
        return rcode == 0 and qd >= 1 and an >= 1
    except OSError:
        return False
    except Exception:
        return False


def residual_post_attach_ready(
    *,
    routes_applied: bool,
    dataplane_running: bool,
    keepalive_ok: bool,
    forward_path_ok: bool,
    dns_ok: bool = True,
    require_forward_smoke: bool = True,
    require_dns_smoke: bool = True,
    dataplane_return_ok: bool = False,
) -> bool:
    """Pure gate: residual capture may stay installed only when attach is healthy.

    Live dataplane + keepalive are always required after dual /1. OS smokes to
    1.1.1.1 / node Unbound have been false-negatives (desktop ``tun=150/12``
    then rollback). A real DATA reply (``udp_to_tun >= 1``) is enough to stay
    Connected. Rollback only when pin/dataplane die or nothing returns.
    """
    if not routes_applied:
        # Pin-only / session-only — not residual capture; health of dual /1 N/A
        return True
    if not dataplane_running:
        return False
    if not keepalive_ok:
        return False
    if dataplane_return_ok:
        return True
    # Live attach waives 1.1.1.1 / Unbound smokes. Without a DATA reply that
    # is a Connected blackhole (dual /1 up, udp_to_tun=0).
    if not require_forward_smoke and not require_dns_smoke:
        return False
    if require_forward_smoke and not forward_path_ok:
        return False
    if require_dns_smoke and not dns_ok:
        return False
    return True


def residual_attach_diag(
    plane: object,
    *,
    if_index: Optional[int],
    bind_ip: str,
    forward_ok: bool,
    dns_ok: bool,
) -> str:
    """Compact attach failure line (fits support-log export)."""
    st = getattr(plane, "stats", None)
    src = getattr(st, "first_tun_src", "") or "-"
    dst = getattr(st, "first_tun_dst", "") or "-"
    return (
        "tun={tu}/{ut} rw={rw} skip={sk} pkt={src}>{dst} if={ifx} bind={bip} "
        "fwd={fwd} dns={dns} err={err}".format(
            tu=getattr(st, "tun_to_udp", "?"),
            ut=getattr(st, "udp_to_tun", "?"),
            rw=getattr(st, "source_rewrites", 0),
            sk=getattr(st, "skipped_non_unicast", 0),
            src=src,
            dst=dst,
            ifx=if_index,
            bip=bind_ip or "-",
            fwd=int(bool(forward_ok)),
            dns=int(bool(dns_ok)),
            err=getattr(st, "errors", "?"),
        )
    )


def residual_wait_tunnel_ip_bindable(
    bind_ip: Optional[str],
    *,
    timeout: float = 4.0,
    poll_s: float = 0.2,
    socket_cls: Optional[Callable[..., object]] = None,
    sleep_fn: Optional[Callable[[float], None]] = None,
    clock_fn: Optional[Callable[[], float]] = None,
) -> bool:
    """True when *bind_ip* can be bound (Wintun address is preferred, not DAD)."""
    import socket

    ip = (bind_ip or "").strip()
    if not ip:
        return False
    factory = socket_cls or socket.socket
    sleeper = time.sleep if sleep_fn is None else sleep_fn
    clock = time.monotonic if clock_fn is None else clock_fn
    deadline = clock() + max(0.0, float(timeout))
    while True:
        sock = None
        try:
            sock = factory(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((ip, 0))
            return True
        except OSError:
            pass
        except Exception:
            pass
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
        if clock() >= deadline:
            return False
        sleeper(max(0.05, float(poll_s)))


def residual_wait_dataplane_return(
    plane: object,
    *,
    timeout: float = 4.0,
    poll_s: float = 0.2,
    inject_fn: Optional[Callable[[], None]] = None,
    sleep_fn: Optional[Callable[[float], None]] = None,
    clock_fn: Optional[Callable[[], float]] = None,
    min_udp_to_tun: int = 1,
) -> bool:
    """True when the residual dataplane has received at least one DATA reply.

    OS 1.1.1.1 / Unbound smokes can fail while Wintun is actually moving
    packets (desktop ``tun=150/12``). After pin + dual /1, wait for
    ``udp_to_tun`` instead of treating those dests as a hard gate.
    """
    sleeper = time.sleep if sleep_fn is None else sleep_fn
    clock = time.monotonic if clock_fn is None else clock_fn
    start = clock()
    deadline = start + max(0.0, float(timeout))
    injected = 0
    while True:
        st = getattr(plane, "stats", None)
        got = int(getattr(st, "udp_to_tun", 0) or 0)
        if got >= int(min_udp_to_tun):
            return True
        now = clock()
        if now >= deadline:
            return False
        if inject_fn is not None and injected < 2:
            half = start + (max(0.0, float(timeout)) * 0.45)
            if injected == 0 or now >= half:
                try:
                    inject_fn()
                except Exception:
                    pass
                injected += 1
        sleeper(max(0.05, float(poll_s)))


def residual_choose_tunnel_dns(*, unbound_ok: bool) -> list[str]:
    """Keep node Unbound when it answers; otherwise public DNS through the tunnel."""
    from client.windows.tun_win import wintun_attach_dns_servers

    return wintun_attach_dns_servers(unbound_ok=unbound_ok)


def residual_apply_windows_tunnel_dns(
    iface: str,
    servers: list[str],
    *,
    run_fn: Optional[Callable[..., object]] = None,
) -> list[str]:
    """Stamp interface DNS + flush cache. Never blocks attach on resolver probes."""
    from client.windows.tun_win import wintun_dns_commands

    name = (iface or "RPT").strip() or "RPT"
    addrs = [str(s).strip() for s in servers if str(s).strip()]
    cmds = wintun_dns_commands(name, addrs)
    if addrs:
        quoted = ", ".join(f"'{a}'" for a in addrs)
        cmds.append(
            "powershell -NoProfile -NonInteractive -Command "
            f"Set-DnsClientServerAddress -InterfaceAlias '{name}' "
            f"-ServerAddresses @({quoted})"
        )
    cmds.append("ipconfig /flushdns")
    runner = residual_shell_run if run_fn is None else run_fn
    for c in cmds:
        try:
            runner(c, timeout=5.0, text=True)
        except TypeError:
            try:
                runner(c)
            except Exception:
                pass
        except Exception:
            pass
    return cmds


def residual_run_post_attach_smokes(
    *,
    bind_ip: Optional[str] = None,
    if_index: Optional[int] = None,
    dns_host: str = "10.88.0.1",
    timeout: float = 2.5,
    attempts: int = 3,
    gap_s: float = 0.4,
    sleep_fn: Optional[Callable[[float], None]] = None,
    forward_fn: Optional[Callable[[], bool]] = None,
    dns_fn: Optional[Callable[[], bool]] = None,
    dataplane_running: bool = True,
    keepalive_ok: bool = True,
) -> tuple[bool, bool, bool]:
    """Retry forward + tunnel-DNS smokes after dual /1 settle.

    Returns ``(ready, forward_ok, dns_ok)``. Still fail-closed when the last
    attempt has a dead forward or DNS path.
    """
    sleeper = time.sleep if sleep_fn is None else sleep_fn
    bind = (bind_ip or "").strip() or None
    dns = (dns_host or "").strip() or "10.88.0.1"

    def _fwd() -> bool:
        if forward_fn is not None:
            return bool(forward_fn())
        return residual_forward_path_smoke(
            timeout=float(timeout),
            bind_ip=bind,
            if_index=if_index,
            mode="udp",
        )

    def _dns() -> bool:
        if dns_fn is not None:
            return bool(dns_fn())
        return residual_tunnel_dns_smoke(
            timeout=float(timeout),
            bind_ip=bind,
            if_index=if_index,
            dns_host=dns,
        )

    n = max(1, int(attempts))
    fwd_ok = False
    dns_ok = False
    for i in range(n):
        fwd_ok = _fwd()
        dns_ok = _dns()
        ready = residual_post_attach_ready(
            routes_applied=True,
            dataplane_running=bool(dataplane_running),
            keepalive_ok=bool(keepalive_ok),
            forward_path_ok=fwd_ok,
            dns_ok=dns_ok,
        )
        if ready:
            return True, fwd_ok, dns_ok
        if i + 1 < n:
            sleeper(float(gap_s))
    return False, fwd_ok, dns_ok


def residual_ip_capture_active(result: Optional[WindowsTunnelResult]) -> bool:
    """True only when device residual public IP can change via full tunnel.

    Requires system-capture TUN + dual /1 routes applied + **live** dataplane —
    not handshake-only, pin-only, stopped plane, liveness-lost idle death, or
    Settings residual IPv4 OFF.
    """
    if result is None:
        return False
    plane = result.dataplane
    if plane is not None:
        try:
            if bool(getattr(plane.stats, "session_liveness_lost", False)):
                return False
        except Exception:
            pass
    from client.residual_stack import residual_ip_capture_from_fields

    return residual_ip_capture_from_fields(
        ok=bool(result.ok),
        routes_applied=bool(result.routes_applied),
        system_capture=bool(result.system_capture),
        has_dataplane=dataplane_is_live(plane),
        plan=getattr(result, "plan", None),
    )


def session_ok_without_residual_capture(
    result: Optional[WindowsTunnelResult],
) -> bool:
    """True when tunnel session is up but Settings residual IPv4 is intentionally OFF.

    Connect must stay connected (session-only honesty) — do not tear down as failure.
    """
    if result is None:
        return False
    from client.residual_stack import session_only_from_fields

    return session_only_from_fields(
        ok=bool(result.ok),
        has_dataplane=dataplane_is_live(result.dataplane),
        plan=getattr(result, "plan", None),
    )


def reassert_server_pin_command(server_host: str, physical_gw: str) -> str:
    """route add for server pin (re-assert after dual /1 so UDP never loops into TUN)."""
    host = (server_host or "").strip()
    gw = (physical_gw or "").strip()
    return f"route add {host} mask 255.255.255.255 {gw} metric 1"


def reassert_server_pin(
    server_host: str,
    physical_gw: Optional[str] = None,
) -> tuple[list[str], bool]:
    """Best-effort re-add server pin after dual /1 (idempotent if already present)."""
    gw = (physical_gw or physical_default_gateway() or "").strip()
    if not gw or not (server_host or "").strip():
        return [], False
    cmd = reassert_server_pin_command(server_host, gw)
    r = residual_shell_run(cmd, timeout=residual_route_cmd_timeout_s(), text=True)
    ok = _route_cmd_succeeded(r.returncode, r.stderr or "", r.stdout or "")
    return [cmd], bool(ok)


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

    No-op when Settings IPv6 residual is off (``ipv6_leak_policy`` ≠ block_isp).

    ``mitigation_ok`` is True only when the **critical** verified PowerShell
    disable reports ``RPT_IPV6_DISABLED>=1`` and exit 0 (see
    ``parse_windows_ipv6_disable_result``). Zero-effect runs (SilentlyContinue /
    empty ForEach / all disables failed) yield ``ok=False`` even if process
    exit were 0 without a positive count. Transition tech is best-effort only.
    """
    from client.full_tunnel import (
        IPV6_LEAK_POLICY_BLOCK_ISP,
        parse_windows_ipv6_disable_result,
        windows_ipv6_disable_powershell,
    )

    # Settings IPv6 OFF → plan.ipv6_leak_policy is allow_isp; skip mitigation.
    if str(getattr(plan, "ipv6_leak_policy", "")) != IPV6_LEAK_POLICY_BLOCK_ISP:
        return [], False

    cmds = windows_ipv6_leak_block_commands(tunnel_iface=plan.tunnel_iface or "RPT")
    critical_ps = windows_ipv6_disable_powershell(
        tunnel_iface=plan.tunnel_iface or "RPT"
    )
    successful: list[str] = []
    critical_ok = False
    crit = critical_ps.strip()
    # Critical Disable-NetAdapterBinding first (quality). Teredo/6to4/isatap
    # are best-effort and must not add 30s+ after HELLO.
    ordered = [c for c in cmds if c.strip() == crit or (
        "Disable-NetAdapterBinding" in c and "RPT_IPV6_DISABLED" in c
    )]
    ordered.extend(c for c in cmds if c not in ordered)
    for cmd in ordered:
        is_critical = cmd.strip() == crit or (
            "Disable-NetAdapterBinding" in cmd and "RPT_IPV6_DISABLED" in cmd
        )
        budget = residual_ipv6_cmd_timeout_s() if is_critical else 2.0
        r = residual_shell_run(cmd, timeout=budget, text=True)
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
        r = residual_shell_run(cmd, timeout=residual_ipv6_cmd_timeout_s(), text=True)
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
    on_idle_session_drop: Optional[Callable[[], None]] = None,
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

    # Do not leave Wintun on silent Unbound — apply_routes emits plan.dns_servers.
    try:
        plan.dns_servers = residual_choose_tunnel_dns(unbound_ok=False)
    except Exception:
        plan.dns_servers = ["1.1.1.1", "9.9.9.9"]

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

    # Best-effort Defender allows. HELLO already proved residual UDP; do not
    # block Connected on Get-NetFirewallRule (often 10–30s). Run off-thread.
    if is_admin():
        try:
            import threading

            from client.windows.firewall_allow import apply_windows_fw_allows

            threading.Thread(
                target=apply_windows_fw_allows,
                kwargs={"server_host": server_host, "timeout": 8.0},
                name="rpt-fw-allow",
                daemon=True,
            ).start()
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

    # netsh address/DNS can bounce the NIC — open the Wintun ring only after that.
    start_io = getattr(tun, "start_io", None)
    if callable(start_io):
        try:
            start_io()
        except Exception as exc:
            tun.close()
            return WindowsTunnelResult(
                False, f"Wintun session failed after address config: {exc}", applied
            )

    # Continuity: poll for IF index ASAP (no fixed 0.4s + 0.5s sleep backlog).
    capture = system_capture_ready(tun)
    if_index: Optional[int] = None
    if capture:
        if_index = wait_for_wintun_if_index(tun)

    tunnel_ip = str(getattr(plan, "tunnel_client_ip", "") or "").strip()
    addr_ready = True
    real_wintun = bool(
        getattr(tun, "_session", None) or getattr(tun, "_adapter", None)
    )
    if capture and tunnel_ip and real_wintun:
        addr_ready = residual_wait_tunnel_ip_bindable(tunnel_ip, timeout=2.0)
        if not addr_ready:
            applied.append("tunnel_ip_not_bindable")

    # ------------------------------------------------------------------
    # CRITICAL ORDER: start residual dataplane *before* dual /1 catch-alls.
    # Dual /1 without a live packet processor blackholes all host internet
    # while the UI may still claim "connected" (user: no internet after fulfill).
    # ------------------------------------------------------------------
    from client.product_policy import product_dataplane_traffic_shape

    # Mutable context for idle liveness-loss restore (filled after dual /1 apply).
    # If keepalives fail repeatedly (node prune / dead UDP), roll back dual /1 so
    # long idle never leaves the host with no internet.
    residual_liveness_ctx: dict = {
        "server_host": server_host,
        "plan": plan,
        "if_index": None,
        "routes_applied": False,
    }

    def _on_residual_liveness_lost() -> None:
        if not residual_liveness_ctx.get("routes_applied"):
            # Still notify idle-drop so Settings auto-reconnect can act
            # even if routes were already cleared.
            cb = residual_liveness_ctx.get("on_idle_session_drop")
            if callable(cb):
                try:
                    cb()
                except Exception:
                    pass
            return
        residual_liveness_ctx["routes_applied"] = False
        try:
            restore_windows_residual_path(
                server_host=residual_liveness_ctx.get("server_host") or server_host,
                plan=residual_liveness_ctx.get("plan") or plan,
                if_index=residual_liveness_ctx.get("if_index"),
                run_kill_switch_rollback=True,
                run_ipv6_rollback=True,
            )
        except Exception:
            try:
                rollback_full_tunnel_routes(
                    residual_liveness_ctx.get("plan") or plan,
                    residual_liveness_ctx.get("server_host") or server_host,
                    residual_liveness_ctx.get("if_index"),
                )
            except Exception:
                pass
        # After dual /1 restore: optional app hook (auto-reconnect if idle).
        cb = residual_liveness_ctx.get("on_idle_session_drop")
        if callable(cb):
            try:
                cb()
            except Exception:
                pass

    residual_liveness_ctx["on_idle_session_drop"] = on_idle_session_drop

    plane = RptDataPlane(
        client,
        traffic_shape=product_dataplane_traffic_shape(),
        on_liveness_lost=_on_residual_liveness_lost,
        tunnel_src_ip=str(getattr(plan, "tunnel_client_ip", "") or ""),
    )
    try:
        plane.start(tun)
    except Exception as exc:
        tun.close()
        return WindowsTunnelResult(
            False, f"dataplane start failed: {exc}", applied, routes_applied=False
        )

    if not dataplane_enabled(tun) or not plane.is_running():
        plane.stop()
        tun.close()
        return WindowsTunnelResult(
            False,
            "dataplane failed — dual /1 not installed (prevents blackhole)",
            applied,
            tun=None,
            routes_applied=False,
        )

    route_msg = "routes skipped"
    routes_applied = False

    from client.full_tunnel import plan_wants_ipv4_catchall

    # Settings residual IPv4 OFF → never install dual /1 (even with valid IF).
    want_ipv4_catchall = plan_wants_ipv4_catchall(plan)
    plane_live = dataplane_is_live(plane)

    # Server pin alone is safe before dual /1 (keeps UDP to node on physical path).
    # Dual /1 only when may_install_dual_slash1_catchalls says so.
    allow_catchall = may_install_dual_slash1_catchalls(
        dataplane_running=plane_live,
        system_capture=bool(capture),
        if_index=if_index,
        want_ipv4_catchall=want_ipv4_catchall,
    )

    if routes_would_blackhole_without_system_capture(capture, True):
        route_msg = "no OS TUN capture — full-tunnel routes NOT applied (prevents blackhole)"
    elif want_ipv4_catchall and not plane_live:
        route_msg = (
            "refused dual /1: dataplane not live (would blackhole internet into TUN)"
        )
        routes_applied = False
    elif want_ipv4_catchall and routes_would_blackhole_without_if_index(if_index, True):
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
    elif is_admin() and capture and if_index is not None and allow_catchall:
        # One pass: pin then dual /1 inside apply_routes_for_adapter.
        # A second pin-only pass re-ran netsh address/DNS and padded Connect.
        # Stay up if udp_to_tun >= 1 after a short wait — not 1.1.1.1/Unbound OS smokes.
        cmds, errs, full_ok = apply_routes_for_adapter(
            plan,
            server_host,
            if_index=if_index,
            include_catchall=True,
            physical_gw=physical_gw,
        )
        applied.extend(cmds)
        if full_ok:
            pin_cmds, pin_reok = reassert_server_pin(
                server_host, physical_gw=physical_gw
            )
            applied.extend(pin_cmds)
            if not pin_reok:
                rollback_full_tunnel_routes(plan, server_host, if_index)
                routes_applied = False
                route_msg = (
                    "server pin re-assert failed after dual /1 — "
                    "routes rolled back (prevents blackhole)"
                )
            else:
                routes_applied = True
                residual_liveness_ctx["if_index"] = if_index
                residual_liveness_ctx["routes_applied"] = True
                residual_liveness_ctx["server_host"] = server_host
                residual_liveness_ctx["plan"] = plan
                route_msg = (
                    f"full-tunnel routes applied (IF={if_index}, server pinned; "
                    f"dataplane-first)"
                )
                warns = [e for e in errs if e.startswith("setup warn:")]
                if warns:
                    route_msg += f" ({len(warns)} warn)"
        else:
            routes_applied = False
            residual_liveness_ctx["routes_applied"] = False
            route_msg = "routes refused (pin/catchall failed; rolled back): " + (
                "; ".join(errs) if errs else "unknown"
            )
    elif is_admin() and capture and if_index is not None and not want_ipv4_catchall:
        # Settings residual IPv4 OFF: pin only, no dual /1
        cmds, errs, _pin_ok = apply_routes_for_adapter(
            plan,
            server_host,
            if_index=if_index,
            include_catchall=False,
            physical_gw=physical_gw,
        )
        applied.extend(cmds)
        routes_applied = False
        route_msg = f"server pin only (Settings residual IPv4 off; IF={if_index})"
    elif is_admin():
        route_msg = "admin but no OS TUN — routes not applied (would blackhole)"
    else:
        route_msg = (
            "standard user — system-wide dual /1 skipped "
            "(session + dataplane start without Administrator)"
        )

    # Dual /1 installed but plane died mid-apply → always roll back catch-alls.
    if routes_applied and not dataplane_is_live(plane):
        rollback_full_tunnel_routes(plan, server_host, if_index)
        try:
            plane.stop()
        except Exception:
            pass
        try:
            tun.close()
        except Exception:
            pass
        return WindowsTunnelResult(
            False,
            "dataplane stopped after dual /1 — routes rolled back (prevents blackhole)",
            applied,
            routes_applied=False,
        )

    # Dual /1 is up. Stay Connected if residual DATA actually returns.
    if routes_applied:
        bind_ip = str(getattr(plan, "tunnel_client_ip", "") or "").strip()
        if bind_ip and not addr_ready:
            residual_wait_tunnel_ip_bindable(bind_ip, timeout=2.0)
        try:
            client.send_keepalive()
        except Exception:
            pass

        def _inject_unicast() -> None:
            residual_forward_udp_smoke(
                host="1.1.1.1",
                timeout=0.35,
                bind_ip=bind_ip or None,
            )

        return_ok = residual_wait_dataplane_return(
            plane,
            timeout=2.5,
            poll_s=0.15,
            inject_fn=_inject_unicast,
        )
        if not return_ok or not residual_post_attach_ready(
            routes_applied=True,
            dataplane_running=dataplane_is_live(plane),
            keepalive_ok=True,
            forward_path_ok=return_ok,
            dns_ok=return_ok,
            require_forward_smoke=False,
            require_dns_smoke=False,
            dataplane_return_ok=return_ok,
        ):
            try:
                restore_windows_residual_path(
                    server_host=server_host,
                    plan=plan,
                    if_index=if_index,
                    run_kill_switch_rollback=True,
                    run_ipv6_rollback=True,
                )
            except Exception:
                try:
                    rollback_full_tunnel_routes(plan, server_host, if_index)
                except Exception:
                    pass
            try:
                plane.stop()
            except Exception:
                pass
            try:
                tun.close()
            except Exception:
                pass
            detail = residual_attach_diag(
                plane,
                if_index=if_index,
                bind_ip=bind_ip,
                forward_ok=return_ok,
                dns_ok=return_ok,
            )
            return WindowsTunnelResult(
                False,
                "residual capture rolled back after dual /1 — " + detail,
                applied,
                routes_applied=False,
                plan=plan,
                server_host=server_host,
                if_index=if_index,
                ipv6_mitigation_applied=False,
                kill_switch_applied=False,
            )
        iface = str(getattr(plan, "tunnel_iface", "") or "RPT")
        # Public DNS is already on the IF (configure_address + apply_routes).
        # Probe Unbound briefly; stamp once with the winner — not public then Unbound.
        unbound_ok = residual_tunnel_dns_smoke(
            dns_host="10.88.0.1",
            timeout=0.4,
            bind_ip=bind_ip or None,
            if_index=if_index,
        )
        applied.extend(
            residual_apply_windows_tunnel_dns(
                iface, residual_choose_tunnel_dns(unbound_ok=unbound_ok)
            )
        )
        dns_label = "unbound" if unbound_ok else "public-fallback"
        route_msg = (
            f"{route_msg}; post-attach health ok "
            f"(dataplane return; dns={dns_label})"
        )

    msg = (
        f"TUN mode={tun.mode}; {route_msg}; dataplane running (sealed RPT DATA); "
        f"system_capture={capture}; if_index={if_index}; "
        f"wintun_dll={wintun_dll_available()}"
        f"{wintun_note}"
    )
    if routes_applied and (
        not capture
        or routes_would_blackhole_without_if_index(if_index, True)
        or not dataplane_is_live(plane)
    ):
        plane.stop()
        rollback_full_tunnel_routes(plan, server_host, if_index)
        tun.close()
        return WindowsTunnelResult(
            False,
            "refused: full-tunnel routes without IF-bound live dataplane "
            "would blackhole internet",
            applied,
            routes_applied=False,
        )

    ipv6_ok = False
    from client.residual_stack import plan_wants_ipv6_isp_block

    # IPv6 residual is independent of IPv4 dual /1; apply when Settings IPv6 ON
    # and system TUN is up. Intentional IPv6 OFF → no "incomplete" wording.
    if capture and plan_wants_ipv6_isp_block(plan):
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
    elif capture and not plan_wants_ipv6_isp_block(plan):
        msg += "; IPv6 residual off (Settings)"

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

    # Product residual-IP path: single pure decision table (residual_stack).
    # SESSION_ONLY_OK (Settings residual IPv4 OFF + dataplane up) keeps the session —
    # do not tear down. FAIL tears down. RESIDUAL_OK continues to kill-switch arm.
    if require_system_capture:
        from client.residual_stack import ResidualAttachOutcome, residual_attach_outcome

        attach = residual_attach_outcome(
            ok=bool(result.ok),
            routes_applied=bool(result.routes_applied),
            system_capture=bool(result.system_capture),
            has_dataplane=dataplane_is_live(result.dataplane),
            plan=plan,
        )
        if attach == ResidualAttachOutcome.SESSION_ONLY_OK:
            # Intentional residual IPv4 off: live session, honesty residual_capture=False
            result.message = (result.message or msg) + (
                "; residual IPv4 off (Settings) — session only, ISP IPv4 path unchanged"
            )
            # Keep ok=True, tun/dataplane live; routes_applied already False when IPv4 off
        elif attach == ResidualAttachOutcome.FAIL:
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
        # RESIDUAL_OK: fall through to kill-switch path

    # Kill-switch: opt-in only (Settings kill_switch_opt_in or RPT_KILL_SWITCH=1).
    # Default off — product_kill_switch_enabled() is False unless user opted in.
    # Arm only after residual capture is proven (routes + system capture + dataplane).
    ks_applied = False
    if routes_applied and capture and residual_ip_capture_active(result):
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
                    # Incomplete KS may leave profiles blocked — roll back KS only
                    # (keep residual dual /1; do not blackhole by tearing residual).
                    try:
                        from client.kill_switch import windows_kill_switch_rollback_commands

                        for cmd in windows_kill_switch_rollback_commands():
                            try:
                                residual_shell_run(
                                    cmd,
                                    timeout=residual_restore_cmd_timeout_s(),
                                    text=True,
                                )
                            except Exception:
                                pass
                        result.kill_switch_applied = False
                        ks_applied = False
                    except Exception:
                        # Last resort: full residual restore so host internet works
                        try:
                            restore_windows_residual_path(
                                server_host=server_host,
                                plan=plan,
                                if_index=if_index,
                                run_kill_switch_rollback=True,
                                run_ipv6_rollback=False,
                            )
                            result.routes_applied = False
                            result.kill_switch_applied = False
                            ks_applied = False
                        except Exception:
                            pass
        except Exception as exc:
            result.message = (result.message or msg) + f"; kill-switch incomplete: {exc}"
            ks_applied = False
            result.kill_switch_applied = False

    # Final honesty: never claim residual capture if dual /1 is not applied.
    # (Guards any path that may have rolled routes back after provisional success.)
    if result.routes_applied and not residual_ip_capture_active(result):
        result.routes_applied = False
    if (
        result.ok
        and require_system_capture
        and not residual_ip_capture_active(result)
        and not session_ok_without_residual_capture(result)
    ):
        # Should have been torn down earlier; ensure host internet is restored.
        try:
            restore_windows_residual_path(
                server_host=server_host,
                plan=plan,
                if_index=if_index,
                run_kill_switch_rollback=True,
                run_ipv6_rollback=True,
            )
        except Exception:
            pass
        try:
            if result.dataplane is not None:
                result.dataplane.stop()
        except Exception:
            pass
        try:
            if result.tun is not None:
                result.tun.close()
        except Exception:
            pass
        return WindowsTunnelResult(
            False,
            "residual capture incomplete — routes rolled back "
            f"(prevents internet blackhole). {result.message or msg}",
            list(result.applied_commands or applied),
            routes_applied=False,
            plan=plan,
            server_host=server_host,
            if_index=if_index,
            ipv6_mitigation_applied=False,
            kill_switch_applied=False,
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
    from client.full_tunnel import plan_wants_ipv4_catchall

    cmds = windows_route_commands(
        plan,
        server_host,
        if_index=if_index,
        include_catchall=plan_wants_ipv4_catchall(plan),
    )
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
