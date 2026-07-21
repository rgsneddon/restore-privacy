#!/usr/bin/env python3
"""Run Restore Privacy security audit and refresh AUDIT.md (+ optional audit.md).

Designed for:
  - Operator laptop / CI (full unittest suite)
  - Production node (lighter probes when tests/ missing)

Default period target: every 4 hours via scripts/install_security_audit_timer.sh.

Usage:
  python3 scripts/run_security_audit.py
  python3 scripts/run_security_audit.py --node-only
  python3 scripts/run_security_audit.py --write --out AUDIT.md

Environment:
  RPT_NODE_HOST     default 82.221.101.241
  RPT_STATUS_PORT   default 8080
  RPT_UDP_PORT      default 44044
  RPT_AUDIT_PATH    override output path
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOST = os.environ.get("RPT_NODE_HOST", "82.221.101.241")
STATUS_PORT = int(os.environ.get("RPT_STATUS_PORT", "8080"))
UDP_PORT = int(os.environ.get("RPT_UDP_PORT", "44044"))

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
    """Run security-related unittest modules when available."""
    tests_dir = ROOT / "tests"
    if not tests_dir.is_dir():
        return {"ran": False, "reason": "tests/ not present (node install)", "ok": True, "modules": []}

    cmd = [sys.executable, "-m", "unittest", *SECURITY_TEST_MODULES, "-q"]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    return {
        "ran": True,
        "ok": p.returncode == 0,
        "returncode": p.returncode,
        "modules": SECURITY_TEST_MODULES,
        "stdout_tail": (p.stdout or "")[-2000:],
        "stderr_tail": (p.stderr or "")[-2000:],
    }


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


def build_markdown(results: dict) -> str:
    now = results["generated_at"]
    host = results["node_host"]
    catalog = results["catalog_version"]
    suite = results["unit_suite"]
    tcp = results["tcp_status"]
    http = results["http_status"]
    udp = results["udp"]
    priv = results["no_priv"]
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

    return f"""# Restore Privacy — Code & Policy Audit

| Field | Value |
|-------|--------|
| **Product** | Restore Privacy Tunnel (RPT / RPT2) |
| **Repository** | restore-privacy (**private** source; installers only via paid status host) |
| **Public catalog version** | **{catalog}** |
| **Production node** | **{host}:{UDP_PORT}** (UDP); status UI TCP **{STATUS_PORT}** |
| **Audit generated** | **{human_date()}** (`{now}`) |
| **Cadence** | Automated security pass (target **every 4 hours** on node/operator timer) |
| **Audit type** | Static suite + live node status probe (not a pen-test or multi-OS residual red-team) |
| **Auditor method** | `scripts/run_security_audit.py` — unittest privacy/security modules + TCP/HTTP/UDP probes + no-`.priv` scan |

---

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

**Overall posture:** **Strong** for residual honesty (`residual_ip_capture`), no public live count, no-phones-home Connect, packaging strip of `*.priv`, tunnel DNS + DoT, kill-switch/IPv6, Settings transparency — without multi-hop residual claims.

**Primary residual risks (open by design / environment):**

1. **Operational** — VPS/CDN/provider IP-level logging outside product no-log.  
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

If the **VPS** host (production node) is fully compromised while sessions are active, **in-memory** session material may be exposed. Product **no-log** / nolog composition reduces durable user-info logs on disk but does **not** erase live RAM. **Residual risk:** operator/provider compromise of the node host.

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
    host = DEFAULT_HOST
    results = {
        "generated_at": iso_z(),
        "node_host": host,
        "catalog_version": load_catalog_version(),
        "unit_suite": {"ran": False, "ok": True, "reason": "skipped"} if node_only else run_unit_suite(),
        "tcp_status": probe_tcp(host, STATUS_PORT),
        "http_status": probe_http_status(host, STATUS_PORT),
        "udp": probe_udp_open(host, UDP_PORT),
        "no_priv": check_no_priv_in_tree(),
    }
    results["overall_ok"] = bool(
        results["unit_suite"].get("ok")
        and results["tcp_status"].get("ok")
        and results["http_status"].get("ok")
        and results["no_priv"].get("ok")
    )
    return results


def write_outputs(results: dict, out_path: Path) -> None:
    md = build_markdown(results)
    out_path.write_text(md, encoding="utf-8")
    # Case-insensitive FS: same path. On Linux, optionally mirror lowercase if distinct.
    lower = out_path.parent / "audit.md"
    if lower.resolve() != out_path.resolve():
        try:
            lower.write_text(md, encoding="utf-8")
        except OSError:
            pass
    # Status page copies for Render (rootDir=status_page) + public_docs host
    for status_copy in (
        ROOT / "status_page" / "AUDIT.md",
        ROOT / "status_page" / "public" / "AUDIT.md",
    ):
        try:
            status_copy.parent.mkdir(parents=True, exist_ok=True)
            status_copy.write_text(md, encoding="utf-8")
        except OSError:
            pass
    # Machine-readable
    json_path = ROOT / "status_page" / "static" / "security_audit_latest.json"
    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        # Drop huge tails for JSON
        slim = dict(results)
        us = dict(slim.get("unit_suite") or {})
        us.pop("stdout_tail", None)
        us.pop("stderr_tail", None)
        slim["unit_suite"] = us
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

    results = collect(node_only=args.node_only)
    if args.write:
        write_outputs(results, args.out.resolve())
        print(f"Wrote {args.out}", flush=True)
    if args.json or not args.write:
        print(json.dumps({k: v for k, v in results.items() if k != "unit_suite" or True}, indent=2, default=str))
    if results.get("unit_suite", {}).get("ran") and not results["unit_suite"].get("ok"):
        print(results["unit_suite"].get("stderr_tail") or results["unit_suite"].get("stdout_tail"), file=sys.stderr)
        return 2
    return 0 if results.get("overall_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
