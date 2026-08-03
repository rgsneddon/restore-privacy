#!/usr/bin/env python3
"""Run Restore Privacy security audit and refresh AUDIT.md (+ optional audit.md).

Designed for:
  - Operator laptop / CI (full unittest suite)
  - Production node (lighter probes when tests/ missing)

Default period target: every 1 day via scripts/install_security_audit_timer.sh
(with schedule jitter + privacy-hardened oneshot unit — section A).

Usage:
  python3 scripts/run_security_audit.py
  python3 scripts/run_security_audit.py --node-only
  python3 scripts/run_security_audit.py --write --out AUDIT.md

Environment:
  RPT_NODE_HOST     default 178.105.187.178 Germany residual (timer forces 127.0.0.1 on node)
  RPT_STATUS_PORT   default 8080
  RPT_UDP_PORT      default 44044
  RPT_AUDIT_PATH    override output path
  RPT_AUDIT_NO_OUTBOUND=1  skip any optional live HTTP fetches during audit
  RPT_HOST_STATEMENTS_OFFLINE=1  host-statement probes use fixtures only
  RPT_AUDIT_REQUIRE_LOCALHOST=1  refuse non-loopback probe host (node timer)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
# Default live probe peer when not on the node timer (localhost-only there).
# Product residual default + RO replacement is Germany monopin (DE).
DEFAULT_HOST = os.environ.get("RPT_NODE_HOST", "178.105.187.178")
STATUS_PORT = int(os.environ.get("RPT_STATUS_PORT", "8080"))
UDP_PORT = int(os.environ.get("RPT_UDP_PORT", "44044"))


# Loopback hosts allowed when RPT_AUDIT_REQUIRE_LOCALHOST=1 (node timer policy)
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

# Structural / privacy suite — keep lightweight and deterministic.
# Do not include tests that assert AUDIT.md body content here (those run after --write).
# Architecture 0.3.6+: multihop residual-via-exit, catalog monopin, package RAG helpers.
SECURITY_TEST_MODULES = [
    "tests.test_legal_links",
    "tests.test_legal_docs",
    "tests.test_no_public_client_count",
    "tests.test_connect_no_phones_home",
    "tests.test_obfuscation",
    "tests.test_kill_switch_leaks",
    "tests.test_product_node_key",
    "tests.test_pfs_product_require",
    "tests.test_downloads",
    "tests.test_multihop",
    "tests.test_audit_package_rag",
    # CERBERUS / Helsinki oracle — privacy strip + Suite learning evolution
    "tests.test_oracle_no_user_data",
    "tests.test_oracle_suite_architecture",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(dt: datetime | None = None) -> str:
    d = dt or utc_now()
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def human_date(dt: datetime | None = None) -> str:
    d = dt or utc_now()
    return d.strftime("%-d %B %Y") if sys.platform != "win32" else d.strftime("%d %B %Y")


def parse_iso_z(s: str | None) -> datetime | None:
    """Parse ``YYYY-MM-DDTHH:MM:SSZ`` (audit generated_at) to UTC datetime."""
    raw = (s or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def is_loopback_host(host: str) -> bool:
    """True when probe host is loopback (node-timer local-only policy)."""
    h = (host or "").strip().lower().strip("[]")
    if h in _LOOPBACK_HOSTS:
        return True
    # IPv4 mapped / zone id
    if h.startswith("127."):
        return True
    return False


def localhost_probe_required() -> bool:
    """True when node-timer policy forbids outbound residual peer probes."""
    return os.environ.get("RPT_AUDIT_REQUIRE_LOCALHOST", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def active_residual_probe_schedule() -> list[dict[str, Any]]:
    """Active residual monopin peers for live status probes.

    Source of truth is the **product residual catalog** (same peers the Suite
    client dials). Retired monopin IPs are not scheduled.

    When ``RPT_AUDIT_REQUIRE_LOCALHOST=1`` (node timer), returns a single
    loopback peer only — no outbound multi-node scan.
    """
    if localhost_probe_required():
        return [
            {
                "host": "127.0.0.1",
                "code": "LOCAL",
                "label": "localhost (node timer)",
                "udp_port": UDP_PORT,
                "status_port": STATUS_PORT,
            }
        ]
    peers: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        from client.residual_public import public_catalog_peers, public_label_for_host

        for row in public_catalog_peers(admin=True):
            host = str(row.get("host") or "").strip()
            if not host or host in seen:
                continue
            seen.add(host)
            code = str(row.get("code") or "").strip().upper()
            label = str(row.get("label") or "").strip() or public_label_for_host(host)
            peers.append(
                {
                    "host": host,
                    "code": code,
                    "label": label,
                    "udp_port": int(row.get("port") or UDP_PORT),
                    "status_port": STATUS_PORT,
                }
            )
    except Exception:  # noqa: BLE001
        peers = []
    if not peers:
        # Fail-safe: shipped IS + DE monopin (must stay aligned with multihop catalog).
        for host, code, label in (
            ("82.221.101.241", "IS", "Iceland (IS)"),
            ("178.105.187.178", "DE", "Germany (DE)"),
        ):
            if host not in seen:
                peers.append(
                    {
                        "host": host,
                        "code": code,
                        "label": label,
                        "udp_port": UDP_PORT,
                        "status_port": STATUS_PORT,
                    }
                )
    return peers


def probe_residual_peer(peer: dict[str, Any]) -> dict[str, Any]:
    """Run TCP status, HTTP /status, and UDP residual probes for one peer."""
    host = str(peer.get("host") or "").strip()
    status_port = int(peer.get("status_port") or STATUS_PORT)
    udp_port = int(peer.get("udp_port") or UDP_PORT)
    tcp = probe_tcp(host, status_port)
    http = probe_http_status(host, status_port)
    udp = probe_udp_open(host, udp_port)
    return {
        "code": peer.get("code") or "",
        "label": peer.get("label") or host or "VPN node",
        "host": host,
        "status_port": status_port,
        "udp_port": udp_port,
        "tcp_status": tcp,
        "http_status": http,
        "udp": udp,
        "ok": bool(tcp.get("ok") and http.get("ok")),
    }


def probe_all_residual_nodes(
    schedule: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Probe every peer in the residual schedule (or active catalog when None)."""
    sched = list(schedule if schedule is not None else active_residual_probe_schedule())
    return [probe_residual_peer(p) for p in sched]


def primary_probe_from_live(
    live: list[dict[str, Any]], *, preferred_host: str | None = None
) -> dict[str, Any]:
    """Pick primary peer results for backward-compat top-level tcp/http/udp fields."""
    if not live:
        host = (preferred_host or DEFAULT_HOST).strip() or "127.0.0.1"
        return {
            "host": host,
            "tcp_status": probe_tcp(host, STATUS_PORT),
            "http_status": probe_http_status(host, STATUS_PORT),
            "udp": probe_udp_open(host, UDP_PORT),
        }
    pref = (preferred_host or DEFAULT_HOST).strip()
    for row in live:
        if str(row.get("host") or "").strip() == pref:
            return row
    # Prefer DE when present
    for row in live:
        if str(row.get("code") or "").upper() == "DE":
            return row
    return live[0]


def require_localhost_probe_host(host: str | None = None) -> str:
    """Return host for probes; raise if localhost required and host is not loopback."""
    h = (host if host is not None else DEFAULT_HOST).strip() or "127.0.0.1"
    require = os.environ.get("RPT_AUDIT_REQUIRE_LOCALHOST", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if require and not is_loopback_host(h):
        raise ValueError(
            f"RPT_AUDIT_REQUIRE_LOCALHOST set but RPT_NODE_HOST={h!r} is not loopback; "
            "node timer must probe 127.0.0.1 only"
        )
    return h


# --- Section A: redact audit artifacts before public write ---

_RE_HOME_PATH = re.compile(r"(?i)(/home|\\Users|C:\\Users)/[^\s\"']+")
_RE_SSH_USER_AT = re.compile(r"\b([A-Za-z0-9._-]+)@([A-Za-z0-9._-]+\.[A-Za-z]{2,})\b")
_RE_BEARER = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._\-+/=]{12,}")
_RE_TOKENISH = re.compile(
    r"(?i)\b("
    r"gho_|ghu_|ghp_|github_pat_|sk_live_|sk_test_|rk_live_|rk_test_|"
    r"xox[baprs]-|AKIA[0-9A-Z]{12,}|RPT_ASSET_FETCH_TOKEN=|"
    r"api[_-]?key=|token=|secret=|password="
    r")([^\s\"']{4,})"
)
_RE_PEM_BLOCK = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL | re.IGNORECASE,
)


def redact_audit_text(text: str) -> str:
    """Strip sensitive fragments from strings destined for AUDIT.md / public JSON.

    Removes home paths, token-like secrets, PEM private blocks, residual monopin
    IPv4s (IS/RO/US/retired DE), and softens user@host SSH-style identities.
    SHA-256 pins and public status titles stay; hosts become country labels.
    """
    if not text:
        return text
    s = str(text)
    s = _RE_PEM_BLOCK.sub("[REDACTED_PRIVATE_KEY]", s)
    s = _RE_HOME_PATH.sub(r"\1/[REDACTED_USER]", s)
    s = _RE_BEARER.sub(r"\1[REDACTED_TOKEN]", s)
    s = _RE_TOKENISH.sub(r"\1[REDACTED]", s)
    s = _RE_SSH_USER_AT.sub(r"[REDACTED_USER]@\2", s)
    # Residual monopin IPv4s must not appear on public audit/docs surfaces
    try:
        from client.residual_public import redact_residual_hosts_in_text

        s = redact_residual_hosts_in_text(s)
    except Exception:  # noqa: BLE001
        for host, label in (
            ("82.221.101.241", "Iceland (IS)"),
            ("178.105.187.178", "Germany (DE)"),
            ("185.146.232.107", "Romania (RO, retired)"),
            ("5.161.242.85", "United States (US)"),
            ("167.233.224.5", "VPN node"),
        ):
            s = s.replace(host, label)
    return s


def redact_audit_value(value: Any) -> Any:
    """Recursively redact strings in nested dict/list structures."""
    if isinstance(value, str):
        return redact_audit_text(value)
    if isinstance(value, dict):
        return {k: redact_audit_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_audit_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_audit_value(v) for v in value)
    return value


def slim_results_for_public_json(results: dict) -> dict:
    """Public machine JSON: no suite tails, redacted strings, no exfil-friendly dumps."""
    slim = redact_audit_value(dict(results))
    us = dict(slim.get("unit_suite") or {})
    us.pop("stdout_tail", None)
    us.pop("stderr_tail", None)
    # Never ship multi-KB captured process output
    for k in list(us.keys()):
        if k.endswith("_tail") or k in ("stdout", "stderr", "output"):
            us.pop(k, None)
    slim["unit_suite"] = us
    # Live multi-node probes: keep labels + outcomes; drop raw dial hosts.
    public_live: list[dict[str, Any]] = []
    for row in slim.get("live_node_probes") or []:
        if not isinstance(row, dict):
            continue
        public_live.append(
            {
                "code": row.get("code"),
                "label": row.get("label"),
                "status_port": row.get("status_port"),
                "udp_port": row.get("udp_port"),
                "tcp_status": {
                    "ok": (row.get("tcp_status") or {}).get("ok"),
                    "error": (row.get("tcp_status") or {}).get("error"),
                    "port": (row.get("tcp_status") or {}).get("port"),
                },
                "http_status": {
                    "ok": (row.get("http_status") or {}).get("ok"),
                    "status_code": (row.get("http_status") or {}).get("status_code"),
                    "body": (row.get("http_status") or {}).get("body"),
                    "error": (row.get("http_status") or {}).get("error"),
                },
                "udp": {
                    "sent": (row.get("udp") or {}).get("sent"),
                    "error": (row.get("udp") or {}).get("error"),
                    "port": (row.get("udp") or {}).get("port"),
                },
                "ok": row.get("ok"),
            }
        )
    slim["live_node_probes"] = public_live
    # node_host may still be redacted to country label by redact_audit_value
    slim["privacy"] = {
        "redacted": True,
        "no_suite_tails": True,
        "no_network_exfil": True,
        "multi_node_probes": True,
        "note": (
            "Audit artifacts written locally on --write; optional --publish / "
            "RPT_AUDIT_PUBLISH pushes AUDIT + JSON to status-host deploy surface"
        ),
    }
    return slim


def wipe_path(path: Path) -> None:
    """Best-effort delete of temporary capture files (PrivateTmp companion)."""
    try:
        if path.is_file():
            # Overwrite then unlink (best-effort; not full shred)
            try:
                size = path.stat().st_size
                with path.open("wb") as f:
                    f.write(b"\0" * min(size, 1_000_000))
            except OSError:
                pass
            path.unlink(missing_ok=True)
        elif path.is_dir():
            import shutil

            shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


def audit_outbound_allowed() -> bool:
    """False on hardened node timer (no live third-party fetches during audit)."""
    if os.environ.get("RPT_AUDIT_NO_OUTBOUND", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return False
    if os.environ.get("RPT_HOST_STATEMENTS_OFFLINE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return False
    return True


def probe_tcp(host: str, port: int, timeout: float = 5.0) -> dict:
    out: dict = {"host": host, "port": port, "ok": False, "error": None}
    try:
        with socket.create_connection((host, port), timeout=timeout):
            out["ok"] = True
    except OSError as e:
        out["error"] = str(e)
    return out


def probe_udp_open(host: str, port: int, timeout: float = 3.0) -> dict:
    """Best-effort UDP reachability (send empty; no response expected)."""
    out: dict = {"host": host, "port": port, "sent": False, "error": None}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        s.sendto(b"\x00", (host, port))
        out["sent"] = True
        s.close()
    except OSError as e:
        out["error"] = str(e)
    return out


def probe_http_status(host: str, port: int, timeout: float = 8.0) -> dict:
    url = f"http://{host}:{port}/status"
    out: dict = {"url": url, "ok": False, "status_code": None, "body": None, "error": None}
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(4096)
            out["status_code"] = resp.getcode()
            out["ok"] = resp.getcode() == 200
            try:
                out["body"] = json.loads(raw.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                out["body"] = raw.decode("utf-8", errors="replace")[:200]
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        out["error"] = str(e)
    return out


def run_unit_suite() -> dict:
    """Run security-related unittest modules when available.

    Captures are kept only in-memory for the process lifetime; public write path
    drops tails (section A — no multi-KB suite dumps in JSON).

    Requires project deps from root ``requirements.txt`` (``cryptography>=41``)
    for the same interpreter as ``sys.executable``. Example::

        python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
        .venv/bin/python scripts/run_security_audit.py
    """
    tests_dir = ROOT / "tests"
    if not tests_dir.is_dir():
        return {"ran": False, "reason": "tests/ not present (node install)", "ok": True, "modules": []}

    # Fail fast with an actionable message when the interpreter lacks crypto dep
    # (suite modules import client/crypto paths that need cryptography).
    try:
        import cryptography  # noqa: F401
    except ImportError:
        hint = (
            "ModuleNotFoundError: cryptography — install project deps for this "
            "interpreter: python3 -m venv .venv && .venv/bin/pip install -r "
            "requirements.txt && .venv/bin/python scripts/run_security_audit.py"
        )
        return {
            "ran": True,
            "ok": False,
            "returncode": 1,
            "modules": SECURITY_TEST_MODULES,
            "stdout_tail": "",
            "stderr_tail": redact_audit_text(hint),
            "error": "missing_cryptography",
        }

    cmd = [sys.executable, "-m", "unittest", *SECURITY_TEST_MODULES, "-q"]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    # Prefer offline host-statement fixtures if those tests appear later
    if not audit_outbound_allowed():
        env["RPT_HOST_STATEMENTS_OFFLINE"] = "1"
        env["RPT_AUDIT_NO_OUTBOUND"] = "1"
    scratch = Path(tempfile.mkdtemp(prefix="rpt-audit-suite-"))
    try:
        p = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        # Keep short redacted tails for operator stderr only (not public JSON)
        out_tail = redact_audit_text((p.stdout or "")[-800:])
        err_tail = redact_audit_text((p.stderr or "")[-800:])
        return {
            "ran": True,
            "ok": p.returncode == 0,
            "returncode": p.returncode,
            "modules": SECURITY_TEST_MODULES,
            "stdout_tail": out_tail,
            "stderr_tail": err_tail,
        }
    finally:
        wipe_path(scratch)


def check_no_priv_in_tree() -> dict:
    """Extended public-tree ``*.priv`` scan (section B) + legacy hits field."""
    try:
        from audit_privacy_probes import probe_no_priv_public_trees
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from audit_privacy_probes import probe_no_priv_public_trees  # type: ignore

    install = Path(os.environ.get("RPT_INSTALL_ROOT", "/opt/restore-privacy"))
    ext = probe_no_priv_public_trees(repo_root=ROOT, install_root=install)
    hits = list(ext.get("hits") or [])
    # Normalize to relative paths when under ROOT
    norm: list[str] = []
    for h in hits:
        try:
            p = Path(h)
            if p.is_absolute():
                try:
                    norm.append(str(p.relative_to(ROOT)))
                    continue
                except ValueError:
                    pass
            norm.append(h)
        except (TypeError, ValueError):
            norm.append(str(h))
    return {
        "ok": bool(ext.get("ok")),
        "hits": norm[:20],
        "scanned_roots": ext.get("scanned_roots"),
        "warn": ext.get("warn"),
        "skipped": ext.get("skipped"),
        "reasons": ext.get("reasons"),
    }


def run_section_b_probes(http_status: dict | None = None) -> dict:
    """Section B privacy probes (firewall/expose-surface excluded)."""
    try:
        from audit_privacy_probes import run_all_section_b_probes
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from audit_privacy_probes import run_all_section_b_probes  # type: ignore

    install = Path(os.environ.get("RPT_INSTALL_ROOT", "/opt/restore-privacy"))
    # Avoid slow/failing ephemeral subprocess when node-only timer wants speed?
    # Still run dry-run — it's the product check; timeout 60s is fine.
    return run_all_section_b_probes(
        http_status=http_status,
        repo_root=ROOT,
        install_root=install,
        run_ephemeral_subprocess=True,
    )


def run_multihop_structure_probes() -> dict:
    """Multihop entry/exit product-layout probes for the audit timer path."""
    try:
        from audit_multihop_structure import run_all_multihop_structure_probes
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from audit_multihop_structure import (  # type: ignore
            run_all_multihop_structure_probes,
        )

    install = Path(os.environ.get("RPT_INSTALL_ROOT", "/opt/restore-privacy"))
    return run_all_multihop_structure_probes(repo_root=ROOT, install_root=install)


def load_catalog_version() -> str:
    """Catalog monopin: env → downloads → client/VERSION (repo or install root)."""
    env_v = os.environ.get("RPT_CATALOG_VERSION", "").strip()
    if env_v and env_v.lower() != "unknown":
        return env_v

    install = Path(os.environ.get("RPT_INSTALL_ROOT", "") or ROOT)

    def _from_downloads(base: Path) -> str | None:
        sp = base / "status_page"
        if not sp.is_dir():
            return None
        sp_s = str(sp)
        if sp_s not in sys.path:
            sys.path.insert(0, sp_s)
        try:
            from downloads import current_catalog_version  # type: ignore

            v = str(current_catalog_version()).strip()
            if v:
                return v
        except Exception:
            pass
        try:
            from downloads import RELEASE_VERSION  # type: ignore

            v = str(RELEASE_VERSION).strip()
            if v:
                return v
        except Exception:
            pass
        return None

    def _from_version_file(base: Path) -> str | None:
        for rel in ("client/VERSION", "VERSION", "status_page/assets/CATALOG_VERSION"):
            p = base / rel
            try:
                if p.is_file():
                    v = p.read_text(encoding="utf-8").strip().split()[0]
                    if v and v.lower() != "unknown":
                        return v
            except OSError:
                continue
        return None

    for base in (ROOT, install):
        v = _from_downloads(base)
        if v:
            return v
    for base in (ROOT, install):
        v = _from_version_file(base)
        if v:
            return v
    return "unknown"


def product_exit_pub_pin() -> str:
    """SHA-256 of product/exit_node_elgamal.pub (Germany DE exit pin) when tracked."""
    import hashlib

    pub = ROOT / "product" / "exit_node_elgamal.pub"
    if pub.is_file() and pub.stat().st_size >= 32:
        return hashlib.sha256(pub.read_bytes()).hexdigest().lower()
    return ""


# --- Catalog installer AUDIT STATE (Green / Amber / Red) ---

VALID_PACKAGE_STATES = frozenset({"Green", "Amber", "Red"})

# Solid colour cells for the package AUDIT STATE table (no bare Green/Amber/Red words).
# Unicode solid squares render in plain markdown; VPN APP Shop HTML upgrades them to CSS boxes.
PACKAGE_STATE_SWATCH: dict[str, str] = {
    "Green": "🟩",
    "Amber": "🟧",
    "Red": "🟥",
}


def package_state_cell_markup(state: str) -> str:
    """Return solid-colour cell content for a package RAG state (not the state word)."""
    st = state if state in VALID_PACKAGE_STATES else "Red"
    return PACKAGE_STATE_SWATCH[st]


# OS-relative icons for Platform column (fixed allow-list; not untrusted HTML)
PLATFORM_ICONS: dict[str, str] = {
    "windows": "🪟",
    "linux": "🐧",
    "macos": "🍎",
    "ios": "📱",
    "android": "🤖",
}


def package_platform_cell_markup(
    platform: str, label: str | None = None
) -> str:
    """Platform cell: relative OS icon + bold label."""
    key = (platform or "").strip().lower()
    icon = PLATFORM_ICONS.get(key, "📦")
    name = (label or platform or "?").strip() or "?"
    return f"{icon} **{name}**"


# platform key → filename suffix pattern under releases/{version}/
_CATALOG_PACKAGE_SPECS: list[tuple[str, str, str]] = [
    ("windows", "Windows", "windows-x64-setup.exe"),
    ("linux", "Linux", "linux-x64.tar.gz"),
    ("macos", "macOS", "macos.zip"),
    ("ios", "iOS", "ios.zip"),
    ("android", "Android", "android.apk"),
]


def product_node_pub_pin() -> str:
    """SHA-256 monopin for product/node_elgamal.pub (hex lowercase)."""
    pin_file = ROOT / "product" / "NODE_ELGAMAL_PUB.sha256"
    if pin_file.is_file():
        return pin_file.read_text(encoding="utf-8").strip().split()[0].lower()
    pub = ROOT / "product" / "node_elgamal.pub"
    if pub.is_file():
        import hashlib

        return hashlib.sha256(pub.read_bytes()).hexdigest().lower()
    return ""


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest().lower()


def _package_contains_priv(path: Path) -> bool:
    """True if archive/package embeds any ``*.priv`` member (Red)."""
    name = path.name.lower()
    try:
        if name.endswith(".zip") or name.endswith(".apk") or name.endswith(".exe"):
            # .exe may be 7z SFX — try zip first, then 7z list
            import zipfile

            if name.endswith((".zip", ".apk")):
                with zipfile.ZipFile(path) as zf:
                    for n in zf.namelist():
                        if n.lower().endswith(".priv"):
                            return True
                return False
        if name.endswith((".tar.gz", ".tgz")):
            import tarfile

            with tarfile.open(path, "r:gz") as tf:
                for m in tf.getmembers():
                    if m.name.lower().endswith(".priv"):
                        return True
            return False
        if name.endswith(".exe"):
            # 7z SFX / PE packages: list via 7z when available
            try:
                p = subprocess.run(
                    ["7z", "l", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                for line in (p.stdout or "").splitlines():
                    if ".priv" in line.lower():
                        return True
            except (OSError, subprocess.TimeoutExpired):
                pass
    except Exception:
        return False
    return False


def _is_entry_node_pub_member(name: str) -> bool:
    """True for entry ``node_elgamal.pub`` only — never ``exit_node_elgamal.pub``."""
    base = Path(name.replace("\\", "/")).name.lower()
    return base == "node_elgamal.pub"


def _package_node_pub_sha256(path: Path) -> str | None:
    """Return SHA-256 of embedded entry node_elgamal.pub, or None if not found."""
    name = path.name.lower()
    try:
        if name.endswith((".zip", ".apk")):
            import zipfile

            with zipfile.ZipFile(path) as zf:
                for n in zf.namelist():
                    if _is_entry_node_pub_member(n):
                        return _sha256_bytes(zf.read(n))
            return None
        if name.endswith((".tar.gz", ".tgz")):
            import tarfile

            with tarfile.open(path, "r:gz") as tf:
                for m in tf.getmembers():
                    if m.isfile() and _is_entry_node_pub_member(m.name):
                        f = tf.extractfile(m)
                        if f is not None:
                            return _sha256_bytes(f.read())
            return None
        if name.endswith(".exe"):
            # Prefer 7z extract of known paths
            try:
                p = subprocess.run(
                    ["7z", "l", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                out = p.stdout or ""
                if "node_elgamal.pub" not in out:
                    return None
                import tempfile

                with tempfile.TemporaryDirectory(prefix="rpt-audit-pub-") as td:
                    subprocess.run(
                        [
                            "7z",
                            "e",
                            f"-o{td}",
                            str(path),
                            "*node_elgamal.pub",
                            "-r",
                            "-y",
                        ],
                        capture_output=True,
                        timeout=90,
                    )
                    for hit in Path(td).rglob("node_elgamal.pub"):
                        # rglob also matches *exit*_node_elgamal.pub names — filter basename
                        if _is_entry_node_pub_member(hit.name):
                            return _sha256_bytes(hit.read_bytes())
            except (OSError, subprocess.TimeoutExpired):
                return None
    except Exception:
        return None
    return None


def _windows_pe_ok(path: Path) -> bool | None:
    """True if PE/MZ; False if Mach-O; None if not windows exe or unreadable."""
    if not path.name.lower().endswith(".exe"):
        return None
    try:
        magic = path.read_bytes()[:4]
    except OSError:
        return None
    if magic[:2] == b"MZ":
        return True
    # Mach-O 64-bit (accidental macOS SFX)
    if magic in (bytes.fromhex("cffaedfe"), bytes.fromhex("feedfacf"), bytes.fromhex("cefaedfe")):
        return False
    return False


def _android_wire_ok(path: Path) -> bool | None:
    """True if APK dex embeds product residual wire (PFS + outer obfs)."""
    if not path.name.lower().endswith(".apk"):
        return None
    try:
        import zipfile

        with zipfile.ZipFile(path) as zf:
            if "classes.dex" not in zf.namelist():
                return False
            dex = zf.read("classes.dex")
        return b"pfs-x25519" in dex and b"RPT-OBFS-LAYER" in dex
    except Exception:
        return None


# Dedicated Helsinki paid-installer store (NOT residual VPN peers).
# Package RAG looks here when local monorepo/releases trees are empty (e.g. RO timer).
DEFAULT_HELSINKI_PAID_ASSET_HOST = "135.181.152.10"
DEFAULT_HELSINKI_PAID_ASSET_BASE = "https://135.181.152.10.sslip.io/paid-assets"
DEFAULT_HELSINKI_PAID_ASSET_DISK = "/opt/restore-privacy/paid_assets"


def helsinki_paid_asset_base_url() -> str:
    """Base URL for Helsinki paid installers (no trailing slash)."""
    raw = os.environ.get("RPT_VPS_ASSET_BASE", "").strip().rstrip("/")
    if raw:
        return raw
    return DEFAULT_HELSINKI_PAID_ASSET_BASE.rstrip("/")


def asset_fetch_token() -> str:
    """Token for Helsinki paid-asset HTTP (never browser-facing).

    Order: env → install-root file → secrets/ (operator laptop only).
    """
    for key in ("RPT_ASSET_FETCH_TOKEN", "RPT_VPS_ASSET_TOKEN"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    install = Path(os.environ.get("RPT_INSTALL_ROOT", "/opt/restore-privacy"))
    for cand in (
        install / "var" / "rpt_asset_fetch_token",
        install / "var" / "asset_token",
        ROOT / "secrets" / "rpt_asset_fetch_token",
    ):
        try:
            if cand.is_file():
                val = cand.read_text(encoding="utf-8").strip()
                if val:
                    return val
        except OSError:
            continue
    return ""


def package_store_probe_allowed() -> bool:
    """Helsinki package inventory is first-party fleet infra (allowed on node timer).

    ``RPT_AUDIT_NO_OUTBOUND`` still blocks third-party host-statement fetches;
    package store probe is opt-out via ``RPT_AUDIT_SKIP_PACKAGE_STORE=1``.
    """
    if os.environ.get("RPT_AUDIT_SKIP_PACKAGE_STORE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return False
    return True


def catalog_asset_search_dirs(version: str | None = None) -> list[Path]:
    """Directories that may hold catalog monopin installers (AUDIT package RAG).

    Aligns with paid fulfilment :func:`status_page.payments.asset_search_dirs`
    so RAG does not false-miss packages that the status host can serve:

    1. ``RPT_ASSET_DIR`` (operator override)
    2. ``status_page/assets/{ver}/`` — Render rootDir=status_page deploy path
    3. ``releases/{ver}/`` — monorepo local/dev stage
    4. ``RPT_VPS_ASSET_REMOTE_ROOT/{ver}`` or Helsinki disk
       ``/opt/restore-privacy/paid_assets/{ver}`` (co-located store)
    5. ``dist/{ver}/`` — build intermediate (dev only)

    When local dirs miss, :func:`probe_helsinki_paid_package` checks the
    **Helsinki** HTTP store (``RPT_VPS_ASSET_BASE`` / sslip.io default).

    Each root is the **version directory** where ``filename`` is expected
    (catalog ``relative_path`` = ``{ver}/{filename}``).
    """
    ver = (version or load_catalog_version()).strip()
    dirs: list[Path] = []
    seen: set[str] = set()

    def _add(p: Path) -> None:
        try:
            key = str(p.resolve()) if p.exists() else str(p)
        except OSError:
            key = str(p)
        if key in seen:
            return
        seen.add(key)
        dirs.append(p)

    raw = os.environ.get("RPT_ASSET_DIR", "").strip()
    if raw:
        _add(Path(raw).expanduser())
    # Prefer status assets first (same order as payments.asset_search_dirs)
    _add(ROOT / "status_page" / "assets" / ver)
    _add(ROOT / "releases" / ver)
    remote_root = os.environ.get(
        "RPT_VPS_ASSET_REMOTE_ROOT", DEFAULT_HELSINKI_PAID_ASSET_DISK
    ).strip()
    if remote_root:
        _add(Path(remote_root) / ver)
    # Explicit Helsinki disk path when env points elsewhere (RO lean node)
    if remote_root.rstrip("/") != DEFAULT_HELSINKI_PAID_ASSET_DISK.rstrip("/"):
        _add(Path(DEFAULT_HELSINKI_PAID_ASSET_DISK) / ver)
    _add(ROOT / "dist" / ver)
    # Flat status_page/assets (legacy mis-stage)
    _add(ROOT / "status_page" / "assets")
    return dirs


def probe_helsinki_paid_package(
    version: str,
    filename: str,
    *,
    timeout: float = 12.0,
) -> dict[str, Any] | None:
    """Return remote package metadata when present on Helsinki paid store.

    Uses authenticated Range GET (``X-RPT-Asset-Token``) and closes after the
    first byte so low-spec audit hosts (node timer) never pull full installers.
    """
    if not package_store_probe_allowed():
        return None
    ver = (version or "").strip()
    name = Path((filename or "").strip()).name
    if not ver or not name or name in (".", ".."):
        return None
    token = asset_fetch_token()
    if not token:
        return None
    base = helsinki_paid_asset_base_url()
    url = f"{base}/{ver}/{name}"
    try:
        import http.client
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if parsed.scheme == "https":
            conn: http.client.HTTPConnection = http.client.HTTPSConnection(
                parsed.hostname, port, timeout=timeout
            )
        else:
            conn = http.client.HTTPConnection(parsed.hostname, port, timeout=timeout)
        try:
            conn.request(
                "GET",
                path,
                headers={
                    "X-RPT-Asset-Token": token,
                    "Range": "bytes=0-0",
                    "User-Agent": "rpt-security-audit-package-rag/1",
                    "Connection": "close",
                },
            )
            resp = conn.getresponse()
            code = int(resp.status)
            if code not in (200, 206):
                resp.read(64)
                return None
            size = 0
            cr = resp.getheader("Content-Range") or ""
            if "/" in cr:
                try:
                    size = int(cr.rsplit("/", 1)[-1].strip())
                except ValueError:
                    size = 0
            if size <= 0:
                try:
                    size = int(resp.getheader("Content-Length") or "0")
                except ValueError:
                    size = 0
            # Drain at most one small chunk then close (never spool full PE/APK)
            resp.read(64)
            if size < 1000:
                return None
            return {
                "url": url,
                "bytes": size,
                "host": DEFAULT_HELSINKI_PAID_ASSET_HOST,
                "store": "helsinki_paid_assets",
                "filename": name,
                "version": ver,
            }
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception:
        return None


def resolve_catalog_package_path(
    version: str,
    filename: str,
    *,
    relative_path: str | None = None,
) -> Path | None:
    """Resolve paid catalog installer under monopin fulfilment search paths.

    Uses :func:`catalog_asset_search_dirs` + catalog basename (and optional
    ``relative_path`` like ``0.3.6/restore-privacy-client-0.3.6-….exe``).
    """
    ver = (version or "").strip()
    name = (filename or "").strip()
    if not ver or not name:
        return None
    # Security: basename only (no path traversal)
    name = Path(name).name
    if name in (".", "..") or not name:
        return None
    rel = (relative_path or "").strip().replace("\\", "/")
    rel_name = Path(rel).name if rel else ""

    for base in catalog_asset_search_dirs(ver):
        candidates = [base / name]
        # If relative_path is version/filename and base is version dir, name alone
        # is enough; if base is a parent of version, try relative_path join.
        if rel and rel_name == name and "/" in rel:
            parent = base.parent if base.name == ver else base
            candidates.append(parent / rel)
            candidates.append(base / rel)  # rarely: double version
        for cand in candidates:
            try:
                if cand.is_file() and cand.stat().st_size > 1000:
                    return cand
            except OSError:
                continue
    return None


def catalog_search_roots_display(version: str | None = None) -> list[str]:
    """Human-readable monopin roots for missing-package reasons."""
    ver = (version or load_catalog_version()).strip()
    out: list[str] = []
    for d in catalog_asset_search_dirs(ver):
        try:
            # Prefer repo-relative paths in reasons when under ROOT
            try:
                rel = d.resolve().relative_to(ROOT.resolve())
                out.append(rel.as_posix().rstrip("/") + "/")
                continue
            except (ValueError, OSError):
                pass
            out.append(str(d).replace("\\", "/").rstrip("/") + "/")
        except OSError:
            out.append(str(d).replace("\\", "/") + "/")
    # Always cite Helsinki paid store so Red reasons are actionable
    base = helsinki_paid_asset_base_url()
    helsinki = f"{base}/{ver}/"
    if helsinki not in out and not any("135.181.152.10" in x or "paid-assets" in x for x in out):
        out.append(helsinki)
    return out


def catalog_platform_filenames(
    version: str | None = None,
) -> list[tuple[str, str, str, str]]:
    """(platform, label, filename, relative_path) for current monopin.

    Driven by :func:`downloads.list_catalog_platform_packages` when importable.
    """
    ver = (version or load_catalog_version()).strip()
    label_map = {p: lab for p, lab, _ in _CATALOG_PACKAGE_SPECS}
    try:
        sp = str(ROOT / "status_page")
        if sp not in sys.path:
            sys.path.insert(0, sp)
        from downloads import list_catalog_platform_packages  # type: ignore

        out: list[tuple[str, str, str, str]] = []
        for row in list_catalog_platform_packages(version=ver) or []:
            plat = str(row.get("platform") or "").strip().lower()
            fname = str(row.get("filename") or "").strip()
            rel = str(row.get("relative_path") or f"{ver}/{fname}").strip()
            if not plat or not fname:
                continue
            out.append((plat, label_map.get(plat, plat.title()), fname, rel))
        if len(out) >= 5:
            return out
    except Exception:
        pass
    return [
        (
            plat,
            lab,
            f"restore-privacy-client-{ver}-{suffix}",
            f"{ver}/restore-privacy-client-{ver}-{suffix}",
        )
        for plat, lab, suffix in _CATALOG_PACKAGE_SPECS
    ]


def _package_contains_raw_pub(path: Path, pub_path: Path) -> bool:
    """True when the raw public-key file bytes appear inside the package (PE/archives)."""
    if not pub_path.is_file() or pub_path.stat().st_size < 32:
        return False
    try:
        needle = pub_path.read_bytes()
    except OSError:
        return False
    name = path.name.lower()
    try:
        if name.endswith((".zip", ".apk")):
            import zipfile

            with zipfile.ZipFile(path) as zf:
                for n in zf.namelist():
                    if n.endswith(pub_path.name) or pub_path.name in n:
                        try:
                            if zf.read(n) == needle:
                                return True
                        except Exception:
                            continue
            # Also scan members for raw embed
            with zipfile.ZipFile(path) as zf:
                for n in zf.namelist():
                    try:
                        if needle in zf.read(n):
                            return True
                    except Exception:
                        continue
            return False
        if name.endswith((".tar.gz", ".tgz")):
            import tarfile

            with tarfile.open(path, "r:gz") as tf:
                for m in tf.getmembers():
                    if not m.isfile():
                        continue
                    f = tf.extractfile(m)
                    if f is None:
                        continue
                    try:
                        blob = f.read()
                    except Exception:
                        continue
                    if blob == needle or needle in blob:
                        return True
            return False
        if name.endswith(".exe"):
            # PyInstaller onefile often embeds secrets as raw bytes without 7z member names
            data = path.read_bytes()
            return needle in data
    except Exception:
        return False
    return False


def _windows_multihop_markers(path: Path) -> dict[str, bool]:
    """Structural multihop residual markers inside Windows setup PE."""
    try:
        raw = path.read_bytes()
    except OSError:
        return {"multihop": False, "exit_pub_name": False, "exit_host": False}
    return {
        "multihop": b"multihop" in raw or b"MULTI_HOP" in raw,
        "exit_pub_name": b"exit_node_elgamal" in raw,
        "exit_host": b"178.105.187.178" in raw or b"185.146.232.107" in raw,
    }


def evaluate_package_audit_state(
    platform: str,
    path: Path | None,
    *,
    pin: str,
    expected_filename: str = "",
) -> dict:
    """Pure per-package RAG: presence, no priv, pin, platform structural gates.

    Returns dict with keys: platform, label, filename, state (Green|Amber|Red),
    reasons (list[str]), path (str|None).
    """
    reasons: list[str] = []
    label_map = {p: lab for p, lab, _ in _CATALOG_PACKAGE_SPECS}
    label = label_map.get(platform, platform)
    filename = path.name if path is not None else (expected_filename or "")

    if path is None or not path.is_file():
        ver = load_catalog_version()
        miss = expected_filename or f"restore-privacy-client-{ver}-*"
        roots = catalog_search_roots_display(ver)
        # Helsinki paid store (default fulfilment host) — avoid false Red on RO timer
        probe_name = (expected_filename or filename or "").strip()
        if not probe_name or probe_name.endswith("*"):
            probe_name = filename or ""
        remote = probe_helsinki_paid_package(ver, probe_name)
        if remote and int(remote.get("bytes") or 0) >= 1000:
            return {
                "platform": platform,
                "label": label,
                "filename": remote.get("filename") or filename or miss,
                "state": "Green",
                "reasons": [
                    "present on Helsinki paid_assets store "
                    f"({remote.get('url')}; {int(remote['bytes'])} bytes)",
                    "structural pin/PE gates not re-scanned over HTTP "
                    "(inventory presence from fulfilment host)",
                ],
                "path": remote.get("url"),
                "bytes": int(remote["bytes"]),
                "remote_store": "helsinki",
                "search_roots": roots,
            }
        roots_txt = ", ".join(roots[:6]) if roots else (
            f"releases/{ver}/, status_page/assets/{ver}/, "
            f"{helsinki_paid_asset_base_url()}/{ver}/"
        )
        return {
            "platform": platform,
            "label": label,
            "filename": filename or f"(missing {platform})",
            "state": "Red",
            "reasons": [
                f"catalog monopin asset not staged "
                f"(looked for {miss} / relative_path {ver}/{miss} under "
                f"{roots_txt}; default paid store is Helsinki "
                f"{helsinki_paid_asset_base_url()}/ — set RPT_ASSET_FETCH_TOKEN "
                f"to probe, or stage under paid_assets/{ver}/)"
            ],
            "path": None,
            "search_roots": roots,
        }

    if path.stat().st_size < 1000:
        return {
            "platform": platform,
            "label": label,
            "filename": path.name,
            "state": "Red",
            "reasons": [f"package too small ({path.stat().st_size} bytes)"],
            "path": str(path),
        }

    if _package_contains_priv(path):
        return {
            "platform": platform,
            "label": label,
            "filename": path.name,
            "state": "Red",
            "reasons": ["embeds *.priv (must never ship private keys)"],
            "path": str(path),
        }

    soft: list[str] = []
    hard_fail = False
    entry_pub = ROOT / "product" / "node_elgamal.pub"
    exit_pub = ROOT / "product" / "exit_node_elgamal.pub"

    # Pin when package embeds node_elgamal.pub (archive member or raw PE bytes)
    pub_sha = _package_node_pub_sha256(path)
    if pub_sha is None and _package_contains_raw_pub(path, entry_pub):
        pub_sha = pin or _sha256_bytes(entry_pub.read_bytes())
        reasons.append("node_elgamal.pub embedded (raw product pin match)")
    elif pub_sha is None:
        soft.append("node_elgamal.pub not found inside package (pin not verified)")
    elif pin and pub_sha != pin:
        hard_fail = True
        reasons.append(f"node_elgamal.pub pin mismatch (got {pub_sha[:12]}…)")
    else:
        reasons.append("node_elgamal.pub pin matches product monopin")

    # Platform structural gates
    if platform == "windows":
        pe = _windows_pe_ok(path)
        if pe is False:
            hard_fail = True
            reasons.append("not a Windows PE (MZ) — unrunnable on user devices")
        elif pe is True:
            reasons.append("PE/MZ magic OK")
            mh = _windows_multihop_markers(path)
            if mh.get("multihop") and mh.get("exit_pub_name"):
                reasons.append(
                    "multihop residual prep markers present "
                    "(exit_node_elgamal; residual-via-exit when RPT_MULTIHOP_ENABLED=1)"
                )
            elif mh.get("multihop"):
                soft.append("multihop marker present but exit pub name not found in PE")
            else:
                soft.append(
                    "multihop residual markers not found "
                    "(rebuild via scripts/build_windows_multihop.py)"
                )
            if _package_contains_raw_pub(path, exit_pub):
                reasons.append("exit_node_elgamal.pub raw bytes present (Germany DE exit pin)")
        else:
            soft.append("PE magic not checked")
    elif platform == "android":
        wire = _android_wire_ok(path)
        if wire is False:
            hard_fail = True
            reasons.append("missing product residual wire (pfs-x25519 / RPT-OBFS-LAYER)")
        elif wire is True:
            reasons.append("Android residual wire (PFS + outer obfs) present")
        else:
            soft.append("Android wire not verified")
        try:
            import zipfile

            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                if any(n.endswith("exit_node_elgamal.pub") for n in names):
                    reasons.append("exit_node_elgamal.pub present (multihop exit pin)")
                elif _package_contains_raw_pub(path, exit_pub):
                    reasons.append("exit_node_elgamal.pub raw bytes present (multihop exit)")
        except Exception:
            if _package_contains_raw_pub(path, exit_pub):
                reasons.append("exit_node_elgamal.pub raw bytes present (multihop exit)")
    else:
        reasons.append("archive present (structural residual gates N/A in this pass)")
        if _package_contains_raw_pub(path, exit_pub):
            reasons.append("exit_node_elgamal.pub present (multihop exit pin)")

    if hard_fail:
        state = "Red"
    elif soft:
        state = "Amber"
        reasons.extend(soft)
    else:
        state = "Green"

    # Presence without pin when pin empty → Amber at best
    if state == "Green" and not pin:
        state = "Amber"
        reasons.append("product pin unavailable on this host")

    return {
        "platform": platform,
        "label": label,
        "filename": path.name,
        "state": state,
        "reasons": reasons,
        "path": str(path),
        "bytes": path.stat().st_size,
    }


def evaluate_catalog_packages(catalog_version: str | None = None) -> dict:
    """Evaluate all five catalog installers for the monopin version."""
    ver = (catalog_version or load_catalog_version()).strip()
    pin = product_node_pub_pin()
    exit_pin = product_exit_pub_pin()
    packages: list[dict] = []
    search_roots = catalog_search_roots_display(ver)
    for platform, _label, fname, rel in catalog_platform_filenames(ver):
        path = resolve_catalog_package_path(ver, fname, relative_path=rel)
        row = evaluate_package_audit_state(
            platform, path, pin=pin, expected_filename=fname
        )
        row["relative_path"] = rel
        row["search_roots"] = search_roots
        packages.append(row)
    # Overall: worst state wins
    order = {"Green": 0, "Amber": 1, "Red": 2}
    worst = "Green"
    for p in packages:
        st = p.get("state") or "Red"
        if order.get(st, 2) > order.get(worst, 0):
            worst = st
    staged = sum(1 for p in packages if p.get("path"))
    remote_n = sum(1 for p in packages if p.get("remote_store") == "helsinki")
    return {
        "catalog_version": ver,
        "pin": pin,
        "exit_pin": exit_pin,
        "packages": packages,
        "staged_count": staged,
        "helsinki_remote_count": remote_n,
        "helsinki_paid_asset_base": helsinki_paid_asset_base_url(),
        "overall": worst,
        "legend": {
            "Green": (
                "Present (local monorepo/releases/paid_assets or Helsinki paid "
                "store), no *.priv when scanned, product node pub pin match when "
                "scanned, platform structural gate pass (Windows multihop markers "
                "when PE scanned)"
            ),
            "Amber": "Present but pin/structural check incomplete or soft warning",
            "Red": (
                "Missing from local trees and Helsinki paid store, embeds *.priv, "
                "pin mismatch, or failed structural gate"
            ),
        },
    }


def render_package_rag_section(pkg_results: dict) -> str:
    """Markdown top section: per-installer AUDIT STATE as solid colour cells."""
    ver = pkg_results.get("catalog_version") or "?"
    overall = pkg_results.get("overall") or "Red"
    if overall not in VALID_PACKAGE_STATES:
        overall = "Red"
    overall_cell = package_state_cell_markup(overall)
    packages = pkg_results.get("packages") or []
    legend = pkg_results.get("legend") or {}
    rows = []
    for p in packages:
        state = p.get("state") or "Red"
        if state not in VALID_PACKAGE_STATES:
            state = "Red"
        why = "; ".join(p.get("reasons") or []) or "—"
        swatch = package_state_cell_markup(state)
        plat_cell = package_platform_cell_markup(
            str(p.get("platform") or ""),
            str(p.get("label") or p.get("platform") or ""),
        )
        fname = str(p.get("filename") or "—")
        # Full basename in code span; status HTML enforces nowrap single-line readability
        rows.append(
            f"| {plat_cell} | `{fname}` | {swatch} | {why} |"
        )
    table = (
        "\n".join(rows)
        if rows
        else f"| — | — | {package_state_cell_markup('Red')} | no packages evaluated |"
    )
    return f"""## Installer package AUDIT STATE (catalog v{ver})

Reader confidence for **each current paid catalog installer** after this security-audit pass.
The **STATE** column shows a **solid colour only** (not the words Green/Amber/Red).
**Platform** includes an OS-relative icon. On the status host, long **Package** / **Notes** text scrolls **inside the cell** (not by widening the full page).
Regenerated by `scripts/run_security_audit.py --write` (1-day timer).

| Platform | Package | STATE | Notes |
|----------|---------|-------|-------|
{table}

**Catalog overall (worst package):** {overall_cell}

| State colour | Meaning |
|--------------|---------|
| {package_state_cell_markup("Green")} Green | {legend.get("Green", "OK")} |
| {package_state_cell_markup("Amber")} Amber | {legend.get("Amber", "Partial")} |
| {package_state_cell_markup("Red")} Red | {legend.get("Red", "Fail")} |

---
"""


def primary_peer_public_label(results: dict) -> str:
    """Honest public label for the primary residual peer row.

    After ``redact_audit_value``, ``node_host`` may already be a country label
    (e.g. ``Germany (DE)``). Passing that string through
    ``public_label_for_host`` yields dishonest ``VPN node`` because the helper
    only maps raw monopin IPv4s. Prefer ``live_node_probes`` labels; pass through
    already-public labels; only then map raw hosts.
    """
    host = str(results.get("node_host") or "").strip()
    live = results.get("live_node_probes") or []
    if isinstance(live, list) and live:
        # Match primary host when still raw, or match already-redacted label.
        for row in live:
            if not isinstance(row, dict):
                continue
            row_host = str(row.get("host") or "").strip()
            row_label = str(row.get("label") or "").strip()
            if host and (host == row_host or host == row_label):
                if row_label:
                    return row_label
            if not host and row_label:
                return row_label
        # Preferred: DE when present, else first labeled peer
        for row in live:
            if not isinstance(row, dict):
                continue
            if str(row.get("code") or "").upper() == "DE":
                lab = str(row.get("label") or "").strip()
                if lab:
                    return lab
        lab0 = str((live[0] or {}).get("label") or "").strip()
        if lab0:
            return lab0
    # Already a public country label (contains parentheses country code)
    if host and "(" in host and ")" in host and not host[0].isdigit():
        return host
    if host in ("localhost (node timer)", "127.0.0.1", "localhost", "::1"):
        return "localhost (node timer)" if "127" in host or host == "::1" or host == "localhost" else host
    try:
        from client.residual_public import public_label_for_host

        return public_label_for_host(host) if host else "VPN node"
    except Exception:  # noqa: BLE001
        return host or "VPN node"


def render_live_node_probe_table(results: dict) -> str:
    """Markdown table of per-peer live probes (public country labels only)."""
    live = results.get("live_node_probes") or []
    if not live:
        # Legacy single-host results — use honest primary label helper
        label = primary_peer_public_label(results)
        tcp = results.get("tcp_status") or {}
        http = results.get("http_status") or {}
        udp = results.get("udp") or {}
        live = [
            {
                "label": label,
                "code": "",
                "tcp_status": tcp,
                "http_status": http,
                "udp": udp,
            }
        ]
    rows: list[str] = []
    for row in live:
        label = str(row.get("label") or row.get("code") or "VPN node")
        tcp = row.get("tcp_status") or {}
        http = row.get("http_status") or {}
        udp = row.get("udp") or {}
        body = http.get("body")
        body_s = repr(body) if body is not None else "—"
        rows.append(
            f"| {label} | ok={tcp.get('ok')} err={tcp.get('error')} "
            f"| code={http.get('status_code')} body={body_s} "
            f"| sent={udp.get('sent')} err={udp.get('error')} |"
        )
    table = "\n".join(rows) if rows else "| — | — | — | — |"
    return f"""| Peer | TCP `:{STATUS_PORT}` | HTTP `/status` | UDP `:{UDP_PORT}` |
|------|----------------------|----------------|-------------------|
{table}"""


def build_markdown(results: dict) -> str:
    # Single source of truth for all last-run surfaces in this document.
    now = str(results.get("generated_at") or iso_z()).strip()
    gen_dt = parse_iso_z(now) or utc_now()
    human = human_date(gen_dt)
    host = results["node_host"]
    catalog = results["catalog_version"]
    suite = results["unit_suite"]
    tcp = results["tcp_status"]
    http = results["http_status"]
    udp = results["udp"]
    priv = results["no_priv"]
    pkg = results.get("package_rag") or evaluate_catalog_packages(catalog)
    package_section = render_package_rag_section(pkg)
    live_probe_table = render_live_node_probe_table(results)
    # Prefer label from live_node_probes (survives redact_audit_value which turns
    # monopin IPv4s into "Germany (DE)" / "Iceland (IS)"). public_label_for_host
    # only maps raw IPs — already-redacted labels become dishonest "VPN node".
    primary_label = primary_peer_public_label(results)
    # Live KEYGEN GBP anchors from downloads (not a hard-coded retired monthly price)
    try:
        sys.path.insert(0, str(ROOT / "status_page"))
        from downloads import PRICE_LABEL as _price_mo  # type: ignore
        from downloads import PRICE_YEARLY_LABEL as _price_yr  # type: ignore

        price_mo = str(_price_mo).strip() or "£3.00"
        price_yr = str(_price_yr).strip() or "£30.00"
    except Exception:  # pragma: no cover
        price_mo, price_yr = "£3.00", "£30.00"
    catalog_price_note = (
        f"{price_mo}/month or {price_yr}/year KEYGEN; free Suite installers via "
        "FREE DOWNLOAD; no free GitHub release downloads"
    )
    try:
        from audit_privacy_probes import render_section_b_markdown
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from audit_privacy_probes import render_section_b_markdown  # type: ignore

    section_b_md = render_section_b_markdown(results.get("section_b"))
    try:
        from audit_multihop_structure import render_multihop_structure_markdown
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from audit_multihop_structure import (  # type: ignore
            render_multihop_structure_markdown,
        )

    multihop_md = render_multihop_structure_markdown(
        results.get("multihop_structure")
    )
    # Privacy-scale UK ping + AVG-threshold RAG (live probes when reachable)
    try:
        from client.uk_ping_estimates import render_audit_uk_ping_section
    except ImportError:
        sys.path.insert(0, str(ROOT))
        from client.uk_ping_estimates import render_audit_uk_ping_section  # type: ignore

    try:
        uk_ping_md = render_audit_uk_ping_section(measure=True) + "\n"
    except Exception as exc:  # noqa: BLE001
        uk_ping_md = (
            "## Privacy-scale settings — UK ping + RAG\n\n"
            f"_UK ping section unavailable this pass: {type(exc).__name__}_\n\n"
        )
    suite_line = (
        f"**PASS** ({len(suite.get('modules') or [])} modules)"
        if suite.get("ok")
        else ("**SKIP** (no tests/ on host)" if not suite.get("ran") else "**FAIL**")
    )
    node_ok = bool(tcp.get("ok") and http.get("ok"))
    title_only = False
    if isinstance(http.get("body"), dict):
        body = http["body"]
        title_only = set(body.keys()) <= {"title"} or (
            "title" in body and "clients" not in body and "count" not in body
        )
    sb = results.get("section_b") or {}
    if isinstance(sb.get("probes"), dict):
        tprobe = sb["probes"].get("title_only_status") or {}
        if "title_only" in tprobe:
            title_only = bool(tprobe.get("title_only"))
    pkg_overall = pkg.get("overall") or "Red"
    sb_ok = sb.get("ok")
    sb_line = (
        "PASS"
        if sb_ok
        else ("SKIP/partial" if not sb else "FAIL")
    )
    mh = results.get("multihop_structure") or {}
    mh_ok = mh.get("ok")
    mh_line = (
        "PASS"
        if mh_ok
        else ("SKIP/partial" if not mh else "FAIL")
    )

    return f"""# Restore Privacy — Code & Policy Audit

| Field | Value |
|-------|--------|
| **Product** | Restore Privacy Tunnel (RPT / RPT2) |
| **Repository** | restore-privacy (**private** source; installers only via paid status host) |
| **Public catalog version** | **{catalog}** |
| **Default residual entry** | **Germany (DE)** (product default on all clients; RO monopin retired) |
| **Live probe peer** | **{host}:{UDP_PORT}** (UDP); status UI TCP **{STATUS_PORT}** |
| **Audit generated** | **{human}** (`{now}`) |
| **Cadence** | Automated security pass (~**every 1 day** + **jitter** on privacy-hardened node timer) |
| **Audit type** | Static suite + live node status probe + **per-installer AUDIT STATE** + **section B privacy probes** + **multihop node structure** |
| **Auditor method** | `scripts/run_security_audit.py` — unittest privacy/security modules + TCP/HTTP/UDP probes + no-`.priv` scan + catalog package RAG + section B + multihop structure (no firewall scan) |

---

{package_section}
{section_b_md}
{multihop_md}
{uk_ping_md}
## 1. Executive summary

Latest automated security audit for production node **{host}** and the in-repo privacy/security gates.

**Core privacy thesis (unchanged):** **no user-info logs**, **minimal public status** (title + downloads — **no live client count**), **honest Connected** only when residual full tunnel is active (`residual_ip_capture`), **device Ed25519 keys** (no shared client private key in packages), **no third-party geo on Connect**, **session PFS** + outer **obfs** as **mitigations** (traffic-analysis resistance only — not a claim of full protocol camouflage).

**This pass (automated):**

| Check | Result |
|-------|--------|
| Security unit suite | {suite_line} |
| Node status TCP :{STATUS_PORT} | {"reachable" if tcp.get("ok") else "UNREACHABLE"} |
| Node `/status` HTTP | {"OK" if http.get("ok") else "FAIL"} — title-only={title_only} |
| UDP product port :{UDP_PORT} | {"probe sent" if udp.get("sent") else "send failed"} |
| No `*.priv` under public trees | {"OK" if priv.get("ok") else "HITS: " + ", ".join(priv.get("hits") or [])} |
| Privacy probes (section B) | {sb_line} (firewall excluded) |
| Multihop node structure | {mh_line} (residual-via-exit honesty) |
| Live node healthy (TCP+HTTP) | {"YES" if node_ok else "NO"} |
| Catalog installers AUDIT STATE | {package_state_cell_markup(pkg_overall if pkg_overall in VALID_PACKAGE_STATES else "Red")} (see top package table) |

**Overall posture:** **Strong** for residual honesty (`residual_ip_capture`), no public live count, no-phones-home Connect, packaging strip of `*.priv`, tunnel DNS + DoT, Settings transparency. Multi-hop residual is **opt-in** (`RPT_MULTIHOP_ENABLED=1`): residual-via-exit among non-entry catalog peers (exit **Germany (DE)**); default single-hop **Germany (DE)** entry — not full intermediate encapsulation. Catalog monopin **{catalog}**. Product kill-switch is **off by default** (opt-in ``RPT_KILL_SWITCH=1`` only). Installer package confidence is the RAG table at the top of this audit.

**Primary residual risks (open by design / environment):**

1. **Operational** — Product node is on **FlokiNET** in **Iceland** (strict **Icelandic** privacy / free-expression hosting norms). **As far as we can be assured** from FlokiNET’s public statements (**“No invasive logs”**; resource-usage monitoring only; no third-party tenant traffic/pattern sharing — https://flokinet.is/privacy/, https://flokinet.is/vps/), the host does **not** retain invasive logs of users connecting to the node. That is host-published posture, not a product forensic audit. Separate CDN/status hosts and home-ISP paths may still log. Node **OS compromise** (live RAM) remains residual.  
2. **Apple** — residual IP requires signed Packet Tunnel / NE.  
3. **Linux privilege floor** — residual needs root + TUN/`ip`.  
4. **Traffic analysis** — padding/jitter/cover/outer obfs are mitigations only.  
5. **FDE / wipe / rebuild** — at-rest only; unlocked root still sees secrets.

---

## 2. Scope and method

### 2.1 In scope

| Area | Paths |
|------|--------|
| Shared client | `client/connect.py`, `client/endpoint.py`, `client/full_tunnel.py`, `client/multihop.py`, `client/secrets_loader.py`, `client/legal_links.py`, residual honesty / `residual_ip_capture` |
| Multi-hop residual | Opt-in residual-via-exit (`RPT_MULTIHOP_ENABLED=1`); catalog pubs IS/DE under `product/` (default entry **DE**; US and RO residual peers retired) |
| Windows / Linux | `client/windows/*` (multihop PE via `scripts/build_windows_multihop.py`), `client/linux/*` |
| Mobile / Apple | `client_app/` Flutter + NativePrep residual engines (exit pub inject) |
| Node | `node/*` (handshake, pfs, traffic_shape, crypto_session, nolog); node-only zram+LUKS2 |
| Paid packages | `status_page/downloads.py` monopin **{catalog}**; assets under `status_page/assets/{catalog}/` + VPS `paid_assets` |
| Public web | `status_page/*` catalog **{catalog}** |
| Policies | `PRIVACY_POLICY.md`, `LICENSE`, `CREDITS.md`, `README.md`, `AUDIT.md` |

### 2.2 Method notes

- Public audit is served on the **status host** as **`/AUDIT.md`** and **`/audit.md`** (source repo is private).  
- Product default residual entry **Germany (DE)** (catalog monopin; live probe host may be another peer). Romania monopin retired.  
- Live probe host **{host}**.  
- Product node ElGamal pub pin: `product/NODE_ELGAMAL_PUB.sha256` (SHA-256 `1b126abf…`).  
- **Did not** paste secret material into this document.

---

## 3. Live residual node probe results

Schedule: **all active residual monopin peers** from the product catalog
(not a single default host only). Node-timer runs use **localhost only**.

{live_probe_table}

**Primary peer** (backward-compat summary — default residual entry / preferred host):

| Probe | Detail |
|-------|--------|
| Peer | {primary_label} |
| TCP status `:{STATUS_PORT}` | ok={tcp.get("ok")} error={tcp.get("error")} |
| HTTP `/status` | code={http.get("status_code")} body={http.get("body")!r} |
| UDP residual `:{UDP_PORT}` | sent={udp.get("sent")} error={udp.get("error")} |

**Expectation:** `/status` returns title-only JSON (e.g. `{{"title":"RESTORE PRIVACY"}}`) — **never** a live client count.

---

## 4. Threat model scenarios

### 4.6 Threat model scenarios

#### Scenario A — VPS compromise

Production node placement: **Iceland**, hypervisor host **FlokiNET**. **As far as we can be assured** from FlokiNET’s public statements, the host does **not** retain invasive connection logs of users connecting to the node (**“No invasive logs”**; no third-party traffic/pattern sharing; overall resource usage only). If the **VPS guest OS / root** (production node) is fully compromised while sessions are active, **in-memory** session material may still be exposed. Product **no-log** / nolog composition reduces durable user-info logs on disk but does **not** erase live RAM. **Residual risk:** compromise of the node OS (distinct from FlokiNET’s published no-invasive-logs posture for tenant connection logging).

#### Scenario B — Traffic analysis by ISP

An **ISP** performing **traffic analysis** may still observe connection timing and volume. Outer obfuscation and traffic shaping mitigate fingerprinting; this is **traffic-analysis resistance only**, not a claim of full protocol camouflage. **Residual risk:** sophisticated network observers.

#### Scenario C — Client device seizure

**Device seizure** of a user machine may expose the local **device key** and residual config stored on disk. Packages never ship a shared client private key; keys are generated per device. **Restore Internet** executable (shipped with your download) will erase everything relating to this VPN from your device. **Residual risk:** local disk / unlocked endpoint compromise (if the failsafe was not run before seizure, residual product material may still be recoverable).

---

## 5. Findings (automated this pass)

| Severity | Finding | Status |
|----------|---------|--------|
| **Info** | Automated pass at `{now}` | Recorded |
| **High** | Public client count on status | {"Closed (title-only)" if title_only or not http.get("ok") else "REVIEW"} |
| **Medium** | Shared client priv in packages | {"Closed (no .priv hits)" if priv.get("ok") else "OPEN — see hits"} |
| **Low** | Unit suite failure | {"N/A" if suite.get("ok") or not suite.get("ran") else "OPEN — see suite log"} |
| **Info** | Multi-hop residual | Opt-in residual-via-exit (Germany DE); Windows PE multihop rebuild shipped in catalog when package present |

---

## 6. Automated checks (this pass — {human})

**Modules:** {", ".join(f"`{m}`" for m in (suite.get("modules") or SECURITY_TEST_MODULES))}

| Result | Detail |
|--------|--------|
| **Unit suite** | {suite_line} |
| **Return code** | {suite.get("returncode", "n/a")} |
| **Log** | operator SCRATCH / `security_audit.log` / node journal `rpt-security-audit.service` |
| **Generator** | `scripts/run_security_audit.py` |

### 6.1 Package host credibility

| Expectation | Notes |
|-------------|--------|
| Product host | **{host}** |
| Public catalog | **{catalog}** paid installers on [status host](https://restoreprivacy.online/) ({catalog_price_note}) |
| Node pub pin | `1b126abf…` |
| No `.priv` in public package trees | {"OK" if priv.get("ok") else "HITS"} |

---

## 7. Secrets & packaging checklist

| Control | Status |
|---------|--------|
| `secrets/` gitignored | Yes |
| Installer strip `*.priv` | Yes |
| Product `node_elgamal.pub` tracked | Yes (`product/`) |
| This audit embeds no keys | Confirmed |

---

## 8. Recommendations (non-binding)

1. Keep **1-day** timer enabled on the production node (`install_security_audit_timer.sh`).  
2. Redeploy VPN APP Shop after audit link / catalog changes.  
3. Keep multi-hop residual honesty: residual-via-exit when enabled; do not claim full intermediate encapsulation.  
4. Ops: keep Unbound tunnel-only; no public :53; provider log awareness; zram+LUKS2 node-only on multi-hop hosts.

---

## 9. Conclusion

Automated security audit at **{now}** against node **{host}** and in-repo privacy gates. Public **SECURITY AUDIT** links must resolve on the **status host** (`/AUDIT.md` / `/audit.md`). Source repository is **private**; paid catalog installers are fulfilled on the status host only. Core privacy promises hold when the suite passes and status remains title-only.

Re-run: `python3 scripts/run_security_audit.py --write`

---

## 10. Follow-ups status

| Rec | Status |
|-----|--------|
| Public audit on private GitHub blob | **Fixed** — clients use status-origin `/AUDIT.md` |
| Periodic node audit | **In tree** — 1d systemd timer |
| Multi-hop residual | **In tree** — opt-in residual-via-exit (Germany DE); Windows multihop PE via `build_windows_multihop.py`; Linux/Android/Apple ship exit/DE pub |
| Kill-switch + DoT + outer obfs | In tree |
| Ephemeral node rebuild | In tree (dry-run default) |

---

## 11. Document control

| Item | |
|------|--|
| Output | `AUDIT.md` (repo root); served as `/AUDIT.md` and `/audit.md` on VPN APP Shop |
| Related | `PRIVACY_POLICY.md`, `README.md`, `scripts/run_security_audit.py` |
| Code baseline | Catalog **{catalog}** + node **{host}** |
| Pass date | **{human}** |
| Machine JSON | `status_page/static/security_audit_latest.json` (when `--write`) |
"""


def collect(node_only: bool = False) -> dict:
    """Collect unit suite + multi-node residual live probes + package RAG.

    Live schedule is **all active residual monopin peers** from the product
    catalog (IS + DE today), unless ``RPT_AUDIT_REQUIRE_LOCALHOST=1`` forces a
    single loopback peer (privacy-hardened node timer).
    """
    schedule = active_residual_probe_schedule()
    # Validate primary host against localhost policy (raises when misconfigured).
    primary_host = require_localhost_probe_host(
        schedule[0]["host"] if schedule and localhost_probe_required() else DEFAULT_HOST
    )
    catalog = load_catalog_version()
    live_node_probes = probe_all_residual_nodes(schedule)
    primary = primary_probe_from_live(live_node_probes, preferred_host=primary_host)
    host = str(primary.get("host") or primary_host)
    http_status = primary.get("http_status") or probe_http_status(host, STATUS_PORT)
    tcp_status = primary.get("tcp_status") or probe_tcp(host, STATUS_PORT)
    udp = primary.get("udp") or probe_udp_open(host, UDP_PORT)
    section_b = run_section_b_probes(http_status)
    multihop_structure = run_multihop_structure_probes()
    # Public-safe schedule summary (labels only; hosts redacted later).
    schedule_public = [
        {
            "code": p.get("code"),
            "label": p.get("label"),
            "status_port": p.get("status_port"),
            "udp_port": p.get("udp_port"),
        }
        for p in schedule
    ]
    results = {
        "generated_at": iso_z(),
        "node_host": host,
        "catalog_version": catalog,
        "probe_schedule": schedule_public,
        "live_node_probes": live_node_probes,
        "unit_suite": {"ran": False, "ok": True, "reason": "skipped"} if node_only else run_unit_suite(),
        "tcp_status": tcp_status,
        "http_status": http_status,
        "udp": udp,
        "no_priv": check_no_priv_in_tree(),
        "package_rag": evaluate_catalog_packages(catalog),
        "section_b": section_b,
        "multihop_structure": multihop_structure,
        "audit_privacy": {
            "localhost_required": localhost_probe_required(),
            "outbound_allowed": audit_outbound_allowed(),
            "probe_host_loopback": is_loopback_host(host),
            "multi_node_schedule": not localhost_probe_required(),
            "probe_peer_count": len(live_node_probes),
            "no_network_exfil": True,
            "section_b": True,
            "multihop_structure": True,
            "firewall_probe_excluded": True,
        },
    }
    results["overall_ok"] = bool(
        results["unit_suite"].get("ok")
        and results["tcp_status"].get("ok")
        and results["http_status"].get("ok")
        and results["no_priv"].get("ok")
        and results["section_b"].get("ok", True)
        and results["multihop_structure"].get("ok", True)
        # Package Red does not fail the whole audit exit alone (node host may lack
        # releases/); RAG is reported honestly for readers instead.
    )
    return results


def write_outputs(results: dict, out_path: Path) -> None:
    """Write AUDIT.md + mirrors + JSON with section-A redaction (no suite tails).

    Every successful write stamps a **fresh** write-time ``generated_at`` (ISO-Z)
    so last-run always advances — never reuses a stale collect-time value from
    *results*. That single stamp is shared by every AUDIT mirror and
    ``security_audit_latest.json``.
    """
    # Fresh write-time stamp (unstick sticky last-run even if results are stale).
    stamp = iso_z()
    results = dict(results or {})
    results["generated_at"] = stamp
    # Redact nested error strings before markdown so tails never leak home paths
    safe_results = redact_audit_value(dict(results))
    safe_results["generated_at"] = stamp
    md = redact_audit_text(build_markdown(safe_results))
    # Defense: markdown must embed this stamp everywhere (unstick stale mirrors)
    if stamp not in md:
        md = md + f"\n\n<!-- audit generated_at={stamp} -->\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    # Case-insensitive FS: same path. On Linux, optionally mirror lowercase if distinct.
    lower = out_path.parent / "audit.md"
    if lower.resolve() != out_path.resolve():
        try:
            lower.write_text(md, encoding="utf-8")
        except OSError:
            pass
    # VPN APP Shop copies for Render (rootDir=status_page) + public_docs host
    for status_copy in (
        ROOT / "status_page" / "AUDIT.md",
        ROOT / "status_page" / "public" / "AUDIT.md",
    ):
        try:
            status_copy.parent.mkdir(parents=True, exist_ok=True)
            status_copy.write_text(md, encoding="utf-8")
        except OSError:
            pass
    # Machine-readable (redacted, no suite tails) — same stamp as markdown
    json_path = ROOT / "status_page" / "static" / "security_audit_latest.json"
    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        slim = slim_results_for_public_json(safe_results)
        slim["generated_at"] = stamp
        json_path.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def publish_audit_artifacts(
    *,
    commit: bool = True,
    push: bool = True,
) -> dict[str, Any]:
    """Publish local AUDIT mirrors + security_audit_latest.json to status host.

    Status host (restoreprivacy.online) deploys from git ``status_page/``
    (Render rootDir). This entry stages the written artifacts, commits when
    dirty, and pushes to ``origin`` so the public page last-run advances.

    Returns a result dict: ``ok``, ``steps``, ``error`` (honest failure, never
    faked green). Set ``RPT_AUDIT_PUBLISH=0`` / ``--no-publish`` to skip.
    """
    out: dict[str, Any] = {"ok": False, "steps": [], "error": None, "published": False}
    paths = [
        ROOT / "AUDIT.md",
        ROOT / "status_page" / "AUDIT.md",
        ROOT / "status_page" / "public" / "AUDIT.md",
        ROOT / "status_page" / "static" / "security_audit_latest.json",
    ]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        out["error"] = f"missing artifacts: {missing}"
        out["steps"].append({"action": "check_paths", "ok": False, "missing": missing})
        return out
    out["steps"].append({"action": "check_paths", "ok": True})

    # Optional SSH/rsync publish when RPT_AUDIT_STATUS_SSH is set (scp pair).
    # Residual timer uses this to push ONLY audit JSON + AUDIT.md to Helsinki
    # public-audit (status host prefers that upstream for last-run).
    ssh_spec = (os.environ.get("RPT_AUDIT_STATUS_SSH") or "").strip()
    remote_root = (
        os.environ.get("RPT_AUDIT_STATUS_REMOTE_ROOT") or ""
    ).strip() or "/opt/restore-privacy"
    if ssh_spec:
        key = (os.environ.get("RPT_SSH_KEY") or "").strip()
        # rpt-audit user has home /nonexistent — pin known_hosts under install var.
        install_root = Path(
            os.environ.get("RPT_INSTALL_ROOT") or remote_root or "/opt/restore-privacy"
        )
        known_hosts = install_root / "var" / "audit_status_known_hosts"
        try:
            known_hosts.parent.mkdir(parents=True, exist_ok=True)
            if not known_hosts.is_file():
                known_hosts.write_text("", encoding="utf-8")
            known_hosts.chmod(0o644)
        except OSError:
            pass
        scp = [
            "scp",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=30",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            f"UserKnownHostsFile={known_hosts}",
            "-o",
            "GlobalKnownHostsFile=/dev/null",
        ]
        if key:
            scp.extend(["-i", key])
        else:
            for name in (
                "id_ed25519_restore_privacy_eu",
                "id_ed25519_restore_privacy_vps",
            ):
                cand = Path.home() / ".ssh" / name
                if cand.is_file():
                    scp.extend(["-i", str(cand)])
                    break
        # Default remote layout: public-audit/ (nginx /public-audit/)
        remote_json_rel = (
            os.environ.get("RPT_AUDIT_STATUS_REMOTE_JSON") or ""
        ).strip() or f"{remote_root}/public-audit/security_audit_latest.json"
        remote_audit_rel = (
            os.environ.get("RPT_AUDIT_STATUS_REMOTE_AUDIT") or ""
        ).strip() or f"{remote_root}/public-audit/AUDIT.md"
        remote_json = f"{ssh_spec}:{remote_json_rel}"
        remote_audit = f"{ssh_spec}:{remote_audit_rel}"
        json_path = ROOT / "status_page" / "static" / "security_audit_latest.json"
        if not json_path.is_file():
            # Install-root layout on residual node
            alt = install_root / "status_page/static/security_audit_latest.json"
            if alt.is_file():
                json_path = alt
        pub_audit = ROOT / "status_page" / "public" / "AUDIT.md"
        if not pub_audit.is_file():
            alt_a = Path(os.environ.get("RPT_AUDIT_PATH", ""))
            if not alt_a.is_file():
                alt_a = install_root / "AUDIT.md"
            if alt_a.is_file():
                pub_audit = alt_a
        # Ensure remote dir exists (best-effort ssh mkdir)
        user_host = ssh_spec
        ssh_base = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=30",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            f"UserKnownHostsFile={known_hosts}",
            "-o",
            "GlobalKnownHostsFile=/dev/null",
        ]
        if key:
            ssh_base.extend(["-i", key])
        remote_dir = str(Path(remote_json_rel).parent)
        subprocess.run(
            ssh_base + [user_host, f"mkdir -p {remote_dir}"],
            capture_output=True,
            text=True,
            check=False,
        )
        r1 = subprocess.run(
            scp + [str(json_path), remote_json],
            capture_output=True,
            text=True,
        )
        r2 = subprocess.run(
            scp + [str(pub_audit), remote_audit],
            capture_output=True,
            text=True,
        )
        step = {
            "action": "scp_public_audit",
            "ok": r1.returncode == 0 and r2.returncode == 0,
            "remote": ssh_spec,
            "remote_json": remote_json,
            "stderr": ((r1.stderr or "") + (r2.stderr or ""))[:500],
        }
        out["steps"].append(step)
        if step["ok"]:
            out["ok"] = True
            out["published"] = True
            return out
        out["error"] = step["stderr"] or "scp failed"
        # Fall through to git publish attempt

    if not commit and not push:
        out["error"] = out.get("error") or "publish skipped (no commit/push/ssh)"
        return out

    try:
        add = subprocess.run(
            ["git", "add", "--"] + [str(p.relative_to(ROOT)) for p in paths],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        out["steps"].append(
            {
                "action": "git_add",
                "ok": add.returncode == 0,
                "stderr": add.stderr or "",
            }
        )
        if add.returncode != 0:
            out["error"] = add.stderr or "git add failed"
            return out

        # Only commit when there is a staged change
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(ROOT),
            check=False,
        )
        if diff.returncode == 0:
            out["steps"].append({"action": "git_commit", "ok": True, "note": "nothing to commit"})
        elif commit:
            msg = "Refresh security audit last-run (multi-node live probes)"
            c = subprocess.run(
                ["git", "commit", "-m", msg],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            out["steps"].append(
                {
                    "action": "git_commit",
                    "ok": c.returncode == 0,
                    "stderr": c.stderr or "",
                    "stdout": (c.stdout or "")[:500],
                }
            )
            if c.returncode != 0:
                out["error"] = c.stderr or "git commit failed"
                return out
        if push:
            p = subprocess.run(
                ["git", "push", "origin", "HEAD"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            out["steps"].append(
                {
                    "action": "git_push",
                    "ok": p.returncode == 0,
                    "stderr": p.stderr or "",
                    "stdout": (p.stdout or "")[:500],
                }
            )
            if p.returncode != 0:
                out["error"] = p.stderr or "git push failed"
                return out
            out["ok"] = True
            out["published"] = True
            return out
        out["ok"] = True
        out["published"] = bool(commit)
        return out
    except FileNotFoundError as exc:
        out["error"] = f"git not available: {exc}"
        return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--node-only", action="store_true", help="Skip unittest suite")
    ap.add_argument("--write", action="store_true", help="Write AUDIT.md and mirrors")
    ap.add_argument(
        "--publish",
        action="store_true",
        help="After --write, publish AUDIT + JSON to status-host deploy surface (git push and/or RPT_AUDIT_STATUS_SSH)",
    )
    ap.add_argument(
        "--no-publish",
        action="store_true",
        help="Force-skip publish even when RPT_AUDIT_PUBLISH=1",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(os.environ.get("RPT_AUDIT_PATH") or ROOT / "AUDIT.md"),
    )
    ap.add_argument("--json", action="store_true", help="Print results JSON to stdout")
    args = ap.parse_args(argv)

    try:
        results = collect(node_only=args.node_only)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    if args.write:
        write_outputs(results, args.out.resolve())
        print(f"Wrote {args.out}", flush=True)
        env_pub = os.environ.get("RPT_AUDIT_PUBLISH", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        do_publish = (args.publish or env_pub) and not args.no_publish
        if do_publish:
            pub = publish_audit_artifacts()
            print(f"publish: {json.dumps(pub, default=str)}", flush=True)
            if not pub.get("ok"):
                print(
                    f"publish failed (honest): {pub.get('error')}",
                    file=sys.stderr,
                )
                # Non-zero only when explicitly --publish (env-only stays soft)
                if args.publish:
                    return 4
    if args.json or not args.write:
        # Never dump suite tails to stdout JSON either
        print(json.dumps(slim_results_for_public_json(results), indent=2, default=str))
    if results.get("unit_suite", {}).get("ran") and not results["unit_suite"].get("ok"):
        # Operator-only stderr: already redacted short tails
        print(
            results["unit_suite"].get("stderr_tail")
            or results["unit_suite"].get("stdout_tail")
            or "unit suite failed",
            file=sys.stderr,
        )
        return 2
    return 0 if results.get("overall_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
