# Restore Privacy — Code & Policy Audit

| Field | Value |
|-------|--------|
| **Product** | Restore Privacy Tunnel (RPT) |
| **Repository** | `restore_privacy` |
| **Version under review** | **0.2.2** (`client/VERSION`, catalog `RELEASE_VERSION` / `RELEASE_TAG`) |
| **Production node** | **82.221.101.241:44044** (UDP); status UI TCP 8080 |
| **Audit date** | 20 July 2026 (**0.2.2 ship pass**); threat-model scenarios refreshed |
| **Prior passes** | 0.1.8 first-pass; 0.2.0 ship; 0.2.1 docs; UK geo strip; DNS/IPv6; node pub pin; traffic-shape/PFS/multi-hop config; monitoring aggregates |
| **Audit type** | Static code + policy consistency (not a pen-test or multi-OS residual red-team) |
| **Auditor method** | Tree scan, endpoint/catalog alignment, packaging gates, security/policy unit suite; documented threat scenarios |

---

## 1. Executive summary

Restore Privacy **0.2.2** ships clients and public catalog aligned to the **FlokiNET** node at **82.221.101.241**, with product **traffic shaping enabled by default** on the Windows/Linux Python DATA path, Settings links to audit / privacy policy / end user licence, and docs aligned.

**Core privacy thesis:** **no user-info logs**, **minimal public status** (title + downloads — **no live client count**), **honest Connected** when residual full tunnel is active, **device Ed25519 keys** (no shared client private key in packages), **no third-party geo on Connect**.

**New / updated privacy hardening (this pass):**

| Area | Status |
|------|--------|
| **Public client count removed** | Status page HTML/API + node UI/API title-only; registry keeps internal size for routing only |
| Session **PFS** (ephemeral X25519 → session AEAD IKM) | Shipped on Python handshake path |
| **Layer obfuscation** (QUIC-mimic outer wrap) | **On by default** (`RPT_OBFS`); client+node DATA/HELLO path |
| **Traffic shape** (pad / jitter / cover) | **On by default**; opt out `RPT_TRAFFIC_SHAPE=0` |
| **Kill switch + IPv6 + WebRTC surface** | Windows/Linux firewall helpers + STUN/mDNS block; Android blocking flags |
| **Node DoT DNS** | Unbound tunnel-only + DoT forward; clients DNS=`10.88.0.1` only |
| **HSM/TPM-class key backend** | `node/key_backend.py` file\|mock\|sealed; product HELLO decrypt via backend |
| **PFS product default** | `require_pfs` on node/client product path; legacy lab-only |
| **Key rotation** | `node/key_rotation.py` + public re-provision; no shared client priv |
| **PQ readiness** | `docs/PQ_MIGRATION.md` + `node/pq_hybrid.py` hybrid IKM hook (not residual PQ wire) |
| **Native residual wire parity** | Android + iOS/macOS NativePrep: **PFS + RPTP/RPTC pad/cover + outer QUIC-mimic obfs** dual-wired to Python product DATA path |
| **Multi-hop** | Hop *list* config only; not residual multi-hop |

**Overall posture:** **Strong** alignment for residual honesty (`residual_ip_capture`), no public live count, no-phones-home Connect, packaging strip of `*.priv`, tunnel DNS + DoT upstream, kill-switch/IPv6, and **product wire parity** (Python + native residual engines: pad/cover/obfs/PFS) with honest DPI limits.

**Primary residual risks (open by design / environment):**

1. **Operational** — VPS/CDN/provider IP-level logging outside product no-log (privacy §4).  
2. **Apple** — residual IP still requires signed Packet Tunnel / NE; public zips may be prep packages.  
3. **Linux privilege floor** — residual needs root + TUN/`ip` (M4).  
4. **IPv6** — mitigation blocks ISP IPv6 path; node is still primarily IPv4 data-plane.  
5. **Traffic analysis** — padding/jitter/cover/outer obfs are mitigations, not undetectability guarantees.

---

## 2. Scope and method

### 2.1 In scope

| Area | Paths |
|------|--------|
| Shared client | `client/connect.py`, `endpoint.py`, `full_tunnel.py`, `secrets_loader.py`, `multihop.py`, `dataplane.py`, `product_policy.py`, `legal_links.py` |
| Windows / Linux | `client/windows/*`, `client/linux/*` |
| Mobile / Apple | `client_app/` Flutter + NativePrep residual engines (PFS/pad/cover/obfs) |
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
        v  status: title only (no public count)
[Status page]  <-- download catalog (no live counter)
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
| L5 | *(closed)* Mobile/native pad–cover–obfs–PFS lag | Dual-wired on Android + NativePrep iOS/macOS; gates in `test_native_parity_wire` / `test_native_pfs_wire`. Product `_PRODUCT_OBFS_KEY` is **33 bytes** (17 + 8 NUL + 8 tail) on Python/Kotlin/Swift — Apple pad must be `count: 8` (not 7); structural check in `TestNativeObfsKeyMatchesPython`. |

### 4.5 Info / strengths

| ID | Observation |
|----|-------------|
| I1 | Residual honesty + IPv6 honesty on product Connect |
| I2 | Dual `/1` anti-blackhole routing |
| I3 | No shared client priv; device key bootstrap |
| I4 | Public status minimization (no client count) |
| I5 | Node no-log + host privacy install script |
| I6 | Tunnel DNS default 10.88.0.1 (node Unbound) |
| I7 | Version surfaces aligned at **0.2.2** |
| I8 | MIT + CREDITS present |
| I9 | PFS unit tests (long-term-only fail) |
| I10 | Multi-hop status honesty (not routed / entry-only) |
| I11 | Self-host one-shot script |
| I12 | Product traffic-shape on by default + Settings legal links |
| I13 | Native residual pad/cover/obfs/PFS parity with Python DATA path (Android + apple_shared + iOS/macOS NativePrep; exact product obfs key length) |
| I14 | Threat model scenarios documented (VPS compromise, ISP traffic analysis, client device seizure) |

---

## 4.6 Threat model scenarios

Durable product-honest scenarios for operators and users. Update this section when architecture, defaults, or hosting assumptions change. User-facing summary: [PRIVACY_POLICY.md](PRIVACY_POLICY.md) § Threat model; plain-language pointer: [README.md](README.md).

**Honesty constraints (all scenarios):** Product does **not** claim DPI-undetectability, multi-hop residual routing, or that VPS/provider IP metadata is invisible. Pad / jitter / cover / outer obfuscation are **mitigations only**.

### Scenario A — VPS compromise

| | |
|--|--|
| **Threat** | An attacker or subpoena gains control of the operator VPS (root shell, disk image, or live memory of the RPT node process). |
| **Product response** | Node defaults: **no-log** (`node/nolog.py` — connection / session / traffic / user-info logs off); public status **title-only** (no live client count, no per-client lists); session state is **in-memory** for routing; session AEAD uses **ephemeral X25519 PFS** so long-term node key alone should not reconstruct past session traffic keys from the public transcript; packages never ship `node_elgamal.priv`; optional sealed/TPM-class backend reduces plaintext long-term key on disk. |
| **Residual risk** | **Active** sessions in memory at compromise time may still be inspectable (keys, VPN IPs, concurrent peer addresses). Provider or attacker **IP-level / netflow** logs outside the app remain. Compromised long-term keys enable future impersonation until rotation + client public-pin refresh. Disk forensics may recover misconfigured host logs if the operator disabled no-log. |

### Scenario B — Traffic analysis by ISP (or local network observer)

| | |
|--|--|
| **Threat** | The user’s ISP, workplace network, or local passive observer watches size/timing/destination of packets between the client and the product node (and may try protocol fingerprinting). |
| **Product response** | Residual full tunnel moves **destination** traffic through the node so sites see the node egress, not the home IP (when residual capture is actually up). **Outer obfuscation** (QUIC-mimic wrap) and **traffic shaping** (padding, send jitter, cover frames) reduce coarse clear-`RPT2` magic and size/timing fingerprints on the product path. Kill-switch / tunnel DNS reduce casual ISP DNS and non-tunnel leak while connected. |
| **Residual risk** | **Traffic analysis by ISP** still sees that the user talks to the VPN node (volume, duration, rough timing). Mitigations are **not** a guarantee of DPI-undetectability or pluggable-transport parity. Multi-hop residual is **not** product-routed. Behavioral patterns (when you connect, how long you stay online) remain visible to the on-path observer. |

### Scenario C — Client device seizure

| | |
|--|--|
| **Threat** | Lawful seizure or theft of the user’s phone/PC with forensic access to disk and, if unlocked, live process memory. |
| **Product response** | No product telemetry of browsing history to the node; local **device Ed25519** key is install-scoped (not a shared installer secret); licence acceptance and connection log (if used) are **local-only** and user-exportable, not uploaded by design; residual Connect does not phone home to third-party geo APIs. |
| **Residual risk** | **Client device seizure** can expose the **local device key**, settings, any local connection log, OS VPN config, browser history, and other apps—outside RPT’s no-log node promise. Full-disk encryption and OS lock screens are the primary controls; the product does not claim deniable storage or remote wipe. Possession of the device key allows tunnel use as that install until the operator revokes/rotates admission material. |

### Scenario coverage matrix (quick)

| Scenario | Primary mitigations in product | Explicit non-claim |
|----------|-------------------------------|--------------------|
| VPS compromise | No-log defaults; in-memory sessions; PFS; no public client metrics | No “provider sees nothing”; no perfect past-session secrecy if memory was live |
| ISP traffic analysis | Residual tunnel; pad/cover/obfs mitigations; kill-switch / tunnel DNS | No DPI-undetectability; no multi-hop residual |
| Client device seizure | No server-side user history; local-only prefs/logs | No protection of unlocked disk / other apps / endpoint forensics |

---

## 5. Policy consistency matrix

| Claim | Behaviour | Verdict |
|-------|-----------|---------|
| No user-info logs | `nolog.py`; systemd null stdout | Aligned (host can still misconfigure) |
| Public page: no live count | `normalize_status` title-only | Aligned |
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

1. Rebuild/sign Apple packages on a Mac from current `main` (NativePrep pad/cover/obfs/PFS) before marketing residual Apple.  
2. Redeploy status page (Render) so catalog picks up current release tag.  
3. *(done)* Native residual pad/cover/obfs/PFS dual-wire — keep NativePrep hash-aligned with apple_shared helpers.  
4. Optional next privacy: real multi-hop residual relay (only then flip `MULTI_HOP_ROUTING_IMPLEMENTED`).  
5. Ops: keep Unbound tunnel-only; no public :53; provider log awareness.  

---

## 9. Conclusion

**0.2.2+** is consistent on core privacy promises, enables product DATA traffic shaping / outer obfuscation / PFS by default on **Python and native residual engines** (Android + Apple NativePrep), surfaces audit/privacy/licence from Settings, and keeps multi-hop **honest** (config / entry-only). Remaining Medium items are privilege/environment and incomplete TA resistance — not silent product dishonesty.

Re-run after major releases or crypto/packaging changes.

---

## 10. Follow-ups status

| Rec | Status |
|-----|--------|
| M1/M2 docs | Closed |
| UK geo removal | Closed |
| Release gates / secrets | In place |
| Node pub pin + Android refresh | Closed in product |
| PFS + traffic_shape product default on | In tree (Python + native residual engines) |
| Settings legal links | In tree (Windows + Flutter) |
| Multi-hop residual | **Not done** (config only) |
| Self-host recipe | In tree |
| Kill-switch + DoT DNS + outer obfs | In tree (Python + native residual outer wrap) |
| Native pad/cover/obfs/PFS parity | **Done** (Android + iOS/macOS NativePrep; structural gates) |

---

## 11. Document control

| Item | |
|------|--|
| Output | `audit.md` (repo root) |
| Related | `PRIVACY_POLICY.md` (Threat model), `README.md` (Threat model), `scripts/RELEASE_NOTES_0.2.2.md` |
| Code baseline | 0.2.2 ship + node 82.221.101.241 |
| Threat scenarios | §4.6 — re-review on each major release |
