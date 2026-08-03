# VPN architecture exploration: C++ residual crypto, Flutter FFI, leak vs latency

**Audience:** implementers and future goals (not public marketing).  
**Status:** decision-ready architecture direction (analysis).  
**Date context:** monorepo hybrid after `residual_core` scaffold (PFS IKM + HKDF + RPT2 keepalive).  
**Non-claims:** this document does **not** claim a fully rewritten C++ node, full live Connect from C++, or zero traffic-analysis risk.

---


## 0. Continuing implementer rule (this monorepo)

**C++ residual_core** owns pure residual crypto and wire helpers. **Flutter** owns UI and
`MethodChannel('restore_privacy/vpn')` bridge only — **no residual IP AEAD / UDP
dataplane in Dart**. **Do not** full-rewrite residual nodes (`node/server.py`) into C++
in this phase. **Lean residual defaults** (traffic shape / outer obfuscation / multi-hop
**off**) keep client CPU and hop cost low for product single-hop Connect; privacy-scale
layers stay user opt-in. Residual UDP **44044** is the product residual port for RTT honesty.

---
## 1. Current product residual stack (ground truth)

| Layer | Location | Role today |
|-------|----------|------------|
| Flutter UI shell | `client_app/lib/` — `main.dart`, Settings, entry | Product chrome; Connect UX |
| Flutter residual bridge | `client_app/lib/vpn_controller.dart` | `MethodChannel('restore_privacy/vpn')` → prepare/connect/disconnect/status/privacy scale |
| Desktop residual (Python) | `client/connect.py`, `client/dataplane.py`, `client/full_tunnel.py` | HELLO, session, TUN dataplane, IPv4/IPv6 residual policy |
| Protocol + crypto (Python) | `node/protocol.py`, `node/pfs.py`, `node/crypto_session.py`, `node/handshake.py` | RPT2 frames, eph X25519 PFS, HKDF, ChaCha20-Poly1305 AEAD |
| Residual nodes (Python) | `node/server.py`, `node/sessions.py`, admission/payment gates | UDP residual admit + session AEAD |
| Apple residual engine | `client_app/apple_shared/Rpt2/` (Swift CryptoKit) | Packet Tunnel path: X25519 PFS, ChaChaPoly, HELLO parity |
| Apple NE host | `client_app/macos/NativePrep/PacketTunnelProvider.swift` (and iOS twin) | OS residual capture |
| C++ residual core | `residual_core/` | **Shipped pure:** PFS IKM + HKDF, X25519, ChaCha20-Poly1305, keepalive/frames, lean residual defaults; C ABI for future host/FFI |

**Product residual truth (must not be regressed):**

- Connect is cryptographic admission (device key + node pubs) — **no geo gate**.
- Session AEAD keys prefer **ephemeral X25519** mixed as `|pfs-x25519|` into SHA-256 IKM (`node/pfs.py`), then **HKDF-SHA256** info `rpt-v2-session` (`node/crypto_session.py`).
- Wire: bare **RPT2** by default; outer obfs / traffic shape are **optional** privacy-scale layers.
- Catalog residual peers **IS + DE** only; multihop residual-via-exit is **opt-in**.

---

## 2. X25519 ephemeral exchange

### 2.1 What product does today

| Implementation | Mechanism |
|----------------|-----------|
| Python | `cryptography` `X25519PrivateKey` / `exchange` in `node/pfs.py` (`EphemeralX25519`, `x25519_shared_secret`) |
| Swift (Apple) | CryptoKit Curve25519 in `RptClientEngine` / HELLO build-parse |
| C++ `residual_core` | **X25519 DH + PFS IKM** shipped (`x25519.hpp` / RFC 7748 goldens + product PFS) |

Client HELLO embeds client eph public; SERVER_HELLO opening includes server eph public when PFS is required (`client/connect.py` `require_pfs=True` product default).

### 2.2 Possibilities for C++

| Option | Pros | Cons |
|--------|------|------|
| **A. Link OpenSSL/BoringSSL** `X25519_*` | Battle-tested, FIPS options on BoringSSL | Extra dependency; packaging per platform |
| **B. libsodium** `crypto_scalarmult_curve25519` | Clean API, widely used in VPN space | Another dep; build scripts |
| **C. Pure portable Curve25519** (tweetnacl-class) | No external crypto for mobile static link | Review burden; slower if not careful |
| **D. Platform APIs** (CNG Windows, SecKey Apple) via thin wrappers | OS-maintained | Fragmented code paths |

### 2.3 Recommendation

**Phased C++:**

1. **Implement X25519 generate + shared secret in `residual_core`** behind a small interface (`X25519KeyPair`, `shared_secret(priv, peer_pub32)`), defaulting to **OpenSSL 3** (or LibreSSL on Apple) with a CMake `find_package(OpenSSL)` option and a documented fallback pure implementation for offline unit tests with fixed test vectors.
2. Keep **golden vectors** against Python `x25519_shared_secret` + existing `derive_pfs_session_shared` (already tested).
3. Do **not** invent a new handshake: wire layout stays RPT2 HELLO as in `node/handshake.py` / Swift engine.

**Leak impact:** real eph DH is what makes PFS meaningful (long-term key compromise ≠ past session AEAD). Already product law on Python/Swift paths; C++ must match before it owns session keys.

**Latency impact:** one X25519 per connect is **sub-ms** on modern CPUs — not a ping bottleneck vs RTT to IS/DE.

---

## 3. ChaCha20-Poly1305 AEAD

### 3.1 What product does today

| Implementation | Mechanism |
|----------------|-----------|
| Python | `ChaCha20Poly1305` seal/open in `node/crypto_session.py` (session data + hybrid blob AAD `RPT2-HYBRID` / `RPT2-SERVER-HELLO` + session_id) |
| Swift | `CryptoKit.ChaChaPoly` in `RptSessionCrypto.swift` |
| C++ | **Shipped** `chacha20_poly1305_seal` / `open` + C ABI |

Dataplane path (`client/dataplane.py`) seals IP packets and optional cover frames through `SessionCrypto`, with traffic-shape padding applied **around** AEAD (not instead of it).

### 3.2 Possibilities for C++

| Option | Notes |
|--------|--------|
| OpenSSL EVP ChaCha20-Poly1305 | Natural pair with OpenSSL X25519 |
| libsodium `crypto_aead_chacha20poly1305_ietf` | IETF nonce=12 layout matches product 12-byte nonces |
| Platform (Windows BCrypt, Apple CryptoKit via C++ interop) | Avoid for core hot path — keep pure C++ for shared lib |

### 3.3 Recommendation

1. Add `SessionCrypto::seal` / `open` to `residual_core` with **fixed 12-byte nonce**, 32-byte key, AAD pass-through — parity tests vs Python for empty/small payloads and known nonces (test-only fixed nonces).
2. Cover-frame / pad policy remains a **policy layer** (optional); default product is lean residual (shape **off**) so AEAD seal of raw IP is the hot path.
3. Never “AEAD off for speed” — residual confidentiality is non-negotiable; speed comes from **not** enabling pad/cover/jitter by default.

**Latency:** ChaCha20-Poly1305 is software-fast and often comparable to AES-GCM without AES-NI dependency; it is the right AEAD for residual UDP on mixed platforms.

---

## 4. FFI into Flutter residual channel

### 4.1 Current bridge (do not throw away)

```
Flutter UI
  └─ VpnController  MethodChannel 'restore_privacy/vpn'
        ├─ prepareVpn / connect / disconnect / status
        ├─ setResidualStack / setPrivacyScale
        └─ (removed) host→Flutter UPDATE_PUSH
              │
              ▼
Native host (per OS)
  ├─ Android VpnService + residual engine hooks
  ├─ Windows plugin / tunnel
  ├─ Apple PacketTunnel + Rpt2 Swift engine
  └─ (desktop Python residual in some builds)
```

Channel name and methods are **product API surface** used by Settings privacy scale and Connect honesty (`residualCapture`, IPv6 flags).

### 4.2 FFI options

| Path | Fit | Notes |
|------|-----|--------|
| **dart:ffi** → `libresidual_core` | Best for pure crypto + frame encode | Load dynamic lib or static via plugin; no MethodChannel overhead for crypto |
| **MethodChannel** only | Already used for OS VPN lifecycle | Keep for prepare/connect/status; **do not** push every packet through Dart |
| **ffigen / pigeon** | Ergonomics | Generate bindings from `residual_core.h` |
| **Rewrite residual in Dart** | Poor | Slower crypto; duplicates Swift/Python |

### 4.3 Recommended architecture for residual data plane

```
┌─────────────────────────────────────────────────────────────┐
│ Flutter (UI only on hot path): Connect button, status,      │
│ privacy scale prefs, licence/KEYGEN entry                     │
└───────────────────────────┬─────────────────────────────────┘
                            │ MethodChannel: connect/disconnect/status
                            │ dart:ffi (optional): key derive / frame unit tests
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Native residual process / NE                                │
│  - Owns UDP socket + TUN                                    │
│  - Links residual_core (X25519, HKDF, ChaCha20-Poly1305)    │
│  - Apple: PacketTunnel may call C++ via bridging C ABI      │
│  - Desktop: replace Python seal/HELLO gradually             │
└─────────────────────────────────────────────────────────────┘
```

**Hard rule for low ping and low leak:**

- **Packets never cross the Flutter isolate** for encrypt/decrypt.
- Flutter only configures policy and displays residual honesty (`residual_ip_capture`).
- C++ (or Swift calling C++) runs **inside** the tunnel process.

### 4.4 Practical FFI increments

1. **Now (safe):** expand `residual_core` + C ABI; unit tests only (no product Connect change).
2. **Next:** desktop native plugin links `libresidual_core` for HELLO key derivation / DATA seal (parity suite vs Python).
3. **Then:** Apple residual: optional C++ core behind Swift PacketTunnel (CryptoKit can remain until C++ proven).
4. **Avoid:** “FFI every keepalive from Dart” — that adds jitter and GC pressure.

---

## 5. Leak mitigation vs low ping (architecture balance)

### 5.1 Leak classes and product levers (in tree)

| Leak class | Product control | Default | Latency cost |
|------------|-----------------|---------|--------------|
| Cleartext residual IP (not full tunnel) | Residual capture honesty; dual /1 IPv4 | On when Connected | Baseline |
| IPv6 ISP bypass | IPv6 residual block | On (product residual) | Negligible |
| DNS leak | Tunnel-only DNS (`10.88.0.1` family) | On while residual up | Low if DoT not forced globally |
| Kill-switch (block all on drop) | `RPT_KILL_SWITCH` / Settings | **Off** (scoped allows) | Can hurt UX; enable for paranoid |
| Protocol fingerprint | Outer obfs (QUIC-like) | **Off** lean residual | Small CPU; rarely RTT |
| Traffic analysis volume | Traffic shape / cover / pad | **Off** | **Adds RTT feel** (jitter/cover) |
| Path attribution | Multihop residual-via-exit | **Opt-in** | **Adds ~exit RTT** (entry+exit) |

Sources: `client/full_tunnel.py`, `client/privacy_live.py`, `client_app/lib/transparency_copy.dart`, `node/obfuscation.py`, `node/traffic_shape.py`, multihop residual-via-exit honesty in audit docs.

### 5.2 Architecture principle: two profiles

**Profile L — Low latency (product default residual):**

- Single-hop preferred entry (DE default catalog).
- PFS X25519 + ChaCha20-Poly1305 always on.
- IPv4 residual capture + IPv6 block + tunnel DNS.
- Obfs off, shape off, multihop off.
- Kill-switch off unless user opts in.

**Profile H — High privacy scale (user Settings):**

- Same crypto.
- Optionally: outer obfs, traffic shape, multihop residual-via-exit.
- Expect higher p50/p95 latency; never claim “same ping as L”.

### 5.3 Measurement methodology (do not invent SLAs)

- Probe **entry** and **exit** monopin RTT from operator hosts (`docs/PING_LATENCY_ADVICE.md`, audit privacy-scale tables).
- Client-side: log Connect → first residual DATA RTT separately from HELLO handshake time.
- Any C++ dataplane claim must beat or match Python/Swift on **same path**, same profile L.

### 5.4 Leak-tight hot path checklist (implementation target)

1. Residual capture up ⇒ public IP is residual peer (honest status if not).
2. No plaintext RPT session keys outside process memory; eph keys wiped after derive where feasible.
3. No dual-stack bypass (IPv6) while residual Connected with IPv6 residual ON.
4. DNS only via tunnel DNS while residual up.
5. Optional layers never silently disable residual capture.

---

## 6. Should residual **nodes** be rewritten in C++?

### 6.1 What a node must do

- UDP admit CLIENT_HELLO (ElGamal/Pedersen/device Ed25519 + optional PQ hybrid).
- Issue SERVER_HELLO, session AEAD, DATA/KEEPALIVE, optional NODE_STATUS (UPDATE_PUSH product path removed — manual client update).
- Payment/device-trial gates, nolog posture, wipe/rebuild ops, fleet sequencing.
- Co-joined roles (VPN + other services) on some hosts.

Python today: `node/server.py` + modules under `node/`. Operational scripts and fleet wipe are Python-heavy.

### 6.2 Options

| Option | Verdict |
|--------|---------|
| **Full C++ node rewrite now** | **Not appropriate** as a single goal — multi-quarter parity risk (payment gate, wipe, co-join, observability). Dual-stack bugs leak users. |
| **Shared C++ crypto/frame library in node + clients** | **Yes** — single source of seal/open/X25519/HELLO framing; Python/Swift call into it. |
| **C++ “fast path” worker** (UDP DATA only) behind Python admit | Possible later; complexity high (session state handoff). |
| **Keep Python node indefinitely** | Acceptable if crypto moves to C++ and performance of HELLO is fine (HELLO is rare vs DATA). |

### 6.3 Decision (decision-ready)

**Do not fully rewrite residual nodes in C++ in the next engineering milestone.**

**Do** pursue a **phased shared-core** plan:

| Phase | Deliverable | Node impact |
|-------|-------------|-------------|
| **P0** (done/start) | `residual_core` PFS IKM + HKDF + keepalive | Tests only |
| **P1** | X25519 + ChaCha20-Poly1305 in `residual_core` + goldens vs Python/Swift | Node still Python; optional ctypes/cffi experiment for seal |
| **P2** | Desktop client residual process links C++ for HELLO+DATA | Node remains Python |
| **P3** | Apple PacketTunnel optionally links C++ core | Swift NE shell stays |
| **P4** | Evaluate C++ node only if P1–P3 prove parity **and** profiling shows Python DATA path is a bottleneck | Separate goal; never “big bang” cutover |

**Risks of dual-stack:** two AEAD implementations must match bit-for-bit on nonces/AAD/padding; continuous interop tests (Python client ↔ C++ “node mock”, Swift ↔ C++) are mandatory before production cutover.

**Latency note:** for residual **nodes**, RTT is dominated by **network path and fleet location** (IS/DE), not Python crypto for AEAD. Node rewrite is a **reliability/ops** play more than a ping play. Client-side C++ helps **mobile/desktop consistency** and reduces Python from the user device hot path.

---

## 7. Recommended next engineering increments (ordered)

1. **`residual_core` P1 crypto**
   - X25519 generate/exchange + unit vectors vs Python.
   - ChaCha20-Poly1305 seal/open + vectors vs Python (fixed nonce tests).
2. **Interop harness (Python)**
   - Generate HELLO/session fixtures in Python; consume in C++ tests (and reverse).
3. **Desktop residual host**
   - Link `libresidual_core` into the process that already owns TUN/UDP (not Flutter isolate).
4. **Flutter**
   - Keep `MethodChannel('restore_privacy/vpn')` for lifecycle.
   - Optional `dart:ffi` only for diagnostics / developer tools, not dataplane.
5. **Apple**
   - Bridge C ABI into PacketTunnel when desktop parity is green; do not delete Swift Rpt2 until dual-run comparison passes.
6. **Node C++**
   - Defer full rewrite; optional shared library for seal/open inside Python via cffi **after** client P1.

### Explicitly **not** proposed by this exploration

- Claiming residual nodes are already rewritten in C++.
- Shipping multi-hop + shape + obfs **on by default** (destroys low-ping product default).
- Routing residual packets through Flutter for “simplicity.”
- Perfect anonymity or zero traffic-analysis risk.

---

## 8. Mapping to existing residual_core

| Capability | Status in `residual_core` | Next |
|------------|---------------------------|------|
| PFS IKM `\|pfs-x25519\|` | Implemented + tested | Keep |
| HKDF session key | Implemented + tested | Keep |
| RPT2 keepalive | Implemented + tested | Expand DATA/HELLO packers |
| X25519 DH | Missing | P1 |
| ChaCha20-Poly1305 | Missing | P1 |
| C ABI | Partial (`residual_core.h`) | Grow with crypto |
| Flutter FFI | Not wired | After P1, host-side first |
| Node rewrite | Not started | Defer (see §6) |

Build/test (baseline):

```bash
cmake -S residual_core -B residual_core/build && cmake --build residual_core/build
./residual_core/build/residual_core_tests
```

---

## 9. Summary recommendation

| Question | Answer |
|----------|--------|
| Use X25519 in C++? | **Yes** — next crypto milestone; match product PFS. |
| Use ChaCha20-Poly1305 in C++? | **Yes** — session AEAD parity with Python/Swift. |
| FFI into Flutter residual channel? | **Lifecycle via MethodChannel; crypto/dataplane in native process linking C++.** Not packet-through-Dart. |
| Leak vs ping? | **Default lean residual (L)**; optional privacy scale (H). Always residual capture honesty + IPv6/DNS. |
| Rewrite nodes in C++? | **Not full rewrite now.** Shared C++ crypto core first; Python node remains until proven need. |

This is the VPN architecture direction: **one portable C++ residual core**, **OS-native tunnel hosts**, **Flutter UI only**, **privacy-scale layers opt-in**, **node rewrite deferred and phased**.
