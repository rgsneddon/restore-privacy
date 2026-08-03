# Residual leak hardening exploration and Settings honesty design

**Audience:** implementers (not public marketing).  
**Goal:** inventory data-leakage mitigations for residual VPN; design how **Settings** can show **minimal** residual risk when protections are on—**without** claiming absolute zero leakage for all threat models.  
**Related:** `residual_core/docs/VPN_ARCHITECTURE_C_PLUS_PLUS.md`, `client_app/lib/leak_test.dart`, `client_app/lib/transparency_copy.dart`, `client/leak_protection.py`, `client/full_tunnel.py`.

---

## 0. Product law: “zero” vs “minimal non-risk”

| Language | Allowed? | Why |
|----------|----------|-----|
| Absolute **“zero data leakage in all cases”** | **No** | Traffic analysis, OEM dual-stack bugs, browser WebRTC before residual up, operator path, and DPI fingerprinting cannot be mathematically eliminated. Product already disclaims multihop-as-perfect and DPI-undetectability. |
| **“Minimal residual risk (this session)”** / **“Leak test: PASS — residual path protected”** | **Yes** | Matches shipped leak-test PASS criteria when residual capture, tunnel DNS, IPv6 protection, and matching egress probe all hold. |
| **“Non-risk residual IP / DNS for ordinary browsing under Profile L”** | **Yes, with scope** | Ordinary ISP IP and public-DNS leaks are what residual is designed to stop when Connected and PASS. |

**Settings design tension (OBJECTIVE):** users want to *see* leakage near zero. **Resolution:** show a **session posture score** grounded in live residual flags + leak-test PASS, labelled **“Minimal residual leak risk (session)”**, with an expandable honesty note that residual is not a guarantee against all adversaries.

---

## 1. Leak inventory: shipped vs gaps vs possible additions

### 1.1 Residual public IP (IPv4) capture

| Item | Detail |
|------|--------|
| **Threat** | OS traffic uses ISP public IPv4 instead of residual node. |
| **Shipped** | Full-tunnel IPv4 dual `/1` residual capture; honesty flags `residualCapture` / status not “Connected” without capture (`client/full_tunnel.py`, `connect_status`, Apple residual honesty). Leak test fails if `residualCaptureActive` is false (`client_app/lib/leak_test.dart`). |
| **Gaps** | Brief race on connect/disconnect; OS-specific route fights; captive portals. |
| **Possible additions** | Continuous residual-IP watchdog while Connected; auto-reconnect on capture drop; Settings “last verified residual IP” timestamp. |

### 1.2 IPv6 ISP bypass

| Item | Detail |
|------|--------|
| **Threat** | Dual-stack devices leak identity over IPv6 while IPv4 is residual. |
| **Shipped** | Residual IPv6 protection default **ON** (`settings_store` `residual_ipv6`); leak test requires `ipv6Protected` for full **PASS**. Transparency copy explains OFF risks (`transparency_copy.dart`). |
| **Gaps** | OEM stacks that ignore blocks; IPv6 OFF user choice. |
| **Possible additions** | Hard-fail Connect if IPv6 residual ON but OS did not apply block; periodic IPv6 egress probe in leak test; Settings badge “IPv6 residual: protected”. |

### 1.3 DNS leakage

| Item | Detail |
|------|--------|
| **Threat** | Queries to 1.1.1.1 / 8.8.8.8 / ISP resolver reveal browsing. |
| **Shipped** | Tunnel-gateway-only DNS plan (`client/leak_protection.py` `product_dns_servers`, public DNS blocklist); leak test requires `dnsTunnelGatewayOnly` and empty `publicDnsViolations`. |
| **Gaps** | Apps with hardcoded DoH/DoT to public resolvers; Android Private DNS “Automatic” edge cases. |
| **Possible additions** | Detect system Private DNS conflicting with residual; optional block of known public DoH IPs while residual up; Settings “DNS: tunnel only ✓”. |

### 1.4 Kill-switch / fail-closed egress

| Item | Detail |
|------|--------|
| **Threat** | On residual drop, traffic fails open to ISP. |
| **Shipped** | Kill-switch **parked / product default OFF** (`client/kill_switch.py` documents always-false product gate). Scoped allows preferred over global block. |
| **Gaps** | No user-facing “block internet if residual dies” in Settings for product residual. |
| **Possible additions** | Opt-in kill-switch Settings control (honest “may break captive portals / updates”); status “fail-closed armed”. Tradeoff: UX pain vs leak on disconnect. |

### 1.5 Traffic shape / outer obfuscation

| Item | Detail |
|------|--------|
| **Threat** | Plain RPT UDP fingerprint; volume analysis. |
| **Shipped** | Privacy scale toggles default **OFF** (lean residual): `privacy_traffic_shape`, `privacy_outer_obfuscation` (`residual_privacy_policy.dart`). When ON: pad/cover/jitter and QUIC-mimic wrap. |
| **Gaps** | Not DPI-proof; shape adds latency. |
| **Possible additions** | Settings: show whether shape/obfs active in posture row; recommend ON only for restricted networks; never claim “undetectable”. |

### 1.6 Multihop path privacy

| Item | Detail |
|------|--------|
| **Threat** | Entry node sees residual ingress; single-hop ties entry to user more tightly. |
| **Shipped** | Multihop residual-via-exit **opt-in** (`privacy_multihop`); exit Germany; honesty: not full onion encapsulation (`leak_test` disclaimer). |
| **Gaps** | Latency; not perfect path privacy. |
| **Possible additions** | Posture: “Path: single-hop DE” vs “Path: residual-via-exit”; never “anonymous network”. |

### 1.7 WebRTC / local-app / LAN bypass

| Item | Detail |
|------|--------|
| **Threat** | Browser STUN/WebRTC learns host public IP; mDNS/LAN apps bypass tunnel. |
| **Shipped** | Documented in `leak_protection.py` (WebRTC limited); KS STUN/mDNS blocks **parked**. Leak test does not claim WebRTC-proof. |
| **Gaps** | No in-app WebRTC block on all platforms. |
| **Possible additions** | Settings guidance link “disable WebRTC in browser”; optional platform STUN block when KS un-parked; leak-test note “browser WebRTC not covered”. |

### 1.8 Device-local logging / phones-home

| Item | Detail |
|------|--------|
| **Threat** | Client or node logs user activity; status host learns identity. |
| **Shipped** | Connect no-phones-home residual path (product audit); title-only public status; local connection log is **on-device** Settings feature; node nolog posture in node scripts. |
| **Gaps** | Local log still stores Connect events if user enables; crash reports OS-level. |
| **Possible additions** | Settings “local log: off by default”; clear-log button; posture “no residual activity upload”. |

### 1.9 Time-of-day / session edge cases

| Item | Detail |
|------|--------|
| **Threat** | Pre-Connect and post-Disconnect windows use ISP. |
| **Shipped** | Status honesty when residual not fully up; autoconnect optional. |
| **Gaps** | Cannot protect traffic before Connect. |
| **Possible additions** | Clear Settings banner: “Protection applies only while Connected and residual capture is active.” |

### 1.10 Crypto / protocol (identity of residual path)

| Item | Detail |
|------|--------|
| **Threat** | Session keys recoverable; clear magic. |
| **Shipped** | PFS X25519 + ChaCha20-Poly1305 (Python/Swift); C++ core starting (`residual_core`). |
| **Gaps** | C++ not on all hosts yet. |
| **Possible additions** | Shared C++ AEAD (architecture doc); does not replace residual capture. |

---

## 2. What shipped leak test PASS already means

From `client_app/lib/leak_test.dart` (`runProductLeakTest` / product-honest evaluation):

**PASS only when all hold:**

1. Residual capture **active**  
2. Tunnel DNS only (no public DNS violations)  
3. IPv6 residual protection **confirmed**  
4. Live public-IP egress probe **ran**, **matched** residual path, not inconclusive  

**PARTIAL:** residual IPv4 looks good but IPv6/probe incomplete.  
**FAIL:** residual not active, or DNS/egress failed while residual claimed up.

This is the correct **technical backbone** for any Settings “minimal risk” indicator—not marketing inventing a new score.

---

## 3. Settings presentation design (honest “minimal leak”)

### 3.1 New Settings block (recommended): **Residual leak posture**

Place under existing privacy scale / leak test section in `settings_screen.dart` (near “Run leak test”).

**Headline (when Connected + last leak test PASS within N minutes):**

> **Residual leak risk: Minimal (this session)**  
> Residual IP capture, tunnel DNS, and IPv6 residual protection are active. Last leak test: PASS.

**Headline (Connected, no recent PASS):**

> **Residual leak risk: Unverified**  
> Connect is up; run Leak test to confirm residual IP and DNS.

**Headline (Not residual-protected):**

> **Residual leak risk: Unprotected**  
> Residual capture is not active — ISP path may be used.

**Forbidden UI copy:**

- “Zero leakage guaranteed”  
- “100% leak-proof”  
- “Invisible to all networks / DPI”

**Allowed honesty footnote (always visible, small text):**

> Minimal means ordinary residual IP and DNS leaks are mitigated for this session under product residual rules. It does **not** mean perfect anonymity, traffic-analysis resistance, or protection before Connect / after Disconnect. Optional privacy-scale layers (shape, outer obfuscation, multihop) trade speed for harder fingerprinting — not zero risk.

### 3.2 Checklist rows (live flags, not marketing)

| Row | Source | Green when |
|-----|--------|------------|
| Residual IPv4 capture | native status / residualCapture | true |
| IPv6 residual protection | ipv6Protected | true |
| Tunnel DNS only | dns plan + no public DNS | true |
| Kill-switch | product KS gate | “Off (default)” or “Armed” if un-parked |
| Privacy scale extras | shape/obfs/multihop | “Lean (default)” or list ON |
| Last leak test | store last verdict + time | PASS / PARTIAL / FAIL / never |

### 3.3 Mapping user desire (“zero”) to UI

| User expectation | Settings shows |
|------------------|----------------|
| “My real IP is hidden while Connected” | Residual capture + PASS leak test |
| “DNS not to Google/Cloudflare” | Tunnel DNS row green |
| “No IPv6 sneak path” | IPv6 residual green |
| “Nothing can ever leak” | Explicitly **not** promised; footnote |

---

## 4. Additional hardening methods worth exploring (beyond UI)

Ordered by **real leak reduction** for typical users:

1. **Session residual watchdog** — re-check capture + IPv6 + DNS every N seconds while Connected; surface drop immediately.  
2. **Stricter Connect readiness** — refuse “Connected” UI until residualCapture && (ipv6 protected if residual IPv6 ON). Already partly honesty-driven; tighten if gaps remain.  
3. **Private DNS / DoH conflict detection** — warn in Settings when OS Private DNS may bypass tunnel.  
4. **Opt-in kill-switch** — un-park product gate carefully; Windows profile DefaultOutboundAction design already documented.  
5. **WebRTC / STUN guidance + optional blocks** when KS path returns.  
6. **Local log default off** + clear button for minimal device-local residue.  
7. **C++ shared AEAD/X25519** — consistency/security hygiene, not a substitute for capture.  
8. **Browser extension residual note** — browser_extension is not OS residual TUN; Settings should not imply it replaces residual (already product map honesty).

**Lower priority for “minimal risk” badge (high latency / incomplete threat coverage):**

- Default-on multihop or traffic shape (hurts ping; still not traffic-analysis proof).  
- Claims of DPI invisibility.

---

## 5. Ordered next-engineering list

| # | Work | Real leak reduction vs UI-only |
|---|------|--------------------------------|
| 1 | **Settings Residual leak posture** panel: live flags + last leak-test verdict + honesty footnote | UI + drives re-test |
| 2 | Persist **last leak test result + timestamp**; show on Home when Connected | UI |
| 3 | **Watchdog** residualCapture/ipv6/dns while Connected | **Real** |
| 4 | **Private DNS / DoH conflict** warning | **Real** (guidance + detect) |
| 5 | Optional **kill-switch** Settings (product un-park) | **Real** (trade UX) |
| 6 | WebRTC/STUN guidance + optional KS STUN | **Real** (partial) |
| 7 | residual_core X25519 + ChaCha (crypto parity) | Security hygiene |
| 8 | Default-on multihop/shape | **Not recommended** for default minimal-risk + low ping |

---

## 6. Explicitly out of scope / cannot guarantee

- Perfect anonymity or “zero leakage” against all adversaries.  
- Full traffic-analysis resistance or DPI-undetectability.  
- Protection for traffic **before** residual Connect or **after** Disconnect.  
- All OEM dual-stack / enterprise MDM edge cases.  
- Browser WebRTC / app-hardcoded DoH without OS residual capture + app cooperation.  
- Multihop as full intermediate onion encapsulation (product residual-via-exit only).  
- No monopin ship / payment rule changes in this exploration.

---

## 7. Summary

| Question | Answer |
|----------|--------|
| Can Settings show “zero leak”? | Show **Minimal residual leak risk (this session)** only when residual capture + IPv6 residual + tunnel DNS + leak-test PASS; never absolute zero. |
| What already hardens users? | Residual IPv4 capture, IPv6 residual default on, tunnel DNS, honest status, opt-in privacy scale, product-honest leak test. |
| What to add first? | Posture panel + last PASS display + residual watchdog; then OS DNS conflict and optional kill-switch. |
| Kill-switch default? | Keep **off** for product residual unless user opts in (matches parked product gate). |

This is the leak-hardening direction: **measure and display real residual posture**, **expand technical mitigations that stop ordinary IP/DNS/IPv6 leaks**, and **refuse marketing zero**.
