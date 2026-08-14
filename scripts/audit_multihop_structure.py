"""Multihop node-structure probes for the security audit (timer path).

Structural / product-layout checks only. Does **not** claim live dual-relay residual
IP proof or full intermediate onion encapsulation.

Honesty baseline (1.2.6 catalog — **IS, US and RO residual peers retired**):
  - Default residual entry: Germany ``PRODUCT_DE_HOST`` / ``PRODUCT_EXIT_HOST``
    + ``product/de_node_elgamal.pub`` (exit pub may still be ``exit_node_elgamal.pub``)
  - Singapore ``PRODUCT_SG_HOST`` + ``product/sg_node_elgamal.pub``
  - Live product catalog peers are **DE + SG only** (see ``product_country_catalog``)
  - Retired ``PRODUCT_NODE_HOST`` (Iceland) / ``PRODUCT_US_HOST`` may still exist for
    redaction / legacy HELLO paths — **not** listed as active catalog peers
  - ``MULTI_HOP_ROUTING_IMPLEMENTED`` residual-via-exit when multi-hop is active
  - Default remains single-hop **DE** entry when multi-hop is not enabled
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Any, Mapping

DEFAULT_INSTALL_ROOT = Path(os.environ.get("RPT_INSTALL_ROOT", "/opt/restore-privacy"))

# Product monopin facts (must match client/multihop.py + client/endpoint.py)
EXPECTED_ICELAND_HOST = "82.221.101.241"  # retired monopin constant only
EXPECTED_SG_HOST = "5.223.48.8"
# Germany is default residual entry + multi-hop exit monopin
EXPECTED_EXIT_HOST = "178.105.187.178"
EXPECTED_DE_HOST = EXPECTED_EXIT_HOST
EXPECTED_ENTRY_HOST = EXPECTED_DE_HOST
EXPECTED_US_HOST = "5.161.242.85"
EXPECTED_PORT = 44044
EXPECTED_DEFAULT_ENTRY_COUNTRY = "DE"


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


def _pub_paths(
    repo: Path, install: Path
) -> tuple[Path | None, Path | None, Path | None]:
    """Locate IS/RO/US public keys under product/ (repo or install seed)."""
    entry = None
    exit_p = None
    us_p = None
    for base in (repo, install):
        e = base / "product" / "node_elgamal.pub"
        x = base / "product" / "exit_node_elgamal.pub"
        u = base / "product" / "us_node_elgamal.pub"
        if entry is None and e.is_file() and e.stat().st_size >= 32:
            entry = e
        if exit_p is None and x.is_file() and x.stat().st_size >= 32:
            exit_p = x
        if us_p is None and u.is_file() and u.stat().st_size >= 32:
            us_p = u
    return entry, exit_p, us_p


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

    # Active catalog peers: DE + SG only (IS/US/RO retired from live product catalog)
    sg_host = getattr(mh, "PRODUCT_SG_HOST", None)
    exit_host = getattr(mh, "PRODUCT_EXIT_HOST", None)
    de_host = getattr(mh, "PRODUCT_DE_HOST", None) or exit_host
    us_host = getattr(mh, "PRODUCT_US_HOST", None)  # retired constant may remain
    iceland_host = getattr(mh, "PRODUCT_NODE_HOST", None) or getattr(
        ep, "PRODUCT_NODE_HOST", None
    )
    entry_port = int(getattr(ep, "PRODUCT_NODE_PORT", EXPECTED_PORT) or EXPECTED_PORT)
    exit_port = int(getattr(mh, "PRODUCT_EXIT_PORT", entry_port) or entry_port)
    us_port = int(getattr(mh, "PRODUCT_US_PORT", entry_port) or entry_port)
    default_country = str(getattr(mh, "DEFAULT_ENTRY_COUNTRY", "") or "")

    if de_host != EXPECTED_DE_HOST:
        ok = False
        reasons.append(
            f"DE host {de_host!r} != product Germany pin {EXPECTED_DE_HOST}"
        )
    else:
        reasons.append(f"Germany peer {de_host}:{exit_port} (DE monopin / default entry)")

    if sg_host != EXPECTED_SG_HOST:
        ok = False
        reasons.append(
            f"Singapore host {sg_host!r} != product pin {EXPECTED_SG_HOST}"
        )
    else:
        reasons.append(f"Singapore peer {sg_host}:{entry_port} (SG monopin)")

    if exit_host != EXPECTED_EXIT_HOST:
        ok = False
        reasons.append(
            f"exit host {exit_host!r} != product Germany pin {EXPECTED_EXIT_HOST}"
        )
    else:
        reasons.append(f"Germany exit {exit_host}:{exit_port} (DE monopin)")

    # Live catalog must be DE+SG only — do not list IS/US/RO as active peers.
    try:
        catalog = list(mh.product_country_catalog())
        catalog_codes = {
            str(getattr(n, "code", "") or "").strip().upper() for n in catalog
        }
        live = {"DE", "SG"}
        retired = {"IS", "US", "RO"}
        if catalog_codes & retired:
            ok = False
            reasons.append(
                f"product_country_catalog still lists retired {sorted(catalog_codes & retired)}"
            )
        elif not live.issubset(catalog_codes):
            ok = False
            reasons.append(
                f"product_country_catalog codes {sorted(catalog_codes)!r} "
                "expected to include DE and SG"
            )
        else:
            reasons.append(
                "live catalog peers DE+SG only (Iceland / United States / Romania retired)"
            )
    except Exception as exc:  # noqa: BLE001
        reasons.append(f"catalog peer check skipped: {exc}")

    if default_country != EXPECTED_DEFAULT_ENTRY_COUNTRY:
        ok = False
        reasons.append(
            f"DEFAULT_ENTRY_COUNTRY={default_country!r} expected "
            f"{EXPECTED_DEFAULT_ENTRY_COUNTRY!r}"
        )
    else:
        reasons.append(
            f"DEFAULT_ENTRY_COUNTRY={EXPECTED_DEFAULT_ENTRY_COUNTRY} "
            "(product default residual entry = Germany)"
        )

    if sg_host == de_host:
        ok = False
        reasons.append("Singapore and Germany hosts must differ")

    if iceland_host and iceland_host == EXPECTED_ICELAND_HOST:
        reasons.append("retired Iceland monopin constant retained (not a live catalog peer)")

    return _status(
        ok=ok,
        skipped=False,
        reasons=reasons,
        entry_host=de_host,
        exit_host=exit_host,
        us_host=us_host,
        de_host=de_host,
        sg_host=sg_host,
        entry_port=entry_port,
        exit_port=exit_port,
        us_port=us_port,
        routing_implemented=bool(getattr(mh, "MULTI_HOP_ROUTING_IMPLEMENTED", False)),
    )


def probe_multihop_product_pubs(
    *,
    repo_root: Path | None = None,
    install_root: Path | None = None,
) -> dict[str, Any]:
    """Tracked IS/RO/US ElGamal public keys present, distinct, non-empty."""
    repo = repo_root or Path(__file__).resolve().parents[1]
    install = install_root or Path(
        os.environ.get("RPT_INSTALL_ROOT", str(DEFAULT_INSTALL_ROOT))
    )
    entry, exit_p, us_p = _pub_paths(repo, install)
    reasons: list[str] = []
    ok = True
    if entry is None:
        ok = False
        reasons.append("product/node_elgamal.pub missing or too small")
    else:
        reasons.append(f"IS pub present ({entry}) sha={_sha256_file(entry)[:16]}…")
    if exit_p is None:
        ok = False
        reasons.append("product/exit_node_elgamal.pub missing or too small")
    else:
        reasons.append(
            f"exit/DE pub present ({exit_p}) sha={_sha256_file(exit_p)[:16]}…"
        )
    if us_p is None:
        ok = False
        reasons.append("product/us_node_elgamal.pub missing or too small")
    else:
        reasons.append(f"US pub present ({us_p}) sha={_sha256_file(us_p)[:16]}…")
    if entry is not None and exit_p is not None:
        if entry.read_bytes() == exit_p.read_bytes():
            ok = False
            reasons.append("IS and exit/DE pubs must be distinct key material")
    if us_p is not None and entry is not None:
        if us_p.read_bytes() == entry.read_bytes():
            ok = False
            reasons.append("US and IS pubs must be distinct key material")
    if us_p is not None and exit_p is not None:
        if us_p.read_bytes() == exit_p.read_bytes():
            ok = False
            reasons.append("US and exit/DE pubs must be distinct key material")
    if entry is not None and exit_p is not None and us_p is not None:
        reasons.append("IS/exit-DE/US pubs present and pairwise distinct")
    return _status(
        ok=ok,
        skipped=False if (entry or exit_p or us_p) else True,
        reasons=reasons,
        entry_pub=str(entry) if entry else None,
        exit_pub=str(exit_p) if exit_p else None,
        us_pub=str(us_p) if us_p else None,
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

    # Non-exit entry (SG) → DE exit for residual-via-exit check (IS peer retired)
    sg_host = getattr(mh, "PRODUCT_SG_HOST", None) or EXPECTED_SG_HOST
    sg_port = int(getattr(mh, "PRODUCT_SG_PORT", EXPECTED_PORT) or EXPECTED_PORT)
    de_host = getattr(mh, "PRODUCT_EXIT_HOST", None) or EXPECTED_EXIT_HOST
    hops = [
        mh.Hop(sg_host, sg_port, role="entry"),
        mh.Hop(mh.PRODUCT_EXIT_HOST, mh.PRODUCT_EXIT_PORT, role="exit"),
    ]
    cfg = mh.MultiHopConfig(hops=hops, enabled=True)
    ok = True
    if not mh.is_multihop_active(cfg):
        ok = False
        reasons.append("is_multihop_active(enabled, 2 hops) is False")
    else:
        reasons.append("is_multihop_active=True for SG→DE entry→exit path")

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

    # Default single-hop honesty: product default country → DE monopin
    cfg_def = mh.multihop_config_for_entry_country(None, multihop_enabled=False)
    single = mh.residual_endpoint(cfg_def)
    if single.host != de_host:
        ok = False
        reasons.append(
            f"default single-hop residual {single.host!r} != DE {de_host}"
        )
    else:
        reasons.append(
            f"multi-hop disabled residual stays entry {single.host} "
            "(default single-hop DE)"
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
            "default single-hop Germany (DE) entry (RO replaced)"
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
| **Default entry / exit** (Germany) | `Germany (DE)` | `product/de_node_elgamal.pub` (exit alias: `exit_node_elgamal.pub`) |
| **Catalog peer** (Singapore) | `Singapore (SG)` | `product/sg_node_elgamal.pub` |

Live residual catalog is **DE + SG only**. Iceland, United States and Romania residual peers are **retired** (not current catalog peers).

"""
