# Restore Privacy — Code & Policy Audit

| Field | Value |
|-------|--------|
| **Product** | Restore Privacy Tunnel (RPT / RPT2) |
| **Repository** | [restore-privacy](https://github.com/rgsneddon/restore-privacy) (public packages + operator tree) |
| **Public catalog version** | **0.2.9** |
| **Production node** | **82.221.101.241:44044** (UDP); status UI TCP **8080** |
| **Audit generated** | **21 July 2026** (`2026-07-21T02:30:04Z`) |
| **Cadence** | Automated security pass (target **every 4 hours** on node/operator timer) |
| **Audit type** | Static suite + live node status probe (not a pen-test or multi-OS residual red-team) |
| **Auditor method** | `scripts/run_security_audit.py` — unittest privacy/security modules + TCP/HTTP/UDP probes + no-`.priv` scan |

---

## 1. Executive summary

Latest automated security audit for production node **82.221.101.241** and the in-repo privacy/security gates.

**Core privacy thesis (unchanged):** **no user-info logs**, **minimal public status** (title + downloads — **no live client count**), **honest Connected** only when residual full tunnel is active (`residual_ip_capture`), **device Ed25519 keys** (no shared client private key in packages), **no third-party geo on Connect**, **session PFS** + outer **obfs** as **mitigations** (traffic-analysis resistance only — not a claim of full protocol camouflage).

**This pass (automated):**

| Check | Result |
|-------|--------|
| Security unit suite | **PASS** (9 modules) |
| Node status TCP :8080 | reachable |
| Node `/status` HTTP | OK — title-only=True |
| UDP product port :44044 | probe sent |
| No `*.priv` under product/releases/status_page | OK |
| Live node healthy (TCP+HTTP) | YES |

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
| Public web | `status_page/*` catalog **0.2.9** |
| Policies | `PRIVACY_POLICY.md`, `LICENSE`, `CREDITS.md`, `README.md`, `AUDIT.md` |

### 2.2 Method notes

- Public audit URLs use **restore-privacy** GitHub (`AUDIT.md`). Status page also serves **`/AUDIT.md`** and **`/audit.md`**.  
- Product default host **82.221.101.241**.  
- Product node ElGamal pub pin: `product/NODE_ELGAMAL_PUB.sha256` (SHA-256 `1b126abf…`).  
- **Did not** paste secret material into this document.

---

## 3. Live node probe results

| Probe | Detail |
|-------|--------|
| TCP `82.221.101.241:8080` | ok=True error=None |
| HTTP `http://82.221.101.241:8080/status` | code=200 body={'title': 'RESTORE PRIVACY'} |
| UDP `82.221.101.241:44044` | sent=True error=None |

**Expectation:** `/status` returns title-only JSON (e.g. `{"title":"RESTORE PRIVACY"}`) — **never** a live client count.

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
| **Info** | Automated pass at `2026-07-21T02:30:04Z` | Recorded |
| **High** | Public client count on status | Closed (title-only) |
| **Medium** | Shared client priv in packages | Closed (no .priv hits) |
| **Low** | Unit suite failure | N/A |
| **Info** | Multi-hop residual | Not implemented (honest config-only) |

---

## 6. Automated checks (this pass — 21 July 2026)

**Modules:** `tests.test_legal_links`, `tests.test_legal_docs`, `tests.test_no_public_client_count`, `tests.test_connect_no_phones_home`, `tests.test_obfuscation`, `tests.test_kill_switch_leaks`, `tests.test_product_node_key`, `tests.test_pfs_product_require`, `tests.test_downloads`

| Result | Detail |
|--------|--------|
| **Unit suite** | **PASS** (9 modules) |
| **Return code** | 0 |
| **Log** | operator SCRATCH / `security_audit.log` / node journal `rpt-security-audit.service` |
| **Generator** | `scripts/run_security_audit.py` |

### 6.1 Package host credibility

| Expectation | Notes |
|-------------|--------|
| Product host | **82.221.101.241** |
| Public catalog | **0.2.9** on [restore-privacy releases](https://github.com/rgsneddon/restore-privacy/releases) |
| Node pub pin | `1b126abf…` |
| No `.priv` in public package trees | OK |

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

Automated security audit at **2026-07-21T02:30:04Z** against node **82.221.101.241** and in-repo privacy gates. Public **SECURITY AUDIT** links must resolve on the **public** restore-privacy host (and/or status-page `/AUDIT.md`). Core privacy promises hold when the suite passes and status remains title-only.

Re-run: `python3 scripts/run_security_audit.py --write`

---

## 10. Follow-ups status

| Rec | Status |
|-----|--------|
| Public audit 404 (private RUST-IN-PRIVACY blob) | **Fixed** — links → restore-privacy + local `/AUDIT.md` |
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
| Code baseline | Catalog **0.2.9** + node **82.221.101.241** |
| Pass date | **21 July 2026** |
| Machine JSON | `status_page/static/security_audit_latest.json` (when `--write`) |
