"""Pre-wipe health gates for fleet peer wipedown (fail closed).

Live wipe of any residual peer **must** pass:

1. **≥1 other catalog peer residual healthy** — clients need solid failover
   while this node drains (generalizes historic “exit healthy before entry wipe”).
2. **Local node pre-wipe health** — confirm product surfaces before rebuild so
   package reinstall targets a known-good baseline.

Neither gate invents zero client packet loss. Continuity is automatic residual
failover to a healthy peer; re-prefer the user’s selected entry when healthy again.
"""

from __future__ import annotations

import os
import socket
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# Product monopin hosts (must match client.endpoint / multihop constants)
DEFAULT_EXIT_HOST = os.environ.get("RPT_EXIT_HOST", "185.146.232.107")
DEFAULT_EXIT_PORT = int(os.environ.get("RPT_EXIT_PORT", "44044") or "44044")
DEFAULT_ENTRY_HOST = os.environ.get("RPT_NODE_HOST", "82.221.101.241")
DEFAULT_ENTRY_PORT = int(os.environ.get("RPT_NODE_PORT", "44044") or "44044")


@dataclass
class HealthProbeResult:
    """One health probe outcome."""

    name: str
    ok: bool
    detail: str
    host: str = ""
    port: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
            "host": self.host,
            "port": self.port,
        }


@dataclass
class PrewipeGateResult:
    """Combined pre-wipe gate decision for live wipedown."""

    allow_wipe: bool
    exit_probe: HealthProbeResult
    entry_probe: HealthProbeResult
    reasons: list[str] = field(default_factory=list)
    package_reinstall_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "allow_wipe": self.allow_wipe,
            "exit_probe": self.exit_probe.to_dict(),
            "entry_probe": self.entry_probe.to_dict(),
            "reasons": list(self.reasons),
            "package_reinstall_required": self.package_reinstall_required,
            "continuity_honesty": (
                "automatic residual failover to exit while entry drains; "
                "not absolute zero packet loss"
            ),
        }


def probe_icmp_reachable(
    host: str,
    *,
    timeout_s: float = 3.0,
    run_cmd: Optional[Callable[[list[str]], tuple[int, str]]] = None,
) -> HealthProbeResult:
    """ICMP echo must get a reply — fails closed for dead/unroutable hosts.

    UDP send-only is fail-open (kernel accepts sendto to blackholes). ICMP reply
    (or an alternate residual response) is required for exit failover confidence.
    """
    h = (host or "").strip()
    if not h:
        return HealthProbeResult(
            name="icmp_reachable", ok=False, detail="missing host", host=h
        )

    def _default_run(argv: list[str]) -> tuple[int, str]:
        try:
            r = subprocess.run(
                argv, capture_output=True, text=True, timeout=max(5.0, timeout_s + 2)
            )
            return int(r.returncode), (r.stdout or "") + (r.stderr or "")
        except (OSError, subprocess.TimeoutExpired) as exc:
            return 1, str(exc)

    runner = run_cmd or _default_run
    # Windows: ping -n 1 -w <ms>; Unix: ping -c 1 -W <sec>
    if os.name == "nt":
        ms = max(1, int(timeout_s * 1000))
        argv = ["ping", "-n", "1", "-w", str(ms), h]
    else:
        # -W is deadline seconds on Linux; -c 1 one echo
        sec = max(1, int(timeout_s))
        argv = ["ping", "-c", "1", "-W", str(sec), h]
    rc, out = runner(argv)
    blob = (out or "").lower()
    # Require process success AND reply indicators (avoid "Destination host unreachable" as ok)
    unreachable = any(
        x in blob
        for x in (
            "destination host unreachable",
            "destination net unreachable",
            "request timed out",
            "100% packet loss",
            "0 received",
            "could not find host",
            "unknown host",
            "name or service not known",
            "network is unreachable",
        )
    )
    got_reply = rc == 0 and not unreachable and (
        "ttl=" in blob
        or "time=" in blob
        or "time<" in blob
        or "bytes from" in blob
        or "reply from" in blob
    )
    if got_reply:
        return HealthProbeResult(
            name="icmp_reachable",
            ok=True,
            detail=f"icmp echo reply from {h}",
            host=h,
        )
    return HealthProbeResult(
        name="icmp_reachable",
        ok=False,
        detail=f"icmp fail closed for {h} (rc={rc}; no echo reply)",
        host=h,
    )


def probe_udp_reachable(
    host: str,
    port: int,
    *,
    timeout_s: float = 3.0,
    payload: bytes = b"RPT2",
) -> HealthProbeResult:
    """UDP residual probe that **requires a response** (fail closed).

    ``sendto`` alone is **not** health — it succeeds for dead/blackhole
    destinations (e.g. TEST-NET 203.0.113.0/24). Must ``recvfrom`` a reply
    within *timeout_s*, or the probe fails closed.
    """
    h = (host or "").strip()
    p = int(port)
    if not h or p <= 0:
        return HealthProbeResult(
            name="udp_reachable",
            ok=False,
            detail="missing host/port",
            host=h,
            port=p,
        )
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(timeout_s)
            sent = sock.sendto(payload, (h, p))
            if sent <= 0:
                return HealthProbeResult(
                    name="udp_reachable",
                    ok=False,
                    detail="udp send returned 0 bytes",
                    host=h,
                    port=p,
                )
            try:
                data, addr = sock.recvfrom(65535)
            except (socket.timeout, TimeoutError):
                return HealthProbeResult(
                    name="udp_reachable",
                    ok=False,
                    detail=(
                        f"udp fail closed: sent {sent}B to {h}:{p} but no response "
                        f"within {timeout_s}s (send-only is not health)"
                    ),
                    host=h,
                    port=p,
                )
            if not data:
                return HealthProbeResult(
                    name="udp_reachable",
                    ok=False,
                    detail=f"udp empty response from {addr}",
                    host=h,
                    port=p,
                )
            return HealthProbeResult(
                name="udp_reachable",
                ok=True,
                detail=f"udp response {len(data)}B from {addr[0]}:{addr[1]}",
                host=h,
                port=p,
            )
        finally:
            sock.close()
    except OSError as exc:
        return HealthProbeResult(
            name="udp_reachable",
            ok=False,
            detail=f"udp error: {exc}",
            host=h,
            port=p,
        )


def probe_exit_residual(
    host: str,
    port: int,
    *,
    timeout_s: float = 3.0,
    icmp_run_cmd: Optional[Callable[[list[str]], tuple[int, str]]] = None,
) -> HealthProbeResult:
    """Exit residual health: UDP response **or** ICMP echo (never send-only).

    Fail closed when the host is down/unroutable (no ICMP reply and no UDP
    residual response). Product residual is UDP; many nodes will not answer a
    bare magic probe without HELLO — ICMP then proves the exit VPS is up so
    clients can still target residual once HELLO credentials are used.
    """
    h = (host or "").strip()
    p = int(port)
    udp = probe_udp_reachable(h, p, timeout_s=timeout_s)
    if udp.ok:
        return HealthProbeResult(
            name="exit_residual",
            ok=True,
            detail=f"udp residual ok: {udp.detail}",
            host=h,
            port=p,
        )
    icmp = probe_icmp_reachable(h, timeout_s=timeout_s, run_cmd=icmp_run_cmd)
    if icmp.ok:
        return HealthProbeResult(
            name="exit_residual",
            ok=True,
            detail=(
                f"icmp ok (exit host up for residual path); "
                f"udp no bare reply: {udp.detail}"
            ),
            host=h,
            port=p,
        )
    return HealthProbeResult(
        name="exit_residual",
        ok=False,
        detail=(
            f"fail closed: no UDP residual response and no ICMP echo — "
            f"exit not solid for failover ({udp.detail}; {icmp.detail})"
        ),
        host=h,
        port=p,
    )


def probe_local_udp_listen(
    port: int = DEFAULT_ENTRY_PORT,
    *,
    run_cmd: Optional[Callable[[list[str]], tuple[int, str]]] = None,
) -> HealthProbeResult:
    """Check local node is listening on residual UDP port (pre-wipe baseline)."""
    p = int(port)

    def _default_run(argv: list[str]) -> tuple[int, str]:
        try:
            r = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=10,
            )
            out = (r.stdout or "") + (r.stderr or "")
            return int(r.returncode), out
        except (OSError, subprocess.TimeoutExpired) as exc:
            return 1, str(exc)

    runner = run_cmd or _default_run
    # Prefer ss; fall back to checking socket bindability is not used (would steal port)
    rc, out = runner(["ss", "-ulnp"])
    if rc == 0 and out:
        if str(p) in out or f":{p}" in out:
            return HealthProbeResult(
                name="local_udp_listen",
                ok=True,
                detail=f"ss shows UDP listen involving :{p}",
                host="127.0.0.1",
                port=p,
            )
        return HealthProbeResult(
            name="local_udp_listen",
            ok=False,
            detail=f"ss output has no UDP :{p} (node may be down)",
            host="127.0.0.1",
            port=p,
        )
    # ss missing / failed — try status HTTP title surface (best effort)
    rc2, out2 = runner(
        ["curl", "-sS", "--max-time", "3", "http://127.0.0.1:8080/api/status"]
    )
    if rc2 == 0 and out2.strip():
        return HealthProbeResult(
            name="local_udp_listen",
            ok=True,
            detail="ss unavailable; local status HTTP responded (entry surface up)",
            host="127.0.0.1",
            port=p,
        )
    return HealthProbeResult(
        name="local_udp_listen",
        ok=False,
        detail=f"cannot confirm local listen :{p} (ss rc={rc}; status rc={rc2})",
        host="127.0.0.1",
        port=p,
    )


def check_exit_health(
    *,
    host: str | None = None,
    port: int | None = None,
    probe: Optional[Callable[[str, int], HealthProbeResult]] = None,
) -> HealthProbeResult:
    """Exit residual health for client failover (required before entry drain).

    Default probe is :func:`probe_exit_residual` (UDP response **or** ICMP echo).
    Never treats bare UDP send success as healthy.
    """
    h = (host if host is not None else DEFAULT_EXIT_HOST).strip()
    p = int(port if port is not None else DEFAULT_EXIT_PORT)
    fn = probe or (lambda hh, pp: probe_exit_residual(hh, pp))
    r = fn(h, p)
    return HealthProbeResult(
        name="exit_residual",
        ok=r.ok,
        detail=r.detail,
        host=h,
        port=p,
    )


def check_entry_node_health(
    *,
    port: int | None = None,
    probe: Optional[Callable[[], HealthProbeResult]] = None,
) -> HealthProbeResult:
    """Entry/node pre-wipe health (listen or status surface)."""
    p = int(port if port is not None else DEFAULT_ENTRY_PORT)
    if probe is not None:
        r = probe()
        return HealthProbeResult(
            name="entry_node",
            ok=r.ok,
            detail=r.detail,
            host=r.host or "127.0.0.1",
            port=r.port or p,
        )
    r = probe_local_udp_listen(p)
    return HealthProbeResult(
        name="entry_node",
        ok=r.ok,
        detail=r.detail,
        host=r.host,
        port=r.port,
    )


def evaluate_prewipe_gates(
    *,
    exit_probe: HealthProbeResult,
    entry_probe: HealthProbeResult,
    require_package_reinstall: bool = True,
) -> PrewipeGateResult:
    """Fail-closed combine: peer residual + local node must be healthy to allow wipe.

    Historically named exit/entry probes: *exit_probe* is any **failover peer**
    residual health; *entry_probe* is the **node about to be wiped** (local).
    """
    reasons: list[str] = []
    if not exit_probe.ok:
        reasons.append(
            f"peer residual unhealthy — refuse wipe (no solid client failover): "
            f"{exit_probe.detail}"
        )
    if not entry_probe.ok:
        reasons.append(
            f"local node pre-wipe health failed — refuse wipe: {entry_probe.detail}"
        )
    if require_package_reinstall:
        reasons.append(
            "package reinstall (selfhost) required after rebuild on live path"
        )
    allow = bool(exit_probe.ok and entry_probe.ok)
    # The reinstall "reason" is a requirement note, not a failure
    fail_reasons = [r for r in reasons if not r.startswith("package reinstall")]
    if allow:
        msg = [
            "pre-wipe gates PASS: peer residual healthy (failover solid) + local node healthy",
            "live wipe may proceed only with RPT_EPHEMERAL_CONFIRM + exclusive lock",
            "continuity: clients auto residual-failover to a healthy peer during drain "
            "(not zero packet-loss guarantee)",
        ]
        if require_package_reinstall:
            msg.append("after rebuild: selfhost/package reinstall is mandatory")
        return PrewipeGateResult(
            allow_wipe=True,
            exit_probe=exit_probe,
            entry_probe=entry_probe,
            reasons=msg,
            package_reinstall_required=require_package_reinstall,
        )
    return PrewipeGateResult(
        allow_wipe=False,
        exit_probe=exit_probe,
        entry_probe=entry_probe,
        reasons=fail_reasons
        + (
            ["package reinstall still required after any future successful rebuild"]
            if require_package_reinstall
            else []
        ),
        package_reinstall_required=require_package_reinstall,
    )


def evaluate_catalog_peer_prewipe(
    target_code: str,
    peer_health: dict[str, bool],
    *,
    local_ok: bool = True,
    local_detail: str = "local node baseline ok",
) -> PrewipeGateResult:
    """Bridge pure fleet peer gate into :class:`PrewipeGateResult`.

    *peer_health* maps country codes → healthy. Target must have ≥1 healthy
    **other** peer; local node health is the second gate.
    """
    from node.fleet_wipe import evaluate_peer_prewipe_gate

    peer = evaluate_peer_prewipe_gate(target_code, peer_health)
    peer_probe = HealthProbeResult(
        name="catalog_peer_residual",
        ok=peer.allow_wipe,
        detail="; ".join(peer.reasons) if peer.reasons else "",
        host=",".join(peer.healthy_peers) if peer.healthy_peers else "",
    )
    local_probe = HealthProbeResult(
        name="local_node",
        ok=bool(local_ok),
        detail=local_detail,
        host="127.0.0.1",
    )
    return evaluate_prewipe_gates(
        exit_probe=peer_probe,
        entry_probe=local_probe,
    )


def run_live_prewipe_gates(
    *,
    exit_host: str | None = None,
    exit_port: int | None = None,
    entry_port: int | None = None,
    exit_probe_fn: Optional[Callable[[str, int], HealthProbeResult]] = None,
    entry_probe_fn: Optional[Callable[[], HealthProbeResult]] = None,
    target_code: str | None = None,
    peer_health: dict[str, bool] | None = None,
) -> PrewipeGateResult:
    """Execute real probes and evaluate fail-closed gates (live path entrypoint).

    When *target_code* is set, uses catalog peer map (:func:`evaluate_catalog_peer_prewipe`)
    so wiping RO requires a healthy IS (or other) peer — not a hardcoded exit-only host.
    Legacy path (no target_code) still probes DEFAULT_EXIT_HOST as the failover peer.
    """
    entry_r = check_entry_node_health(port=entry_port, probe=entry_probe_fn)
    if target_code:
        from node.fleet_wipe import fleet_country_codes

        codes = fleet_country_codes()
        want = (target_code or "").strip().upper()
        ph: dict[str, bool] = {}
        if peer_health is not None:
            ph = {str(k).upper(): bool(v) for k, v in peer_health.items()}
        else:
            # Probe each other catalog peer via exit residual host map
            from client.multihop import PRODUCT_COUNTRY_CATALOG

            host_by_code = {
                n.code: (n.host, int(n.port)) for n in PRODUCT_COUNTRY_CATALOG
            }
            for c in codes:
                if c == want:
                    ph[c] = bool(entry_r.ok)
                    continue
                host, port = host_by_code.get(c, (DEFAULT_EXIT_HOST, DEFAULT_EXIT_PORT))
                if exit_host and c != want and len(codes) == 2:
                    # Prefer explicit override for the single alternate
                    host = exit_host
                    port = int(exit_port if exit_port is not None else DEFAULT_EXIT_PORT)
                pr = check_exit_health(
                    host=host, port=port, probe=exit_probe_fn
                )
                ph[c] = bool(pr.ok)
        return evaluate_catalog_peer_prewipe(
            want,
            ph,
            local_ok=bool(entry_r.ok),
            local_detail=entry_r.detail,
        )
    exit_r = check_exit_health(
        host=exit_host, port=exit_port, probe=exit_probe_fn
    )
    return evaluate_prewipe_gates(exit_probe=exit_r, entry_probe=entry_r)


def plan_has_required_live_steps(step_ids: list[str]) -> tuple[bool, list[str]]:
    """Structural gate: required ordered steps for safe live weekly wipe.

    Package/selfhost reinstall after rebuild is mandatory — a plan without
    ``selfhost_reapply`` (or ``selfhost_full``) is refused for live wipe.
    Peer preflight may be ``peer_failover_preflight`` (fleet) or legacy
    ``exit_failover_preflight``.
    """
    missing: list[str] = []
    required = [
        "entry_node_preflight",
        "exclusive_lock_acquire",
        "rebuild_host",
        "selfhost_reapply",  # package reinstall / product posture (mandatory)
        "health_check",
        "exclusive_lock_release",
    ]
    ids = list(step_ids or [])
    # Peer failover preflight (catalog or legacy name)
    if (
        "peer_failover_preflight" not in ids
        and "exit_failover_preflight" not in ids
    ):
        missing.append("peer_failover_preflight|exit_failover_preflight")
    for r in required:
        if r not in ids:
            # Allow alternate id used by pure role helpers
            if r == "selfhost_reapply" and "selfhost_full" in ids:
                continue
            missing.append(r)
    if missing:
        return False, missing
    # Ordering: preflights before rebuild; selfhost after rebuild; health after selfhost
    peer_pf = (
        "peer_failover_preflight"
        if "peer_failover_preflight" in ids
        else "exit_failover_preflight"
    )
    if ids.index(peer_pf) >= ids.index("rebuild_host"):
        missing.append("order:peer_preflight_before_rebuild")
    if ids.index("entry_node_preflight") >= ids.index("rebuild_host"):
        missing.append("order:entry_preflight_before_rebuild")
    selfhost_idx = (
        ids.index("selfhost_reapply")
        if "selfhost_reapply" in ids
        else ids.index("selfhost_full")
    )
    if selfhost_idx <= ids.index("rebuild_host"):
        missing.append("order:selfhost_after_rebuild")
    if ids.index("health_check") <= selfhost_idx:
        missing.append("order:health_after_selfhost")
    if ids.index("exclusive_lock_release") <= ids.index("health_check"):
        missing.append("order:lock_release_after_health")
    return (len(missing) == 0), missing


def package_reinstall_required_for_live_wipe() -> bool:
    """Product policy: live weekly wipe always requires package reinstall after rebuild."""
    return True
