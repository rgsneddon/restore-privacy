"""Multihop node-structure probes for the security audit (timer path).

Structural / product-layout checks only. Does **not** claim live dual-relay residual
IP proof or full intermediate onion encapsulation.

Honesty baseline (0.3.6+):
  - Entry: Iceland ``PRODUCT_NODE_HOST`` + ``product/node_elgamal.pub``
  - Exit: Romania ``PRODUCT_EXIT_HOST`` + ``product/exit_node_elgamal.pub`` (distinct)
  - ``MULTI_HOP_ROUTING_IMPLEMENTED`` residual-via-exit when multi-hop is active
  - Default remains single-hop entry when multi-hop is not enabled
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Any, Mapping

DEFAULT_INSTALL_ROOT = Path(os.environ.get("RPT_INSTALL_ROOT", "/opt/restore-privacy"))

# Product monopin facts (must match client/multihop.py + client/endpoint.py)
EXPECTED_ENTRY_HOST = "82.221.101.241"
EXPECTED_EXIT_HOST = "185.146.232.107"
EXPECTED_PORT = 44044


def _status(
    *,
    ok: bool = True,
    warn: bool = False,
    skipped: bool = False,
    reasons: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "ok": bool(ok),
        "warn": bool(warn),
        "skipped": bool(skipped),
        "reasons": list(reasons or []),
    }
    out.update(extra)
    return out


def _python_roots(repo: Path, install: Path) -> list[Path]:
    roots: list[Path] = []
    for base in (repo, install):
        if base not in roots:
            roots.append(base)
    return roots


def _import_multihop(repo: Path, install: Path):
    """Import client.multihop from monorepo or install-root seed."""
    last: Exception | None = None
    for base in _python_roots(repo, install):
        try:
            if str(base) not in sys.path:
                sys.path.insert(0, str(base))
            import client.multihop as mh  # type: ignore

            return mh
        except Exception as exc:  # noqa: BLE001
            last = exc
            continue
    raise ImportError(f"client.multihop unavailable: {last}")


def _import_endpoint(repo: Path, install: Path):
    last: Exception | None = None
    for base in _python_roots(repo, install):
        try:
            if str(base) not in sys.path:
                sys.path.insert(0, str(base))
            import client.endpoint as ep  # type: ignore

            return ep
        except Exception as exc:  # noqa: BLE001
            last = exc
            continue
    raise ImportError(f"client.endpoint unavailable: {last}")


def _pub_paths(repo: Path, install: Path) -> tuple[Path | None, Path | None]:
    """Locate entry/exit public keys under product/ (repo or install seed)."""
    entry = None
    exit_p = None
    for base in (repo, install):
        e = base / "product" / "node_elgamal.pub"
        x = base / "product" / "exit_node_elgamal.pub"
        if entry is None and e.is_file() and e.stat().st_size >= 32:
            entry = e
        if exit_p is None and x.is_file() and x.stat().st_size >= 32:
            exit_p = x
    return entry, exit_p


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().lower()


def probe_multihop_module_flags(
    *,
    repo_root: Path | None = None,
    install_root: Path | None = None,
) -> dict[str, Any]:
    """MULTI_HOP_ROUTING_IMPLEMENTED + entry/exit host monopin constants."""
    repo = repo_root or Path(__file__).resolve().parents[1]
    install = install_root or Path(
        os.environ.get("RPT_INSTALL_ROOT", str(DEFAULT_INSTALL_ROOT))
    )
    reasons: list[str] = []
    try:
        mh = _import_multihop(repo, install)
        ep = _import_endpoint(repo, install)
    except ImportError as exc:
        return _status(
            ok=False,
            skipped=True,
            reasons=[str(exc), "seed client/multihop.py + client/endpoint.py"],
        )

    ok = True
    if not getattr(mh, "MULTI_HOP_ROUTING_IMPLEMENTED", False):
        ok = False
        reasons.append("MULTI_HOP_ROUTING_IMPLEMENTED is False (stale product flag)")
    else:
        reasons.append("MULTI_HOP_ROUTING_IMPLEMENTED=True (residual-via-exit)")

    entry_host = getattr(ep, "PRODUCT_NODE_HOST", None) or getattr(
        mh, "PRODUCT_NODE_HOST", None
    )
    # multihop imports PRODUCT_NODE_HOST from endpoint
    entry_host = getattr(mh, "PRODUCT_NODE_HOST", entry_host)
    exit_host = getattr(mh, "PRODUCT_EXIT_HOST", None)
    entry_port = int(getattr(ep, "PRODUCT_NODE_PORT", EXPECTED_PORT) or EXPECTED_PORT)
    exit_port = int(getattr(mh, "PRODUCT_EXIT_PORT", entry_port) or entry_port)

    if entry_host != EXPECTED_ENTRY_HOST:
        ok = False
        reasons.append(
            f"entry host {entry_host!r} != product Iceland pin {EXPECTED_ENTRY_HOST}"
        )
    else:
        reasons.append(f"entry host {entry_host}:{entry_port} (Iceland monopin)")

    if exit_host != EXPECTED_EXIT_HOST:
        ok = False
        reasons.append(
            f"exit host {exit_host!r} != product Romania pin {EXPECTED_EXIT_HOST}"
        )
    else:
        reasons.append(f"exit host {exit_host}:{exit_port} (Romania monopin)")

    if entry_host == exit_host:
        ok = False
        reasons.append("entry and exit hosts must differ")

    return _status(
        ok=ok,
        skipped=False,
        reasons=reasons,
        entry_host=entry_host,
        exit_host=exit_host,
        entry_port=entry_port,
        exit_port=exit_port,
        routing_implemented=bool(getattr(mh, "MULTI_HOP_ROUTING_IMPLEMENTED", False)),
    )


def probe_multihop_product_pubs(
    *,
    repo_root: Path | None = None,
    install_root: Path | None = None,
) -> dict[str, Any]:
    """Tracked entry + exit ElGamal public keys present, distinct, non-empty."""
    repo = repo_root or Path(__file__).resolve().parents[1]
    install = install_root or Path(
        os.environ.get("RPT_INSTALL_ROOT", str(DEFAULT_INSTALL_ROOT))
    )
    entry, exit_p = _pub_paths(repo, install)
    reasons: list[str] = []
    ok = True
    if entry is None:
        ok = False
        reasons.append("product/node_elgamal.pub missing or too small")
    else:
        reasons.append(f"entry pub present ({entry}) sha={_sha256_file(entry)[:16]}…")
    if exit_p is None:
        ok = False
        reasons.append("product/exit_node_elgamal.pub missing or too small")
    else:
        reasons.append(f"exit pub present ({exit_p}) sha={_sha256_file(exit_p)[:16]}…")
    if entry is not None and exit_p is not None:
        if entry.read_bytes() == exit_p.read_bytes():
            ok = False
            reasons.append("entry and exit pubs must be distinct key material")
        else:
            reasons.append("entry and exit pubs are distinct")
    return _status(
        ok=ok,
        skipped=False if (entry or exit_p) else True,
        reasons=reasons,
        entry_pub=str(entry) if entry else None,
        exit_pub=str(exit_p) if exit_p else None,
    )


def probe_multihop_residual_via_exit(
    *,
    repo_root: Path | None = None,
    install_root: Path | None = None,
) -> dict[str, Any]:
    """When multi-hop is enabled with ≥2 hops, residual endpoint is the exit hop."""
    repo = repo_root or Path(__file__).resolve().parents[1]
    install = install_root or Path(
        os.environ.get("RPT_INSTALL_ROOT", str(DEFAULT_INSTALL_ROOT))
    )
    reasons: list[str] = []
    try:
        mh = _import_multihop(repo, install)
    except ImportError as exc:
        return _status(ok=False, skipped=True, reasons=[str(exc)])

    hops = [
        mh.Hop(mh.PRODUCT_NODE_HOST, mh.PRODUCT_NODE_PORT, role="entry"),
        mh.Hop(mh.PRODUCT_EXIT_HOST, mh.PRODUCT_EXIT_PORT, role="exit"),
    ]
    cfg = mh.MultiHopConfig(hops=hops, enabled=True)
    ok = True
    if not mh.is_multihop_active(cfg):
        ok = False
        reasons.append("is_multihop_active(enabled, 2 hops) is False")
    else:
        reasons.append("is_multihop_active=True for entry→exit path")

    residual = mh.residual_endpoint(cfg)
    if residual.host != mh.PRODUCT_EXIT_HOST:
        ok = False
        reasons.append(
            f"residual_endpoint host {residual.host!r} != exit {mh.PRODUCT_EXIT_HOST}"
        )
    else:
        reasons.append(
            f"residual_endpoint dials exit {residual.host}:{residual.port} "
            "(residual-via-exit)"
        )

    # Default single-hop honesty
    cfg_off = mh.MultiHopConfig(hops=hops, enabled=False)
    single = mh.residual_endpoint(cfg_off)
    if single.host != mh.PRODUCT_NODE_HOST:
        ok = False
        reasons.append(
            f"disabled multi-hop residual {single.host!r} != entry {mh.PRODUCT_NODE_HOST}"
        )
    else:
        reasons.append(
            f"multi-hop disabled residual stays entry {single.host} (default single-hop)"
        )

    status = mh.multihop_status_text(cfg)
    low = status.lower()
    if "residual via" not in low and "residual" not in low:
        ok = False
        reasons.append(f"status text missing residual-via-exit honesty: {status!r}")
    else:
        reasons.append(f"status text: {status}")

    # Must not claim full intermediate onion residual
    if "full intermediate" in low or "onion encapsulation" in low:
        ok = False
        reasons.append("status over-claims intermediate encapsulation")

    return _status(ok=ok, skipped=False, reasons=reasons, status_text=status)


def probe_multihop_node_host_layout(
    *,
    repo_root: Path | None = None,
    install_root: Path | None = None,
) -> dict[str, Any]:
    """Node-only multi-hop host recipes (zram+LUKS2) present — clients never ship them."""
    repo = repo_root or Path(__file__).resolve().parents[1]
    install = install_root or Path(
        os.environ.get("RPT_INSTALL_ROOT", str(DEFAULT_INSTALL_ROOT))
    )
    reasons: list[str] = []
    names = ("install_zram_luks.sh", "install_host_privacy.sh")
    found: list[Path] = []
    seen: set[str] = set()
    for name in names:
        for base in (install, repo):
            p = base / "node" / name
            try:
                key = str(p.resolve()) if p.is_file() else ""
            except OSError:
                key = ""
            if p.is_file() and key and key not in seen:
                seen.add(key)
                found.append(p)
                break  # one path per recipe name
    if not found:
        return _status(
            ok=True,
            skipped=True,
            warn=False,
            reasons=[
                "node multi-hop host recipes not seeded on this host "
                "(install_zram_luks / install_host_privacy)"
            ],
        )
    for p in found:
        reasons.append(f"present: {p}")
    reasons.append("node-only: clients never install LUKS/zram")
    return _status(ok=True, skipped=False, reasons=reasons)


def run_all_multihop_structure_probes(
    *,
    repo_root: Path | None = None,
    install_root: Path | None = None,
) -> dict[str, Any]:
    """Aggregate multihop node-structure probes for the audit writer."""
    repo = repo_root or Path(__file__).resolve().parents[1]
    install = install_root or Path(
        os.environ.get("RPT_INSTALL_ROOT", str(DEFAULT_INSTALL_ROOT))
    )
    probes = {
        "multihop_module_flags": probe_multihop_module_flags(
            repo_root=repo, install_root=install
        ),
        "multihop_product_pubs": probe_multihop_product_pubs(
            repo_root=repo, install_root=install
        ),
        "multihop_residual_via_exit": probe_multihop_residual_via_exit(
            repo_root=repo, install_root=install
        ),
        "multihop_node_host_layout": probe_multihop_node_host_layout(
            repo_root=repo, install_root=install
        ),
    }
    # Hard fail if module flags, pubs, or residual-via-exit fail (not skip)
    hard = False
    for name in (
        "multihop_module_flags",
        "multihop_product_pubs",
        "multihop_residual_via_exit",
    ):
        p = probes[name]
        if p.get("skipped"):
            hard = True
        elif not p.get("ok"):
            hard = True
    return {
        "probes": probes,
        "ok": not hard,
        "section": "multihop_node_structure",
        "honesty": (
            "residual-via-exit when multi-hop enabled; "
            "not full intermediate onion encapsulation; "
            "default single-hop United States entry"
        ),
    }


def render_multihop_structure_markdown(
    section: Mapping[str, Any] | None,
) -> str:
    """Markdown section for AUDIT.md — multihop node structure."""
    if not section:
        return ""
    probes = section.get("probes") or {}
    rows: list[str] = []
    for name, data in probes.items():
        if not isinstance(data, dict):
            continue
        if data.get("skipped"):
            state = "SKIP"
        elif data.get("warn") and data.get("ok"):
            state = "WARN"
        elif data.get("ok"):
            state = "PASS"
        else:
            state = "FAIL"
        why = "; ".join(str(x) for x in (data.get("reasons") or [])[:4]) or "—"
        if len(why) > 180:
            why = why[:177] + "..."
        rows.append(f"| **{name}** | **{state}** | {why} |")
    table = "\n".join(rows) if rows else "| — | SKIP | no probes |"
    overall = "PASS" if section.get("ok") else "FAIL"
    honesty = section.get("honesty") or (
        "residual-via-exit when enabled; default single-hop entry"
    )
    return f"""## Multihop node structure (audit timer)

Structural product-layout checks for multi-hop residual (**entry → exit**).  
Honesty: **{honesty}**.

| Probe | State | Notes |
|-------|-------|-------|
{table}

**Multihop structure overall:** **{overall}**

| Role | Host | Public key |
|------|------|------------|
| **Entry** (Iceland) | `{EXPECTED_ENTRY_HOST}:{EXPECTED_PORT}` | `product/node_elgamal.pub` |
| **Exit** (Romania) | `{EXPECTED_EXIT_HOST}:{EXPECTED_PORT}` | `product/exit_node_elgamal.pub` |

"""
