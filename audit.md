# Restore Privacy — Code & Policy Audit

| Field | Value |
|-------|--------|
| **Product** | Restore Privacy Tunnel (RPT) |
| **Repository** | `restore_privacy` |
| **Version under review** | **0.2.0** (`client/VERSION`, catalog `RELEASE_VERSION` / `RELEASE_TAG`) |
| **Production node** | **82.221.101.241:44044** (UDP); status UI TCP 8080 |
| **Audit date** | 19 July 2026 (**0.2.0 ship pass**) |
| **Prior passes** | 0.1.8 first-pass + follow-ups; UK geo strip; DNS prep; IPv6 honesty; host deploy |
| **Audit type** | Static code + policy consistency (not a pen-test or multi-OS residual red-team) |
| **Auditor method** | Tree scan, endpoint/catalog alignment, packaging gates, security/policy unit suite |

---

## 1. Executive summary

Restore Privacy 0.2.0 ships clients and public catalog aligned to the **FlokiNET** node at **82.221.101.241**. Core privacy thesis remains: **no user-info logs**, **minimal public status** (`clients_connected` only), **honest Connected** when residual full tunnel is active, **device Ed25519 keys** (no shared client private key in packages), **no third-party geo on Connect**.

**Overall posture:** **Strong** alignment between claims and code for residual honesty (`residual_ip_capture` / full-tunnel gates), no-phones-home Connect, packaging strip of `*.priv`, tunnel DNS default `10.88.0.1`, and IPv6 leak honesty.

**Closed since first 0.1.8 audit (re-verified this pass):**

- **M1/M2** doc Linux / shared-key phrasing  
- **UK geo gate (M5)** — removed; no product Connect to ipapi/ipinfo  
- **Socket close (L3)** on failed handshake  
- Catalog/Linux wording  

**Primary residual risks (open by design / environment):**

1. **Operational** — VPS/CDN/provider IP-level logging outside product no-log (privacy §4).  
2. **Apple** — residual IP still requires signed Packet Tunnel / NE; 0.2.0 macOS/iOS zips may be prep packages needing Mac rebuild/sign.  
3. **Linux privilege floor** — residual needs root + TUN/`ip` (M4).  
4. **IPv6** — mitigation blocks ISP IPv6 path; node is still primarily IPv4 data-plane.  

**Supporting automated run (this pass):** representative security/policy modules — see §6 (exit 0 preferred).

---

## 2. Scope and method

### 2.1 In scope

| Area | Paths |
|------|--------|
| Shared client | `client/connect.py`, `endpoint.py`, `full_tunnel.py`, `secrets_loader.py`, `ui_theme.py` |
| Windows / Linux | `client/windows/*`, `client/linux/*` |
| Mobile / Apple | `client_app/` Flutter + NativePrep |
| Node | `node/*` (handshake, nolog, install scripts) |
| Public web | `status_page/*` catalog v0.2.0 |
| Packaging | `scripts/build_release_0.2.0.py`, `package_linux.py` |
| Policies | `PRIVACY_POLICY.md`, `LICENSE`, `CREDITS.md`, `README.md`, `sundries.txt`, `audit.md` |

### 2.2 Method notes

- Version surfaces: `client/VERSION` == catalog **0.2.0**.  
- Product default host **82.221.101.241** (not 104.156.224.47).  
- Spot-checked packaging `_assert_no_priv`, `secrets/` gitignore, install_dns + install_host_privacy.  
- **Did not** paste secret material into this document.

---

## 3. Architecture snapshot

```
[Clients 0.2.0 → 82.221.101.241:44044]
        |  RPT2 handshake + sealed DATA
        v
[Node on FlokiNET: admission + sessions + NAT + Unbound 10.88.0.1]
        |
        v  status: title + clients_connected only
[Status page]  <-- download catalog v0.2.0
```

---

## 4. Findings

### 4.1 High

| ID | Finding | Evidence | Follow-up |
|----|---------|----------|-----------|
| — | **No High finding** of intentional private-key shipping or user-info logging in product defaults. | Packaging strip; inject denylist; `node/nolog.py`; status allow-list. | Keep release gates. |

### 4.2 Medium — open (environment / platform)

| ID | Finding | Evidence | Follow-up |
|----|---------|----------|-----------|
| M3 | Apple residual depends on NE signing | README Apple / prep zips | Keep residual UI honest until signed |
| M4 | Linux residual needs root + TUN/`ip` | `product_connect_requires_root` | Honest marketing |
| M5 | *(closed)* UK geo third-party | Removed 0.1.9+ source; 0.2.0 product | Do not reintroduce |
| M6 | Host/provider logging outside app | Privacy §4; FlokiNET policies | Operator discipline |

### 4.3 Medium — closed

| ID | Status | Evidence |
|----|--------|----------|
| M1 | Closed | Privacy §3.2 includes Linux |
| M2 | Closed | README `do **not** ship a shared` |
| UK gate | Closed | `client/uk_gate.py` gone; product Connect no geo HTTPS |

### 4.4 Low

| ID | Finding | Status |
|----|---------|--------|
| L1 | Historical `build_release_0.*.py` surface | Accepted; use current-tag script |
| L2 | Local `dist/`/`build/` hygiene | gitignored |
| L4 | manylinux ABI matrix | Re-run `package_linux.py` each tag |

### 4.5 Info / strengths

| ID | Observation |
|----|-------------|
| I1 | Residual honesty + IPv6 honesty on product Connect |
| I2 | Dual `/1` anti-blackhole routing |
| I3 | No shared client priv; device key bootstrap |
| I4 | Public status minimization |
| I5 | Node no-log + host privacy install script |
| I6 | Tunnel DNS default 10.88.0.1 (node Unbound) |
| I7 | Version surfaces aligned at 0.2.0 |
| I8 | MIT + CREDITS present |

---

## 5. Policy consistency matrix

| Claim | Behaviour | Verdict |
|-------|-----------|---------|
| No user-info logs | `nolog.py`; systemd null stdout | Aligned (host can still misconfigure) |
| Public page: live count only | `normalize_status` | Aligned |
| No shared client priv | Strip/generate device key | Aligned |
| Residual only with full tunnel | Product gates | Aligned |
| No third-party geo on Connect | No phones-home tests | Aligned |
| Catalog v0.2.0 + node 82.221… | downloads + endpoint | Aligned |

---

## 6. Automated checks (this pass)

**Modules (representative):** `test_endpoint_alignment`, `test_downloads`, `test_connect_no_phones_home`, `test_uk_gate`, `test_ipv6_leak_protection`, `test_audit_md`, `test_audit_followups`, residual/secrets/legal as available.

| Result | Detail |
|--------|--------|
| **Suite** | `python -m unittest discover -s tests -v` → **432 tests OK** (exit 0) |
| **Log** | SCRATCH / `v020_audit_tests.log` (local implementer run, 19 July 2026) |

### 6.1 Package host credibility (0.2.0 assets)

| Package | Host check |
|---------|------------|
| Windows setup | PYZ `client.endpoint` contains **82.221.101.241**; no **104.156.224.47** |
| Android APK | Binary strings include **82.221.101.241** (×3); no old IP |
| Linux `.tar.gz` | `client/endpoint.py` + docs → **82.221.101.241** |
| macOS / iOS zips | Host string patched to **82.221.101.241** (same-length replace); Mac rebuild/sign still required for residual NE |

---

## 7. Secrets & packaging checklist

| Control | Status |
|---------|--------|
| `secrets/` gitignored | Yes |
| Installer strip `*.priv` | Yes |
| `_assert_no_priv` on release | Yes (`build_release_0.2.0.py`) |
| Never force-add secrets | Documented |
| This audit embeds no keys | Confirmed |

---

## 8. Recommendations (non-binding)

1. Rebuild Apple packages on a Mac with 0.2.0 sources before marketing residual Apple.  
2. Redeploy status page (Render) so catalog/upstream pick up 0.2.0.  
3. Optional next privacy: Connect kill-switch; device-key rotate UI; client “no unexpected HTTPS” continuous gate (already tested).  
4. Ops: keep Unbound tunnel-only; no public :53; provider log awareness.  

---

## 9. Conclusion

**0.2.0** is consistent on core privacy promises and points clients at the current production node. Remaining Medium items are privilege/environment (Apple NE, Linux root, host logs)—not silent product dishonesty.

Re-run after major releases or crypto/packaging changes.

---

## 10. Follow-ups status

| Rec | Status |
|-----|--------|
| M1/M2 docs | Closed |
| UK geo removal | Closed in product 0.2.0 |
| Release gates / secrets | In place |
| Linux wheels each tag | Documented + 0.2.0 package built |
| Node DNS + host privacy scripts | In tree; applied on 82.221.101.241 |
| Optional kill-switch / multi-hop | Not done (future) |

---

## 11. Document control

| Item | |
|------|--|
| Output | `audit.md` (repo root) |
| Related | `PRIVACY_POLICY.md`, `README.md`, `scripts/RELEASE_NOTES_0.2.0.md` |
| Code baseline | 0.2.0 ship + node 82.221.101.241 |
