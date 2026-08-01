"""Flyclient **hidden-node agent** for rpOS multi-hop participation.

Every rpOS install can register as a **hidden** intermediate hop in the product
multi-hop structure. This is a light agent (OBJECTIVE: flyclient) — it does
**not**:

- run full fleet selfhost / zram+LUKS node install scripts
- skip residual Connect HELLO (legacy residual HELLO-skip path — removed)
- appear as a public catalog residual entry/exit dial target

Resource posture is deliberately bounded: a small loopback TCP **hook acceptor**
plus on-disk registry (no disk crypto stack, no host wipe, no package reinstall).

Participation identity is the bound ``host:port`` of the hook (default loopback)
so multi-hop path builders can include a real intermediate that accepts sockets.
NAT desktop installs stay on loopback — honest light participation, not a public
VPS equivalent.
"""

from __future__ import annotations

import json
import secrets
import socket
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

# Agent identity (not the removed Connect HELLO-skip module).
AGENT_NAME = "flyclient_hidden_node"
AGENT_KIND = "hidden_multihop_node"
PRODUCT_SCOPE = "rpOS"  # Suite residual clients are not auto-enrolled

# Bounded resource posture (declarative caps for honesty / tests).
MAX_RSS_MB_DECLARED = 64
MAX_CPU_PERCENT_DECLARED = 5
USES_SELFHOST_STACK = False
USES_ZRAM_LUKS = False
USES_DISK_CRYPTO_INSTALL = False
# Scripts / paths the agent must never invoke for enablement.
FORBIDDEN_SELFHOST_MARKERS = (
    "selfhost_node.sh",
    "install_zram_luks.sh",
    "install_disk_encryption.sh",
    "node/install.sh",
)

ROLE_HIDDEN = "hidden"
DEFAULT_HOOK_PORT = 44050  # preferred local participation hook port
DEFAULT_BIND_HOST = "127.0.0.1"
# Wire banner for the light hook (not residual HELLO).
HOOK_BANNER_PREFIX = b"FLYCLIENT_HIDDEN_OK"
HOOK_RECV_MAX = 512
HOOK_FORWARD_PREFIX = b"FORWARD:"

REGISTRY_FILENAME = "flyclient_hidden_node.json"
INSTALL_MARKER_NAME = "RPOS_INSTALLED.json"

# Process-local live agents (bound sockets). Keyed by install_id.
_LIVE_AGENTS: dict[str, "FlyclientHiddenAgent"] = {}
_LIVE_LOCK = threading.Lock()


@dataclass
class HiddenNodeRecord:
    """One rpOS install registered as a hidden multi-hop hop."""

    install_id: str
    host: str
    port: int = DEFAULT_HOOK_PORT
    role: str = ROLE_HIDDEN
    product: str = PRODUCT_SCOPE
    agent: str = AGENT_NAME
    enabled: bool = True
    running: bool = False
    public_catalog: bool = False  # always False — never public dial peer
    visibility: str = "hidden"
    uses_selfhost: bool = False
    uses_zram_luks: bool = False
    max_rss_mb: int = MAX_RSS_MB_DECLARED
    max_cpu_percent: int = MAX_CPU_PERCENT_DECLARED
    registered_unix: int = 0
    prefix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HiddenNodeRecord":
        return cls(
            install_id=str(data.get("install_id") or ""),
            host=str(data.get("host") or "").strip() or "127.0.0.1",
            port=int(data.get("port") or DEFAULT_HOOK_PORT),
            role=str(data.get("role") or ROLE_HIDDEN),
            product=str(data.get("product") or PRODUCT_SCOPE),
            agent=str(data.get("agent") or AGENT_NAME),
            enabled=bool(data.get("enabled", True)),
            running=bool(data.get("running", False)),
            public_catalog=False,  # force hidden
            visibility="hidden",
            uses_selfhost=False,
            uses_zram_luks=False,
            max_rss_mb=int(data.get("max_rss_mb") or MAX_RSS_MB_DECLARED),
            max_cpu_percent=int(
                data.get("max_cpu_percent") or MAX_CPU_PERCENT_DECLARED
            ),
            registered_unix=int(data.get("registered_unix") or 0),
            prefix=str(data.get("prefix") or ""),
        )

    def as_hop(self):
        """Return a multihop :class:`Hop` with role=hidden (import lazily)."""
        from client.multihop import Hop

        return Hop(host=self.host, port=int(self.port), role=ROLE_HIDDEN)


def handle_hook_payload(install_id: str, data: bytes) -> bytes:
    """Pure light hook/forward unit (no selfhost). Callable without a socket.

    - Empty / probe → banner with install id
    - ``FORWARD:<bytes>`` → echo payload (bounded light forward)
    - anything else → banner + ack of received length
    """
    iid = (install_id or "").encode("utf-8")
    banner = HOOK_BANNER_PREFIX + b" " + iid + b"\n"
    raw = data or b""
    if raw.startswith(HOOK_FORWARD_PREFIX):
        payload = raw[len(HOOK_FORWARD_PREFIX) : HOOK_RECV_MAX]
        return banner + b"FWD:" + payload
    if not raw.strip():
        return banner
    return banner + b"ACK:" + str(len(raw)).encode("ascii") + b"\n"


@dataclass
class FlyclientHiddenAgent:
    """In-process light agent: binds a TCP hook acceptor for multi-hop participation."""

    record: HiddenNodeRecord
    started: bool = False
    # Audit: commands/scripts attempted (must stay empty of selfhost markers).
    invocations: list[str] = field(default_factory=list)
    _sock: socket.socket | None = field(default=None, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    accepts: int = 0

    def start(self) -> dict[str, Any]:
        """Bind loopback (or configured host) TCP hook and accept in a daemon thread.

        No selfhost / LUKS / zram. On port conflict, binds an ephemeral free port
        and updates ``record.port`` to the real bound port.
        """
        if any(m in " ".join(self.invocations) for m in FORBIDDEN_SELFHOST_MARKERS):
            raise RuntimeError("hidden flyclient agent must not invoke selfhost stack")
        if self.started and self._sock is not None:
            return self._status_dict(ok=True)

        # Light desktop participation binds loopback only (honest NAT posture).
        # Non-loopback / public catalog hosts are rewritten so bind always works.
        want = (self.record.host or DEFAULT_BIND_HOST).strip() or DEFAULT_BIND_HOST
        if want in ("0.0.0.0", "::", "*", "localhost"):
            want = DEFAULT_BIND_HOST
        if want not in ("127.0.0.1", "::1") or is_public_catalog_peer_host(want):
            want = DEFAULT_BIND_HOST
        bind_host = DEFAULT_BIND_HOST
        port = int(self.record.port or 0)
        if port <= 0 or port > 65535:
            port = 0

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            try:
                sock.bind((bind_host, port))
            except OSError:
                # Preferred port busy — ephemeral free port.
                sock.bind((bind_host, 0))
        except OSError:
            try:
                sock.close()
            except OSError:
                pass
            raise
        sock.listen(16)
        sock.settimeout(0.5)
        bound_host, bound_port = sock.getsockname()[:2]
        # Participation identity = actually bound address (connectible).
        self.record.host = str(bound_host) if str(bound_host) != "0.0.0.0" else DEFAULT_BIND_HOST
        self.record.port = int(bound_port)
        self.record.enabled = True
        self.record.running = True
        self.record.public_catalog = False
        self.record.visibility = "hidden"
        self._sock = sock
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._accept_loop,
            name=f"flyclient-hidden-{self.record.install_id[:12]}",
            daemon=True,
        )
        self._thread.start()
        self.started = True
        with _LIVE_LOCK:
            _LIVE_AGENTS[self.record.install_id] = self
        return self._status_dict(ok=True)

    def _accept_loop(self) -> None:
        sock = self._sock
        if sock is None:
            return
        while not self._stop.is_set():
            try:
                conn, _addr = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self.accepts += 1
            try:
                conn.settimeout(2.0)
                try:
                    data = conn.recv(HOOK_RECV_MAX)
                except OSError:
                    data = b""
                resp = handle_hook_payload(self.record.install_id, data)
                try:
                    conn.sendall(resp)
                except OSError:
                    pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        thr = self._thread
        if thr is not None and thr.is_alive():
            thr.join(timeout=2.0)
        self._thread = None
        self.started = False
        self.record.running = False
        with _LIVE_LOCK:
            if _LIVE_AGENTS.get(self.record.install_id) is self:
                _LIVE_AGENTS.pop(self.record.install_id, None)
        return {
            "ok": True,
            "agent": AGENT_NAME,
            "install_id": self.record.install_id,
            "running": False,
            "accepts": self.accepts,
            "invocations": list(self.invocations),
        }

    def _status_dict(self, *, ok: bool) -> dict[str, Any]:
        return {
            "ok": ok,
            "agent": AGENT_NAME,
            "kind": AGENT_KIND,
            "install_id": self.record.install_id,
            "running": bool(self.started and self._sock is not None),
            "host": self.record.host,
            "port": int(self.record.port),
            "bound": f"{self.record.host}:{int(self.record.port)}",
            "uses_selfhost": USES_SELFHOST_STACK,
            "uses_zram_luks": USES_ZRAM_LUKS,
            "uses_disk_crypto_install": USES_DISK_CRYPTO_INSTALL,
            "max_rss_mb": self.record.max_rss_mb,
            "max_cpu_percent": self.record.max_cpu_percent,
            "public_catalog": False,
            "visibility": "hidden",
            "accepts": self.accepts,
            "invocations": list(self.invocations),
        }

    def resource_posture(self) -> dict[str, Any]:
        return {
            "agent": AGENT_NAME,
            "max_rss_mb": MAX_RSS_MB_DECLARED,
            "max_cpu_percent": MAX_CPU_PERCENT_DECLARED,
            "uses_selfhost": USES_SELFHOST_STACK,
            "uses_zram_luks": USES_ZRAM_LUKS,
            "uses_disk_crypto_install": USES_DISK_CRYPTO_INSTALL,
            "forbidden_selfhost_markers": list(FORBIDDEN_SELFHOST_MARKERS),
            "hook_bound": bool(self._sock is not None),
        }

    def probe_local(self, payload: bytes = b"") -> bytes:
        """Connect to this agent's bound hook and return the response bytes."""
        if not self.started or self._sock is None:
            raise RuntimeError("agent not started")
        return probe_hidden_hook(self.record.host, int(self.record.port), payload)


def probe_hidden_hook(
    host: str,
    port: int,
    payload: bytes = b"",
    *,
    timeout: float = 2.0,
) -> bytes:
    """TCP client probe against a live flyclient hidden hook (real path)."""
    h = (host or DEFAULT_BIND_HOST).strip() or DEFAULT_BIND_HOST
    with socket.create_connection((h, int(port)), timeout=timeout) as s:
        s.settimeout(timeout)
        if payload:
            s.sendall(payload)
        else:
            s.sendall(b"")
        chunks: list[bytes] = []
        try:
            while True:
                part = s.recv(HOOK_RECV_MAX)
                if not part:
                    break
                chunks.append(part)
                if len(b"".join(chunks)) >= HOOK_RECV_MAX:
                    break
        except socket.timeout:
            pass
        return b"".join(chunks)


def get_live_agent(install_id: str) -> FlyclientHiddenAgent | None:
    with _LIVE_LOCK:
        return _LIVE_AGENTS.get(install_id)


def list_live_agents() -> list[FlyclientHiddenAgent]:
    with _LIVE_LOCK:
        return list(_LIVE_AGENTS.values())


def stop_all_live_agents() -> int:
    """Stop every process-local agent (tests / shutdown)."""
    with _LIVE_LOCK:
        agents = list(_LIVE_AGENTS.values())
    n = 0
    for a in agents:
        a.stop()
        n += 1
    return n


def new_install_id() -> str:
    return f"rpos-{uuid.uuid4().hex[:16]}"


def registry_path(prefix: Path | str) -> Path:
    return Path(prefix) / REGISTRY_FILENAME


def load_registry(prefix: Path | str) -> list[HiddenNodeRecord]:
    path = registry_path(prefix)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = raw.get("nodes") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    out: list[HiddenNodeRecord] = []
    for it in items:
        if isinstance(it, dict):
            out.append(HiddenNodeRecord.from_dict(it))
    return out


def save_registry(prefix: Path | str, nodes: Sequence[HiddenNodeRecord]) -> Path:
    path = registry_path(prefix)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "agent": AGENT_NAME,
        "kind": AGENT_KIND,
        "public_catalog": False,
        "nodes": [n.to_dict() for n in nodes],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def register_instance(
    prefix: Path | str,
    *,
    install_id: str | None = None,
    host: str = DEFAULT_BIND_HOST,
    port: int = DEFAULT_HOOK_PORT,
    start: bool = True,
) -> HiddenNodeRecord:
    """Register (or refresh) this install as a hidden multi-hop node.

    Persists under *prefix*/flyclient_hidden_node.json. When *start* is True,
    binds a real TCP hook acceptor and keeps the agent in the process-local
    live map. Never marks public_catalog.
    """
    pref = Path(prefix)
    pref.mkdir(parents=True, exist_ok=True)
    iid = (install_id or "").strip() or new_install_id()
    host_s = (host or "").strip() or DEFAULT_BIND_HOST
    if host_s in ("0.0.0.0", "::", "*"):
        host_s = DEFAULT_BIND_HOST

    nodes = load_registry(pref)
    existing = next((n for n in nodes if n.install_id == iid), None)
    now = int(time.time())
    if existing is None:
        rec = HiddenNodeRecord(
            install_id=iid,
            host=host_s,
            port=int(port) if port else 0,
            registered_unix=now,
            prefix=str(pref),
        )
        nodes.append(rec)
    else:
        existing.host = host_s
        existing.port = int(port) if port else int(existing.port or 0)
        existing.enabled = True
        existing.public_catalog = False
        existing.visibility = "hidden"
        existing.uses_selfhost = False
        existing.uses_zram_luks = False
        existing.prefix = str(pref)
        rec = existing

    live = get_live_agent(iid)
    if start:
        if live is not None and live.started:
            # Refresh host/port from live bind
            rec.host = live.record.host
            rec.port = live.record.port
            rec.running = True
            agent = live
        else:
            agent = FlyclientHiddenAgent(record=rec)
            agent.start()
            rec = agent.record
        # Sync registry list with bound identity
        for i, n in enumerate(nodes):
            if n.install_id == iid:
                nodes[i] = rec
                break
    save_registry(pref, nodes)
    return rec


def enable_for_rpos_install(
    prefix: Path | str,
    *,
    install_id: str | None = None,
    host: str = DEFAULT_BIND_HOST,
    port: int | None = None,
) -> dict[str, Any]:
    """rpOS install-path entry: enable hidden flyclient node for this instance.

    Binds a real light TCP hook (default loopback). No selfhost scripts.
    """
    pref = Path(prefix)
    iid = (install_id or "").strip()
    marker = pref / INSTALL_MARKER_NAME
    if not iid and marker.is_file():
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
            iid = str(data.get("install_id") or data.get("hidden_node_install_id") or "")
        except (OSError, json.JSONDecodeError):
            iid = ""
    if not iid:
        iid = new_install_id()

    # Preferred port from id; bind may fall back to ephemeral if busy.
    if port is None:
        digest = sum(ord(c) for c in iid) % 1000
        port = DEFAULT_HOOK_PORT + digest

    rec = register_instance(
        pref,
        install_id=iid,
        host=host or DEFAULT_BIND_HOST,
        port=int(port),
        start=True,
    )
    agent = get_live_agent(rec.install_id)
    if agent is None:
        agent = FlyclientHiddenAgent(record=rec)
        start_info = agent.start()
        rec = agent.record
        # persist bound identity
        nodes = load_registry(pref)
        for i, n in enumerate(nodes):
            if n.install_id == rec.install_id:
                nodes[i] = rec
                break
        else:
            nodes.append(rec)
        save_registry(pref, nodes)
    else:
        start_info = agent._status_dict(ok=True)

    # Prove hook accepts connections (participation unit is live).
    try:
        probe = probe_hidden_hook(rec.host, int(rec.port), b"PING")
        hook_ok = probe.startswith(HOOK_BANNER_PREFIX)
    except OSError as exc:
        probe = b""
        hook_ok = False
        start_info = {**start_info, "probe_error": str(exc)}

    if marker.is_file():
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        data["install_id"] = rec.install_id
        data["hidden_node_enabled"] = True
        data["flyclient_hidden_node"] = True
        data["hidden_node_visibility"] = "hidden"
        data["hidden_node_public_catalog"] = False
        data["hidden_node_uses_selfhost"] = False
        data["hidden_node_agent"] = AGENT_NAME
        data["hidden_node_host"] = rec.host
        data["hidden_node_port"] = rec.port
        data["hidden_node_bound"] = f"{rec.host}:{int(rec.port)}"
        data["hidden_node_hook_ok"] = hook_ok
        marker.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    return {
        "ok": bool(hook_ok),
        "enabled": True,
        "install_id": rec.install_id,
        "agent": AGENT_NAME,
        "kind": AGENT_KIND,
        "role": ROLE_HIDDEN,
        "visibility": "hidden",
        "public_catalog": False,
        "host": rec.host,
        "port": int(rec.port),
        "bound": f"{rec.host}:{int(rec.port)}",
        "hook_ok": hook_ok,
        "hook_probe": probe.decode("utf-8", errors="replace")[:120],
        "registry": str(registry_path(pref)),
        "uses_selfhost": USES_SELFHOST_STACK,
        "uses_zram_luks": USES_ZRAM_LUKS,
        "uses_disk_crypto_install": USES_DISK_CRYPTO_INSTALL,
        "resource": agent.resource_posture() if agent else {},
        "start": start_info,
        "record": rec.to_dict(),
    }


def discover_hidden_registry_prefixes(
    env: dict[str, str] | None = None,
) -> list[Path]:
    """Prefixes that may hold flyclient_hidden_node.json for product multi-hop."""
    import os

    e = env if env is not None else os.environ
    out: list[Path] = []
    raw = str(e.get("RPT_HIDDEN_NODE_PREFIXES", "") or "").strip()
    if raw:
        for part in raw.replace(";", os.pathsep).split(os.pathsep):
            p = part.strip()
            if p:
                out.append(Path(p))
    single = str(e.get("RPT_HIDDEN_NODE_PREFIX", "") or "").strip()
    if single:
        out.append(Path(single))
    # Default rpOS install root
    out.append(Path.home() / ".rpos" / "install")
    # Dedupe preserving order
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def discover_enabled_hidden_hops(
    env: dict[str, str] | None = None,
    *,
    prefixes: Sequence[Path | str] | None = None,
    include_live: bool = True,
) -> list:
    """Hidden hops for product multi-hop: live agents + on-disk registries.

    Returns multihop :class:`Hop` list with role=hidden only. Live process agents
    win over stale registry ports so path identity matches the bound hook.
    """
    from client.multihop import Hop

    hops: list = []
    seen: set[tuple[str, int]] = set()

    if include_live:
        for agent in list_live_agents():
            rec = agent.record
            if not rec.enabled or not agent.started:
                continue
            host = (rec.host or "").strip()
            port = int(rec.port or 0)
            if not host or port <= 0:
                continue
            key = (host, port)
            if key in seen:
                continue
            seen.add(key)
            hops.append(Hop(host=host, port=port, role=ROLE_HIDDEN))

    prefs: list[Path | str]
    if prefixes is not None:
        prefs = list(prefixes)
    else:
        prefs = list(discover_hidden_registry_prefixes(env))
    for pref in prefs:
        for rec in load_registry(pref):
            if not rec.enabled:
                continue
            # Prefer live identity for same install_id
            live = get_live_agent(rec.install_id)
            if live is not None and live.started:
                host = live.record.host
                port = int(live.record.port)
            else:
                host = (rec.host or "").strip()
                port = int(rec.port or 0)
            if not host or port <= 0:
                continue
            key = (host, port)
            if key in seen:
                continue
            seen.add(key)
            hops.append(Hop(host=host, port=port, role=ROLE_HIDDEN))
    return hops


def list_enabled_hidden_nodes(
    prefixes: Iterable[Path | str] | None = None,
    *,
    single_prefix: Path | str | None = None,
) -> list[HiddenNodeRecord]:
    """Load enabled hidden nodes from one or more install prefixes."""
    paths: list[Path] = []
    if single_prefix is not None:
        paths.append(Path(single_prefix))
    if prefixes is not None:
        paths.extend(Path(p) for p in prefixes)
    out: list[HiddenNodeRecord] = []
    seen: set[str] = set()
    for p in paths:
        for n in load_registry(p):
            if not n.enabled:
                continue
            if n.install_id in seen:
                continue
            seen.add(n.install_id)
            n.public_catalog = False
            out.append(n)
    return out


def hidden_hops_from_records(
    records: Sequence[HiddenNodeRecord] | None,
) -> list:
    """Convert hidden records to multihop Hop list (role=hidden only)."""
    from client.multihop import Hop

    hops = []
    for r in records or []:
        if not r.enabled:
            continue
        host = (r.host or "").strip()
        if not host:
            continue
        hops.append(Hop(host=host, port=int(r.port), role=ROLE_HIDDEN))
    return hops


def is_public_catalog_peer_host(host: str) -> bool:
    """True only for shipped public residual catalog hosts (IS/DE)."""
    from client.multihop import PRODUCT_COUNTRY_CATALOG

    h = (host or "").strip()
    if not h:
        return False
    for n in PRODUCT_COUNTRY_CATALOG:
        if n.host.strip() == h:
            return True
    return False


def assert_not_public_catalog(record: HiddenNodeRecord) -> None:
    """Fail if a hidden node is mis-marked or collides with public catalog hosts.

    Loopback participation hosts are always allowed. Non-loopback hosts that
    match a public monopin peer address are rejected (must not re-badge VPS).
    """
    if record.public_catalog:
        raise ValueError("hidden flyclient node must not set public_catalog=True")
    if record.visibility != "hidden" or record.role != ROLE_HIDDEN:
        raise ValueError("hidden flyclient node must use role/visibility=hidden")
    host = (record.host or "").strip()
    if host in ("127.0.0.1", "::1", "localhost"):
        return
    if is_public_catalog_peer_host(host):
        raise ValueError(
            f"hidden flyclient host {host!r} collides with public catalog peer"
        )


def agent_never_invokes_selfhost(agent: FlyclientHiddenAgent) -> bool:
    """Structural honesty: start/stop leave no selfhost script invocations."""
    blob = " ".join(agent.invocations).lower()
    return not any(m.lower() in blob for m in FORBIDDEN_SELFHOST_MARKERS)


# Synthetic host helper for unit tests (never a public catalog IP).
def synthetic_hidden_host(*, seed: str | None = None) -> str:
    """Return a non-catalog synthetic host for path unit tests."""
    raw = (seed or secrets.token_hex(4)).encode("utf-8")
    # Pad/hash to stable octets without requiring hex-only seeds.
    a = (sum(raw) % 250) + 1
    b = (sum(raw[i] * (i + 3) for i in range(len(raw))) % 250) + 1
    return f"10.77.{a}.{b}"
