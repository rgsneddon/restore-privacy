"""Flyclient **hidden-node agent** for rpOS multi-hop participation.

Every rpOS install can register as a **hidden** intermediate hop in the product
multi-hop structure. This is a light agent (OBJECTIVE: flyclient) — it does
**not**:

- run full fleet selfhost / zram+LUKS node install scripts
- skip residual Connect HELLO (legacy residual HELLO-skip path — removed)
- appear as a public catalog residual entry/exit dial target

Resource posture is deliberately bounded: in-process registry + optional
loopback hook only; no disk crypto stack, no host wipe, no package reinstall.
"""

from __future__ import annotations

import json
import secrets
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
DEFAULT_HOOK_PORT = 44050  # local participation hook (not public residual dial)

REGISTRY_FILENAME = "flyclient_hidden_node.json"
INSTALL_MARKER_NAME = "RPOS_INSTALLED.json"


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


@dataclass
class FlyclientHiddenAgent:
    """In-process light agent state for one install instance."""

    record: HiddenNodeRecord
    started: bool = False
    # Audit: commands/scripts attempted (must stay empty of selfhost markers).
    invocations: list[str] = field(default_factory=list)

    def start(self) -> dict[str, Any]:
        """Start light participation hook — no selfhost / LUKS / zram."""
        if any(m in " ".join(self.invocations) for m in FORBIDDEN_SELFHOST_MARKERS):
            raise RuntimeError("hidden flyclient agent must not invoke selfhost stack")
        self.started = True
        self.record.running = True
        self.record.enabled = True
        return {
            "ok": True,
            "agent": AGENT_NAME,
            "kind": AGENT_KIND,
            "install_id": self.record.install_id,
            "running": True,
            "uses_selfhost": USES_SELFHOST_STACK,
            "uses_zram_luks": USES_ZRAM_LUKS,
            "uses_disk_crypto_install": USES_DISK_CRYPTO_INSTALL,
            "max_rss_mb": self.record.max_rss_mb,
            "max_cpu_percent": self.record.max_cpu_percent,
            "public_catalog": False,
            "visibility": "hidden",
            "invocations": list(self.invocations),
        }

    def stop(self) -> dict[str, Any]:
        self.started = False
        self.record.running = False
        return {
            "ok": True,
            "agent": AGENT_NAME,
            "install_id": self.record.install_id,
            "running": False,
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
        }


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
    host: str = "127.0.0.1",
    port: int = DEFAULT_HOOK_PORT,
    start: bool = True,
) -> HiddenNodeRecord:
    """Register (or refresh) this install as a hidden multi-hop node.

    Persists under *prefix*/flyclient_hidden_node.json. Never marks public_catalog.
    """
    pref = Path(prefix)
    pref.mkdir(parents=True, exist_ok=True)
    iid = (install_id or "").strip() or new_install_id()
    host_s = (host or "").strip() or "127.0.0.1"
    # Never allow empty host that could collide with public catalog semantics.
    if host_s in ("0.0.0.0", "::", "*"):
        host_s = "127.0.0.1"

    nodes = load_registry(pref)
    existing = next((n for n in nodes if n.install_id == iid), None)
    now = int(time.time())
    if existing is None:
        rec = HiddenNodeRecord(
            install_id=iid,
            host=host_s,
            port=int(port),
            registered_unix=now,
            prefix=str(pref),
        )
        nodes.append(rec)
    else:
        existing.host = host_s
        existing.port = int(port)
        existing.enabled = True
        existing.public_catalog = False
        existing.visibility = "hidden"
        existing.uses_selfhost = False
        existing.uses_zram_luks = False
        existing.prefix = str(pref)
        rec = existing

    agent = FlyclientHiddenAgent(record=rec)
    if start:
        agent.start()
    save_registry(pref, nodes)
    return rec


def enable_for_rpos_install(
    prefix: Path | str,
    *,
    install_id: str | None = None,
    host: str = "127.0.0.1",
    port: int | None = None,
) -> dict[str, Any]:
    """rpOS install-path entry: enable hidden flyclient node for this instance.

    Safe for dry-run / smoke: local registry only, no selfhost scripts.
    """
    pref = Path(prefix)
    # Stable id from install marker when present.
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

    # Ephemeral local port offset from id (still loopback-only participation).
    if port is None:
        # Deterministic-ish port in private range from install id entropy.
        digest = sum(ord(c) for c in iid) % 1000
        port = DEFAULT_HOOK_PORT + digest

    rec = register_instance(
        pref,
        install_id=iid,
        host=host,
        port=int(port),
        start=True,
    )
    agent = FlyclientHiddenAgent(record=rec)
    start_info = agent.start() if not rec.running else {
        "ok": True,
        "running": True,
        "agent": AGENT_NAME,
        "install_id": rec.install_id,
        "uses_selfhost": False,
        "uses_zram_luks": False,
        "public_catalog": False,
    }
    # Persist flags on install marker when present.
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
        marker.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "enabled": True,
        "install_id": rec.install_id,
        "agent": AGENT_NAME,
        "kind": AGENT_KIND,
        "role": ROLE_HIDDEN,
        "visibility": "hidden",
        "public_catalog": False,
        "host": rec.host,
        "port": rec.port,
        "registry": str(registry_path(pref)),
        "uses_selfhost": USES_SELFHOST_STACK,
        "uses_zram_luks": USES_ZRAM_LUKS,
        "uses_disk_crypto_install": USES_DISK_CRYPTO_INSTALL,
        "resource": agent.resource_posture(),
        "start": start_info,
        "record": rec.to_dict(),
    }


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
