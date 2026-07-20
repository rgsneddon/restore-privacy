# Restore Privacy — Code & Policy Audit

| Field | Value |
|-------|--------|
| **Product** | Restore Privacy Tunnel (RPT) |
| **Repository** | `restore_privacy` |
| **Version under review** | **0.2.2** (`client/VERSION`, catalog `RELEASE_VERSION` / `RELEASE_TAG`) |
| **Production node** | **82.221.101.241:44044** (UDP); status UI TCP 8080 |
| **Audit date** | 20 July 2026 (**0.2.2 ship pass**) |
| **Prior passes** | 0.1.8 first-pass; 0.2.0 ship; 0.2.1 docs; UK geo strip; DNS/IPv6; node pub pin; traffic-shape/PFS/multi-hop config |
| **Audit type** | Static code + policy consistency (not a pen-test or multi-OS residual red-team) |
| **Auditor method** | Tree scan, endpoint/catalog alignment, packaging gates, security/policy unit suite |

---

## 1. Executive summary

Restore Privacy **0.2.2** ships clients and public catalog aligned to the **FlokiNET** node at **82.221.101.241**, with product **traffic shaping enabled by default** on the Windows/Linux Python DATA path, Settings links to audit / privacy policy / end user licence, and docs aligned.

**Core privacy thesis (unchanged):** **no user-info logs**, **minimal public status** (`clients_connected` only), **honest Connected** when residual full tunnel is active, **device Ed25519 keys** (no shared client private key in packages), **no third-party geo on Connect**.

**New / updated since 0.2.1 (this pass):**

| Area | Status |
|------|--------|
| Session **PFS** (ephemeral X25519 → session AEAD IKM) | Shipped on Python handshake path; unit-proven long-term-only reconstruction fails |
| **Traffic shape** (pad / jitter / cover) | **Enabled by default** via `product_dataplane_traffic_shape()`; opt out `RPT_TRAFFIC_SHAPE=0` |
| **Settings legal links** | Audit, privacy policy, end user licence → stable GitHub blob URLs |
| **Multi-hop** | Hop *list* config only; `is_multihop_active() is False`; status **entry-only / not routed** |
| **Self-host** | `scripts/selfhost_node.sh` one-shot recipe |
| **Product node pub pin** | `product/node_elgamal.pub` + Android assets refresh on Connect |

**Overall posture:** **Strong** alignment between claims and code for residual honesty (`residual_ip_capture`), no-phones-home Connect, packaging strip of `*.priv`, tunnel DNS default `10.88.0.1`, IPv6 leak honesty, multi-hop **honesty**, and product traffic-shape **on by default** with honest DPI limits.

**Primary residual risks (open by design / environment):**

1. **Operational** — VPS/CDN/provider IP-level logging outside product no-log (privacy §4).  
2. **Apple** — residual IP still requires signed Packet Tunnel / NE; 0.2.2 macOS/iOS zips may be prep packages.  
3. **Linux privilege floor** — residual needs root + TUN/`ip` (M4).  
4. **IPv6** — mitigation blocks ISP IPv6 path; node is still primarily IPv4 data-plane.  
5. **Traffic analysis** — padding/jitter/cover are mitigations, not undetectability guarantees.  
6. **Mobile wire parity** — Android/Apple native engines may lag Python pad/cover/PFS wire extensions (honest staging).

---

## 2. Scope and method

### 2.1 In scope

| Area | Paths |
|------|--------|
| Shared client | `client/connect.py`, `endpoint.py`, `full_tunnel.py`, `secrets_loader.py`, `multihop.py`, `dataplane.py`, `product_policy.py`, `legal_links.py` |
| Windows / Linux | `client/windows/*`, `client/linux/*` |
| Mobile / Apple | `client_app/` Flutter + NativePrep |
| Node | `node/*` (handshake, pfs, traffic_shape, crypto_session, nolog, install scripts) |
| Public web | `status_page/*` catalog **v0.2.2** |
| Packaging | `scripts/build_release_0.2.2.py`, `package_linux.py`, `selfhost_node.sh` |
| Policies | `PRIVACY_POLICY.md`, `LICENSE`, `CREDITS.md`, `README.md`, `sundries.txt`, `audit.md` |

### 2.2 Method notes

- Version surfaces: `client/VERSION` == catalog **0.2.2**.  
- Product default host **82.221.101.241** (not 104.156.224.47).  
- Product node ElGamal pub pin: `PRODUCT_NODE_ELGAMAL_PUB_SHA256` / `product/NODE_ELGAMAL_PUB.sha256`.  
- Spot-checked `_assert_no_priv`, multi-hop honesty flags, traffic_shape product default **on**.  
- **Did not** paste secret material into this document.

---

## 3. Architecture snapshot

```
[Clients 0.2.2 → 82.221.101.241:44044]
        |  RPT2 HELLO (Ed25519 + ElGamal hybrid + optional X25519 PFS)
        |  sealed DATA (± product pad / cover by default on Python path)
        v
[Node: admission + sessions + NAT + Unbound 10.88.0.1]
        |
        v  status: title + clients_connected only
[Status page]  <-- download catalog v0.2.2
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
| M5 | *(closed)* UK geo third-party | Removed 0.1.9+ source | Do not reintroduce |
| M6 | Host/provider logging outside app | Privacy §4 | Operator discipline |
| M7 | Traffic analysis not eliminated by pad/jitter/cover | product default on; policy §4/§7 | No over-claim (mitigation ≠ undetectability) |
| M8 | Multi-hop not residual yet | `MULTI_HOP_ROUTING_IMPLEMENTED = False` | Do not market multi-hop residual |

### 4.3 Medium — closed

| ID | Status | Evidence |
|----|--------|----------|
| M1 | Closed | Privacy §3.2 includes Linux |
| M2 | Closed | README `do not` ship a shared client priv |
| UK gate | Closed | No product Connect geo HTTPS |
| Node pub pin | Closed in product | `product/node_elgamal.pub` + Android refresh |

### 4.4 Low

| ID | Finding | Status |
|----|---------|--------|
| L1 | Historical `build_release_0.*.py` surface | Accepted; use current-tag script |
| L2 | Local `dist/`/`build/` hygiene | gitignored |
| L4 | manylinux ABI matrix | Re-run `package_linux.py` each tag |
| L5 | Mobile/native PFS/pad parity lag | Documented; Python path primary |

### 4.5 Info / strengths

| ID | Observation |
|----|-------------|
| I1 | Residual honesty + IPv6 honesty on product Connect |
| I2 | Dual `/1` anti-blackhole routing |
| I3 | No shared client priv; device key bootstrap |
| I4 | Public status minimization |
| I5 | Node no-log + host privacy install script |
| I6 | Tunnel DNS default 10.88.0.1 (node Unbound) |
| I7 | Version surfaces aligned at **0.2.2** |
| I8 | MIT + CREDITS present |
| I9 | PFS unit tests (long-term-only fail) |
| I10 | Multi-hop status honesty (not routed / entry-only) |
| I11 | Self-host one-shot script |
| I12 | Product traffic-shape on by default + Settings legal links |

---

## 5. Policy consistency matrix

| Claim | Behaviour | Verdict |
|-------|-----------|---------|
| No user-info logs | `nolog.py`; systemd null stdout | Aligned (host can still misconfigure) |
| Public page: live count only | `normalize_status` | Aligned |
| No shared client priv | Strip/generate device key | Aligned |
| Residual only with full tunnel | Product gates | Aligned |
| No third-party geo on Connect | No phones-home tests | Aligned |
| Catalog v0.2.2 + node 82.221… | downloads + endpoint | Aligned |
| Multi-hop residual | Config only; active=False | Aligned (honest) |
| PFS session keys | X25519 in handshake KDF | Aligned (Python path) |
| Traffic shape | Product default **on**; opt-out env | Aligned |

---

## 6. Automated checks (this pass)

**Modules (representative):** `test_endpoint_alignment`, `test_downloads`, `test_connect_no_phones_home`, `test_pfs`, `test_traffic_shape`, `test_product_traffic_shape`, `test_legal_links`, `test_multihop`, `test_product_node_key`, `test_audit_md`, residual/secrets/legal as available.

| Result | Detail |
|--------|--------|
| **Target** | Exit 0 on supporting suite |
| **Log** | SCRATCH / `tests_0.2.2.log` |

### 6.1 Package host credibility (0.2.2)

| Expectation | Notes |
|-------------|--------|
| Product host | **82.221.101.241** in endpoint sources and packages |
| Node pub | Pin `1b126abf…` (`product/NODE_ELGAMAL_PUB.sha256`) |
| No `.priv` in public packages | `_assert_no_priv` / inject gates |

---

## 7. Secrets & packaging checklist

| Control | Status |
|---------|--------|
| `secrets/` gitignored | Yes |
| Installer strip `*.priv` | Yes |
| `_assert_no_priv` on release | Yes (`build_release_0.2.2.py`) |
| Product `node_elgamal.pub` tracked | Yes (`product/`) |
| Never force-add secrets | Documented |
| This audit embeds no keys | Confirmed |

---

## 8. Recommendations (non-binding)

1. Rebuild/sign Apple packages on a Mac with 0.2.2 sources before marketing residual Apple.  
2. Redeploy status page (Render) so catalog picks up **0.2.2**.  
3. Wire Android/Apple engines to Python pad/cover/PFS wire when residual native path is ready.  
4. Optional next privacy: Connect kill-switch; real multi-hop relay (only then flip `MULTI_HOP_ROUTING_IMPLEMENTED`).  
5. Ops: keep Unbound tunnel-only; no public :53; provider log awareness.  

---

## 9. Conclusion

**0.2.2** is consistent on core privacy promises, enables product DATA traffic shaping by default with honest DPI limits, surfaces audit/privacy/licence from Settings, and keeps multi-hop **honest** (config / entry-only). Remaining Medium items are privilege/environment and incomplete TA resistance — not silent product dishonesty.

Re-run after major releases or crypto/packaging changes.

---

## 10. Follow-ups status

| Rec | Status |
|-----|--------|
| M1/M2 docs | Closed |
| UK geo removal | Closed |
| Release gates / secrets | In place |
| Node pub pin + Android refresh | Closed in product |
| PFS + traffic_shape product default on | In tree (Python path) |
| Settings legal links | In tree (Windows + Flutter) |
| Multi-hop residual | **Not done** (config only) |
| Self-host recipe | In tree |
| Optional kill-switch | Not done (future) |

---

## 11. Document control

| Item | |
|------|--|
| Output | `audit.md` (repo root) |
| Related | `PRIVACY_POLICY.md`, `README.md`, `scripts/RELEASE_NOTES_0.2.2.md` |
| Code baseline | 0.2.2 ship + node 82.221.101.241 |
