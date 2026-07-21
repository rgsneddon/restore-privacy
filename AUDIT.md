# Restore Privacy — Code & Policy Audit

| Field | Value |
|-------|--------|
| **Product** | Restore Privacy Tunnel (RPT / RPT2) |
| **Repositories** | **Private** `restore_privacy` (node/client/status_page) · **Public** [RUST-IN-PRIVACY](https://github.com/rgsneddon/RUST-IN-PRIVACY) (protocol crates + device packages) |
| **Public product version** | **1.0.0** / tag **v1.0.0** ([release](https://github.com/rgsneddon/RUST-IN-PRIVACY/releases/tag/v1.0.0)) |
| **Private tree label** | `client/VERSION` may read **0.2.3** (legacy GUI packaging); status-page catalog is **1.0.0** |
| **Production node** | **82.221.101.241:44044** (UDP); status UI TCP 8080; deploy: Python `node.server` via `scripts/deploy_rpt_node.py` |
| **Audit date** | **21 July 2026** (**docs + dual-repo security pass** — public v1.0.0 installers + production Python node) |
| **Prior passes** | 0.1.8–0.2.3 ship/docs; UK geo strip; DNS/IPv6; node pub pin; traffic-shape/PFS; native parity; monitoring; threat model; FDE; ephemeral nodes; Rust cutover / Android residual |
| **Audit type** | Static code + policy consistency (not a pen-test or multi-OS residual red-team) |
| **Auditor method** | Tree scan, endpoint/catalog alignment, packaging gates, security/policy unit suite; threat scenarios; release no-priv; live HELLO pin check |

---

## 1. Executive summary

Restore Privacy’s **public product ship is v1.0.0** on **RUST-IN-PRIVACY**: Windows/Linux/macOS/iOS/Android residual packages, product ElGamal **pub pin** only, and download buttons that use explicit  
`https://github.com/rgsneddon/RUST-IN-PRIVACY/releases/download/v1.0.0/<file>` URLs. The **private** tree still hosts the **Python production node**, Flutter residual client sources, status page, and operator tooling. Production endpoint remains **82.221.101.241:44044**.

**Core privacy thesis:** **no user-info logs**, **minimal public status** (title + downloads — **no live client count**), **honest Connected** when residual full tunnel is active, **device Ed25519 keys** (no shared client private key in packages), **no third-party geo on Connect**, **session PFS** + outer **obfs** as **mitigations** (not DPI-undetectability).

**Carry-forward privacy hardening (0.2.x → 1.0.0 public packages):**

| Area | Status |
|------|--------|
| **Public client count removed** | Status page HTML/API + node UI/API title-only; registry keeps internal size for routing only |
| Session **PFS** (ephemeral X25519 → session AEAD IKM) | Python + native residual dual-wire |
| **Layer obfuscation** (QUIC-mimic outer wrap) | **On by default**; product key **33 bytes** (Python/Kotlin/Swift) |
| **Traffic shape** (pad / jitter / cover) | **On by default** product residual DATA path |
| **Native residual wire parity** | Android + iOS/macOS NativePrep pad/cover/obfs/PFS |
| **Android connect hotfix** | Rebuilt APK embeds `pfs-x25519` + `RPT-OBFS-LAYER` (prior 0.2.3 APK lacked PFS → node silent-drop / Poll timed out); licence + Settings in Flutter; HELLO retries |
| **Desktop connect UX** | Windows/Linux residual attach off Tk UI thread (no Not Responding freeze); Linux licence gate + Settings |
| **Settings transparency** | Local connection log (exportable), leak test, DPI mitigation disclaimer |
| **Licence gate** | Accept end-user licence before Connect / autoconnect; local-only store |
| **Anon registration honesty** | No admin/operator verification for device key; OS elevation for residual is separate |
| **Aggregate monitoring** | Process-wide bandwidth only; never per-client; not on public status |
| **Threat model docs** | audit §4.6 + PRIVACY_POLICY + README (VPS / ISP / device seizure) |
| **LUKS/dm-crypt FDE + wipe** | Operator scripts; compose with no-log; at-rest honesty |
| **Ephemeral short-lived nodes** | Periodic snapshot/rebuild plan; dry-run default |
| **Multi-hop** | Hop *list* config only; not residual multi-hop |

**Overall posture:** **Strong** alignment for residual honesty (`residual_ip_capture`), no public live count, no-phones-home Connect, packaging strip of `*.priv`, tunnel DNS + DoT, kill-switch/IPv6, native wire parity, user-facing honesty (licence, DPI, threat model), and operator at-rest/ephemeral tooling — without over-claiming DPI-undetectability or multi-hop residual.

**Primary residual risks (open by design / environment):**

1. **Operational** — VPS/CDN/provider IP-level logging outside product no-log (privacy §4 / threat model).  
2. **Apple** — residual IP still requires signed Packet Tunnel / NE; public **v1.0.0** zips are residual packages (see RUST-IN-PRIVACY `docs/APPLE_HANDOFF_1.0.0.md`).  
3. **Linux privilege floor** — residual needs root + TUN/`ip` (M4).  
4. **IPv6** — mitigation blocks ISP IPv6 path; node is still primarily IPv4 data-plane.  
5. **Traffic analysis** — padding/jitter/cover/outer obfs are mitigations, not undetectability guarantees.  
6. **FDE / wipe / rebuild** — protect at-rest or reduce on-host state only; not provider snapshots/netflow; unlocked root still sees secrets.

---

## 2. Scope and method

### 2.1 In scope

| Area | Paths |
|------|--------|
| Shared client | `client/connect.py`, `endpoint.py`, `full_tunnel.py`, `secrets_loader.py`, `multihop.py`, `dataplane.py`, `product_policy.py`, `legal_links.py` |
| Windows / Linux | `client/windows/*`, `client/linux/*` |
| Mobile / Apple | `client_app/` Flutter + NativePrep residual engines (PFS/pad/cover/obfs) |
| Node | `node/*` (handshake, pfs, traffic_shape, crypto_session, nolog, install scripts) |
| Public web | `status_page/*` catalog **v1.0.0** → RUST-IN-PRIVACY release assets |
| Packaging | Public: RUST-IN-PRIVACY `scripts/build_release_1.0.0.py` + Flutter APK; private legacy: `scripts/build_release_0.2.3.py` |
| Policies | `PRIVACY_POLICY.md`, `LICENSE`, `CREDITS.md`, `README.md`, `sundries.txt`, `AUDIT.md` |

### 2.2 Method notes

- Public version surfaces: status-page `RELEASE_VERSION` / `RELEASE_TAG` = **1.0.0** / **v1.0.0**; package basenames `restore-privacy-rust-1.0.0-*`.  
- Private `client/VERSION` may remain **0.2.3** (GUI packaging history) without being the public download catalog.  
- Product default host **82.221.101.241**.  
- Product node ElGamal pub pin: `PRODUCT_NODE_ELGAMAL_PUB_SHA256` / `product/NODE_ELGAMAL_PUB.sha256` (SHA-256 `1b126abf…`).  
- Spot-checked no tracked `*.priv` in public host, multi-hop honesty, traffic_shape / obfs product defaults **on**.  
- **Did not** paste secret material into this document.

---

## 3. Architecture snapshot

```
[Public installers v1.0.0  →  82.221.101.241:44044]
        |  RPT2 HELLO (Ed25519 + ElGamal hybrid + X25519 PFS + outer obfs)
        |  sealed DATA (± product pad / cover on residual paths)
        v
[Production node: Python node.server + NAT + Unbound 10.88.0.1]
        |  secrets: node_elgamal.priv (host only, never packaged)
        v  status API: title only (no public count)
[Status page]  <-- catalog hrefs …/RUST-IN-PRIVACY/releases/download/v1.0.0/<file>
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
| I7 | Public version surfaces aligned at **v1.0.0** (catalog + RUST-IN-PRIVACY); private `client/VERSION` may lag |
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
| Catalog **v1.0.0** + node 82.221… | `status_page/downloads.py` → RUST-IN-PRIVACY `/releases/download/v1.0.0/` | Aligned |
| Multi-hop residual | Config only; active=False | Aligned (honest) |
| PFS session keys | X25519 in handshake KDF | Aligned (Python path) |
| Traffic shape | Product default **on**; opt-out env | Aligned |

---

## 6. Automated checks (this pass — 21 July 2026)

**Modules (representative):** `test_audit_md`, `test_threat_model_docs`, `test_legal_docs`, `test_legal_links`, `test_downloads`, `test_product_node_key`, `test_pfs_product_require`, `test_obfuscation`, `test_kill_switch_leaks`, `test_ipv6_leak_protection`, `test_internet_blackhole`, `test_android_release_wire`, `test_no_public_client_count`, `test_connect_no_phones_home`; RUST-IN-PRIVACY `test_release_1_0_0` + `cargo test --workspace`.

| Result | Detail |
|--------|--------|
| **Target** | Exit 0 on security/structural suite |
| **Log** | SCRATCH / `security_audit.log` / `audit_doc_tests.log` / `cargo_security.log` |

### 6.1 Package host credibility (public v1.0.0)

| Expectation | Notes |
|-------------|--------|
| Product host | **82.221.101.241** in endpoint sources and packages |
| Public release | [RUST-IN-PRIVACY v1.0.0](https://github.com/rgsneddon/RUST-IN-PRIVACY/releases/tag/v1.0.0) |
| Node pub | Pin `1b126abf…` (`product/NODE_ELGAMAL_PUB.sha256`) |
| No `.priv` in public packages | `_assert_no_priv` / inject gates / public tree scan |

---

## 7. Secrets & packaging checklist

| Control | Status |
|---------|--------|
| `secrets/` gitignored | Yes |
| Installer strip `*.priv` | Yes |
| `_assert_no_priv` on release | Yes (public RUST-IN-PRIVACY packaging + legacy `build_release_0.2.3.py` gates) |
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

**Public product v1.0.0** (RUST-IN-PRIVACY installers + status-page catalog) and the **private operator tree** are consistent on core privacy promises: no-log node path, title-only public status, device keys, residual honesty, product DATA traffic shaping / outer obfuscation / PFS on residual engines, Settings transparency + licence gate + threat-model education, and operator FDE/ephemeral rebuild tooling — without over-claiming DPI-undetectability or multi-hop residual. Production node at **82.221.101.241:44044** remains the Python deploy path unless intentionally cut over to Rust `rpt-node`. Multi-hop remains **honest** (config / entry-only). Remaining Medium items are privilege/environment and incomplete traffic-analysis resistance — not silent product dishonesty.

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
| LUKS/dm-crypt FDE + shutdown wipe scripts | **In tree** (`install_disk_encryption.sh`, `install_shutdown_wipe.sh`; at-rest only; not live root secrecy) |
| Ephemeral / short-lived node rebuild | **In tree** (`scripts/ephemeral_node.py`, timer install; dry-run default; periodic snapshot/rebuild plan) |

---

## 11. Document control

| Item | |
|------|--|
| Output | `AUDIT.md` (repo root) |
| Related | `PRIVACY_POLICY.md` (Threat model), `README.md` (Threat model), RUST-IN-PRIVACY `AUDIT.md` / `RELEASE_NOTES_1.0.0.md` |
| Code baseline | Public **v1.0.0** packages + private tree (may still label `client/VERSION` 0.2.3) + node **82.221.101.241** |
| Pass date | **21 July 2026** (docs + dual-repo security pass) |
| Threat scenarios | §4.6 — re-review on each major release |
