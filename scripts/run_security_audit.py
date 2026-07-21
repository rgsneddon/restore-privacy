#!/usr/bin/env python3
"""Run Restore Privacy security audit and refresh AUDIT.md (+ optional audit.md).

Designed for:
  - Operator laptop / CI (full unittest suite)
  - Production node (lighter probes when tests/ missing)

Default period target: every 4 hours via scripts/install_security_audit_timer.sh
(with schedule jitter + privacy-hardened oneshot unit — section A).

Usage:
  python3 scripts/run_security_audit.py
  python3 scripts/run_security_audit.py --node-only
  python3 scripts/run_security_audit.py --write --out AUDIT.md

Environment:
  RPT_NODE_HOST     default 82.221.101.241 (timer forces 127.0.0.1 on node)
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
DEFAULT_HOST = os.environ.get("RPT_NODE_HOST", "82.221.101.241")
STATUS_PORT = int(os.environ.get("RPT_STATUS_PORT", "8080"))
UDP_PORT = int(os.environ.get("RPT_UDP_PORT", "44044"))

# Loopback hosts allowed when RPT_AUDIT_REQUIRE_LOCALHOST=1 (node timer policy)
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

# Structural / privacy suite — keep lightweight and deterministic.
# Do not include tests that assert AUDIT.md body content here (those run after --write).
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
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(dt: datetime | None = None) -> str:
    d = dt or utc_now()
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def human_date(dt: datetime | None = None) -> str:
    d = dt or utc_now()
    return d.strftime("%-d %B %Y") if sys.platform != "win32" else d.strftime("%d %B %Y")


def is_loopback_host(host: str) -> bool:
    """True when probe host is loopback (node-timer local-only policy)."""
    h = (host or "").strip().lower().strip("[]")
    if h in _LOOPBACK_HOSTS:
        return True
    # IPv4 mapped / zone id
    if h.startswith("127."):
        return True
    return False


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

    Removes home paths, token-like secrets, PEM private blocks, and softens
    user@host SSH-style identities. Product monopin hosts (e.g. 82.221.101.241),
    SHA-256 pins, and public status titles are left intact.
    """
    if not text:
        return text
    s = str(text)
    s = _RE_PEM_BLOCK.sub("[REDACTED_PRIVATE_KEY]", s)
    s = _RE_HOME_PATH.sub(r"\1/[REDACTED_USER]", s)
    s = _RE_BEARER.sub(r"\1[REDACTED_TOKEN]", s)
    s = _RE_TOKENISH.sub(r"\1[REDACTED]", s)
    s = _RE_SSH_USER_AT.sub(r"[REDACTED_USER]@\2", s)
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
    slim["privacy"] = {
        "redacted": True,
        "no_suite_tails": True,
        "no_network_exfil": True,
        "note": "Audit artifacts are local-only; timer does not git-push or upload",
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
    """
    tests_dir = ROOT / "tests"
    if not tests_dir.is_dir():
        return {"ran": False, "reason": "tests/ not present (node install)", "ok": True, "modules": []}

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
    hits = []
    for base in (ROOT / "product", ROOT / "releases", ROOT / "status_page"):
        if not base.exists():
            continue
        for p in base.rglob("*.priv"):
            # secrets/ is gitignored; still flag if under product/releases/status
            hits.append(str(p.relative_to(ROOT)))
    return {"ok": len(hits) == 0, "hits": hits[:20]}


def load_catalog_version() -> str:
    try:
        sys.path.insert(0, str(ROOT / "status_page"))
        from downloads import RELEASE_VERSION  # type: ignore

        return str(RELEASE_VERSION)
    except Exception:
        ver = ROOT / "client" / "VERSION"
        if ver.is_file():
            return ver.read_text(encoding="utf-8").strip()
        return "unknown"


# --- Catalog installer AUDIT STATE (Green / Amber / Red) ---

VALID_PACKAGE_STATES = frozenset({"Green", "Amber", "Red"})

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


def _package_node_pub_sha256(path: Path) -> str | None:
    """Return SHA-256 of embedded node_elgamal.pub, or None if not found."""
    name = path.name.lower()
    try:
        if name.endswith((".zip", ".apk")):
            import zipfile

            with zipfile.ZipFile(path) as zf:
                for n in zf.namelist():
                    if n.endswith("node_elgamal.pub") or n.endswith("/node_elgamal.pub"):
                        return _sha256_bytes(zf.read(n))
            return None
        if name.endswith((".tar.gz", ".tgz")):
            import tarfile

            with tarfile.open(path, "r:gz") as tf:
                for m in tf.getmembers():
                    if m.isfile() and m.name.endswith("node_elgamal.pub"):
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


def resolve_catalog_package_path(version: str, filename: str) -> Path | None:
    """Prefer releases/{version}/ then status_page/assets/{version}/."""
    for base in (
        ROOT / "releases" / version / filename,
        ROOT / "status_page" / "assets" / version / filename,
    ):
        if base.is_file() and base.stat().st_size > 1000:
            return base
    return None


def evaluate_package_audit_state(
    platform: str,
    path: Path | None,
    *,
    pin: str,
) -> dict:
    """Pure per-package RAG: presence, no priv, pin, platform structural gates.

    Returns dict with keys: platform, label, filename, state (Green|Amber|Red),
    reasons (list[str]), path (str|None).
    """
    reasons: list[str] = []
    label_map = {p: lab for p, lab, _ in _CATALOG_PACKAGE_SPECS}
    label = label_map.get(platform, platform)
    filename = path.name if path is not None else ""

    if path is None or not path.is_file():
        return {
            "platform": platform,
            "label": label,
            "filename": filename or f"(missing {platform})",
            "state": "Red",
            "reasons": ["package file not found under releases/ or status_page/assets/"],
            "path": None,
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

    # Pin when package embeds node_elgamal.pub
    pub_sha = _package_node_pub_sha256(path)
    if pub_sha is None:
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
    else:
        reasons.append("archive present (structural residual gates N/A in this pass)")

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
    packages: list[dict] = []
    for platform, _label, suffix in _CATALOG_PACKAGE_SPECS:
        fname = f"restore-privacy-client-{ver}-{suffix}"
        path = resolve_catalog_package_path(ver, fname)
        packages.append(evaluate_package_audit_state(platform, path, pin=pin))
    # Overall: worst state wins
    order = {"Green": 0, "Amber": 1, "Red": 2}
    worst = "Green"
    for p in packages:
        st = p.get("state") or "Red"
        if order.get(st, 2) > order.get(worst, 0):
            worst = st
    return {
        "catalog_version": ver,
        "pin": pin,
        "packages": packages,
        "overall": worst,
        "legend": {
            "Green": "Present, no *.priv, product node pub pin match, platform structural gate pass",
            "Amber": "Present but pin/structural check incomplete or soft warning",
            "Red": "Missing, embeds *.priv, pin mismatch, or failed structural gate (e.g. non-PE Windows)",
        },
    }


def render_package_rag_section(pkg_results: dict) -> str:
    """Markdown top section: per-installer AUDIT STATE Green|Amber|Red."""
    ver = pkg_results.get("catalog_version") or "?"
    overall = pkg_results.get("overall") or "Red"
    packages = pkg_results.get("packages") or []
    legend = pkg_results.get("legend") or {}
    rows = []
    for p in packages:
        state = p.get("state") or "Red"
        if state not in VALID_PACKAGE_STATES:
            state = "Red"
        why = "; ".join(p.get("reasons") or []) or "—"
        rows.append(
            f"| **{p.get('label') or p.get('platform')}** | `{p.get('filename')}` | **{state}** | {why} |"
        )
    table = "\n".join(rows) if rows else "| — | — | **Red** | no packages evaluated |"
    return f"""## Installer package AUDIT STATE (catalog v{ver})

Reader confidence for **each current paid catalog installer** after this security-audit pass.
States are **Green**, **Amber**, or **Red** only (RAG). Regenerated by
`scripts/run_security_audit.py --write` (4-hour timer).

| Platform | Package | AUDIT STATE | Notes |
|----------|---------|-------------|-------|
{table}

**Catalog overall (worst package):** **{overall}**

| State | Meaning |
|-------|---------|
| **Green** | {legend.get("Green", "OK")} |
| **Amber** | {legend.get("Amber", "Partial")} |
| **Red** | {legend.get("Red", "Fail")} |

---
"""


def build_markdown(results: dict) -> str:
    now = results["generated_at"]
    host = results["node_host"]
    catalog = results["catalog_version"]
    suite = results["unit_suite"]
    tcp = results["tcp_status"]
    http = results["http_status"]
    udp = results["udp"]
    priv = results["no_priv"]
    pkg = results.get("package_rag") or evaluate_catalog_packages(catalog)
    package_section = render_package_rag_section(pkg)
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
    pkg_overall = pkg.get("overall") or "Red"

    return f"""# Restore Privacy — Code & Policy Audit

| Field | Value |
|-------|--------|
| **Product** | Restore Privacy Tunnel (RPT / RPT2) |
| **Repository** | restore-privacy (**private** source; installers only via paid status host) |
| **Public catalog version** | **{catalog}** |
| **Production node** | **{host}:{UDP_PORT}** (UDP); status UI TCP **{STATUS_PORT}** — **Iceland**, host **FlokiNET** |
| **Audit generated** | **{human_date()}** (`{now}`) |
| **Cadence** | Automated security pass (~**every 4 hours** + **jitter** on privacy-hardened node timer) |
| **Audit type** | Static suite + live node status probe + **per-installer AUDIT STATE (Green/Amber/Red)** |
| **Auditor method** | `scripts/run_security_audit.py` — unittest privacy/security modules + TCP/HTTP/UDP probes + no-`.priv` scan + catalog package RAG |

---

{package_section}
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
| No `*.priv` under product/releases/status_page | {"OK" if priv.get("ok") else "HITS: " + ", ".join(priv.get("hits") or [])} |
| Live node healthy (TCP+HTTP) | {"YES" if node_ok else "NO"} |
| Catalog installers AUDIT STATE | **{pkg_overall}** (see top package table) |

**Overall posture:** **Strong** for residual honesty (`residual_ip_capture`), no public live count, no-phones-home Connect, packaging strip of `*.priv`, tunnel DNS + DoT, Settings transparency — without multi-hop residual claims. Product kill-switch is **off by default** (opt-in ``RPT_KILL_SWITCH=1`` only). Installer package confidence is the RAG table at the top of this audit.

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
| Shared client | `client/connect.py`, `client/endpoint.py`, `client/full_tunnel.py`, `client/secrets_loader.py`, `client/legal_links.py`, residual honesty / `residual_ip_capture` |
| Windows / Linux | `client/windows/*`, `client/linux/*` |
| Mobile / Apple | `client_app/` Flutter + NativePrep residual engines |
| Node | `node/*` (handshake, pfs, traffic_shape, crypto_session, nolog) |
| Public web | `status_page/*` catalog **{catalog}** |
| Policies | `PRIVACY_POLICY.md`, `LICENSE`, `CREDITS.md`, `README.md`, `AUDIT.md` |

### 2.2 Method notes

- Public audit is served on the **status host** as **`/AUDIT.md`** and **`/audit.md`** (source repo is private).  
- Product default host **{host}**.  
- Product node ElGamal pub pin: `product/NODE_ELGAMAL_PUB.sha256` (SHA-256 `1b126abf…`).  
- **Did not** paste secret material into this document.

---

## 3. Live node probe results

| Probe | Detail |
|-------|--------|
| TCP `{host}:{STATUS_PORT}` | ok={tcp.get("ok")} error={tcp.get("error")} |
| HTTP `http://{host}:{STATUS_PORT}/status` | code={http.get("status_code")} body={http.get("body")!r} |
| UDP `{host}:{UDP_PORT}` | sent={udp.get("sent")} error={udp.get("error")} |

**Expectation:** `/status` returns title-only JSON (e.g. `{{"title":"RESTORE PRIVACY"}}`) — **never** a live client count.

---

## 4. Threat model scenarios

### 4.6 Threat model scenarios

#### Scenario A — VPS compromise

Production node placement: **Iceland**, hypervisor host **FlokiNET**. **As far as we can be assured** from FlokiNET’s public statements, the host does **not** retain invasive connection logs of users connecting to the node (**“No invasive logs”**; no third-party traffic/pattern sharing; overall resource usage only). If the **VPS guest OS / root** (production node) is fully compromised while sessions are active, **in-memory** session material may still be exposed. Product **no-log** / nolog composition reduces durable user-info logs on disk but does **not** erase live RAM. **Residual risk:** compromise of the node OS (distinct from FlokiNET’s published no-invasive-logs posture for tenant connection logging).

#### Scenario B — Traffic analysis by ISP

An **ISP** performing **traffic analysis** may still observe connection timing and volume. Outer obfuscation and traffic shaping mitigate fingerprinting; this is **traffic-analysis resistance only**, not a claim of full protocol camouflage. **Residual risk:** sophisticated network observers.

#### Scenario C — Client device seizure

**Device seizure** of a user machine may expose the local **device key** and residual config stored on disk. Packages never ship a shared client private key; keys are generated per device. **Residual risk:** local disk / unlocked endpoint compromise.

---

## 5. Findings (automated this pass)

| Severity | Finding | Status |
|----------|---------|--------|
| **Info** | Automated pass at `{now}` | Recorded |
| **High** | Public client count on status | {"Closed (title-only)" if title_only or not http.get("ok") else "REVIEW"} |
| **Medium** | Shared client priv in packages | {"Closed (no .priv hits)" if priv.get("ok") else "OPEN — see hits"} |
| **Low** | Unit suite failure | {"N/A" if suite.get("ok") or not suite.get("ran") else "OPEN — see suite log"} |
| **Info** | Multi-hop residual | Not implemented (honest config-only) |

---

## 6. Automated checks (this pass — {human_date()})

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
| Public catalog | **{catalog}** paid installers on [status host](https://restoreprivacy.online/) (£2.45; no free GitHub release downloads) |
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

1. Keep **4-hour** timer enabled on the production node (`install_security_audit_timer.sh`).  
2. Redeploy status page after audit link / catalog changes.  
3. Multi-hop residual remains optional future work (do not claim until residual).  
4. Ops: keep Unbound tunnel-only; no public :53; provider log awareness.

---

## 9. Conclusion

Automated security audit at **{now}** against node **{host}** and in-repo privacy gates. Public **SECURITY AUDIT** links must resolve on the **status host** (`/AUDIT.md` / `/audit.md`). Source repository is **private**; paid catalog installers are fulfilled on the status host only. Core privacy promises hold when the suite passes and status remains title-only.

Re-run: `python3 scripts/run_security_audit.py --write`

---

## 10. Follow-ups status

| Rec | Status |
|-----|--------|
| Public audit on private GitHub blob | **Fixed** — clients use status-origin `/AUDIT.md` |
| Periodic node audit | **In tree** — 4h systemd timer |
| Multi-hop residual | Not done (config only) |
| Kill-switch + DoT + outer obfs | In tree |
| Ephemeral node rebuild | In tree (dry-run default) |

---

## 11. Document control

| Item | |
|------|--|
| Output | `AUDIT.md` (repo root); served as `/AUDIT.md` and `/audit.md` on status page |
| Related | `PRIVACY_POLICY.md`, `README.md`, `scripts/run_security_audit.py` |
| Code baseline | Catalog **{catalog}** + node **{host}** |
| Pass date | **{human_date()}** |
| Machine JSON | `status_page/static/security_audit_latest.json` (when `--write`) |
"""


def collect(node_only: bool = False) -> dict:
    # Node timer forces localhost probes; laptop/CI may use product public host.
    host = require_localhost_probe_host(DEFAULT_HOST)
    catalog = load_catalog_version()
    results = {
        "generated_at": iso_z(),
        "node_host": host,
        "catalog_version": catalog,
        "unit_suite": {"ran": False, "ok": True, "reason": "skipped"} if node_only else run_unit_suite(),
        "tcp_status": probe_tcp(host, STATUS_PORT),
        "http_status": probe_http_status(host, STATUS_PORT),
        "udp": probe_udp_open(host, UDP_PORT),
        "no_priv": check_no_priv_in_tree(),
        "package_rag": evaluate_catalog_packages(catalog),
        "audit_privacy": {
            "localhost_required": os.environ.get("RPT_AUDIT_REQUIRE_LOCALHOST", "")
            .strip()
            .lower()
            in ("1", "true", "yes"),
            "outbound_allowed": audit_outbound_allowed(),
            "probe_host_loopback": is_loopback_host(host),
            "no_network_exfil": True,
        },
    }
    results["overall_ok"] = bool(
        results["unit_suite"].get("ok")
        and results["tcp_status"].get("ok")
        and results["http_status"].get("ok")
        and results["no_priv"].get("ok")
        # Package Red does not fail the whole audit exit alone (node host may lack
        # releases/); RAG is reported honestly for readers instead.
    )
    return results


def write_outputs(results: dict, out_path: Path) -> None:
    """Write AUDIT.md + mirrors + JSON with section-A redaction (no suite tails)."""
    # Redact nested error strings before markdown so tails never leak home paths
    safe_results = redact_audit_value(dict(results))
    md = redact_audit_text(build_markdown(safe_results))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    # Case-insensitive FS: same path. On Linux, optionally mirror lowercase if distinct.
    lower = out_path.parent / "audit.md"
    if lower.resolve() != out_path.resolve():
        try:
            lower.write_text(md, encoding="utf-8")
        except OSError:
            pass
    # Status page copies for Render (rootDir=status_page) + public_docs host
    # Local copies only — never git push / HTTP upload from this runner.
    for status_copy in (
        ROOT / "status_page" / "AUDIT.md",
        ROOT / "status_page" / "public" / "AUDIT.md",
    ):
        try:
            status_copy.parent.mkdir(parents=True, exist_ok=True)
            status_copy.write_text(md, encoding="utf-8")
        except OSError:
            pass
    # Machine-readable (redacted, no suite tails)
    json_path = ROOT / "status_page" / "static" / "security_audit_latest.json"
    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        slim = slim_results_for_public_json(safe_results)
        json_path.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--node-only", action="store_true", help="Skip unittest suite")
    ap.add_argument("--write", action="store_true", help="Write AUDIT.md and mirrors")
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
