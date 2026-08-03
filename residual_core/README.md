# residual_core (C++)

Portable **residual protocol core** for Restore Privacy. Hybrid product:

| Layer | Language | Role |
|-------|----------|------|
| UI / entry / settings | Flutter `client_app/` | Multi-platform shell |
| Residual crypto + wire helpers | **this C++ library** | Pure offline primitives |

This is the **start** of the C++ residual path (not a full Python/`NativePrep` port).

## Build & test

From monorepo root:

```bash
cmake -S residual_core -B residual_core/build && cmake --build residual_core/build
./residual_core/build/residual_core_tests
```

## Shipped pure functions

- `derive_pfs_session_shared` — parity with `node/pfs.py` (SHA-256 transcript + `|pfs-x25519|`)
- `derive_session_key` — HKDF-SHA256, info `rpt-v2-session` (parity `node/crypto_session.py`)
- `x25519_shared` / public-from-private — RFC 7748 + product PFS path
- `chacha20_poly1305_seal` / `open` — product residual session AEAD (12-byte nonce)
- `pack_keepalive` / `peek_type` — bare `RPT2` frames (parity `node/protocol.py`)
- `lean_residual.hpp` — product lean defaults (shape / outer obfs / multihop **off**)
- C ABI in `include/residual_core/residual_core.h` (PFS, keepalive, AEAD seal/open, lean defaults)

No sockets, no Flutter, no geo gate — unit-testable offline.

## Continuing rule (hybrid product)

| Do | Do not |
|----|--------|
| Expand **pure residual crypto/wire** in C++ here | Full rewrite of residual **nodes** in C++ now |
| Keep Flutter as **UI + MethodChannel bridge only** | Own residual IP AEAD / UDP dataplane in Dart |
| Keep privacy-scale layers **default-off** (low ping) | Turn shape/obfs/multihop on by default for “more privacy” |
| Prefer residual UDP **44044** for residual RTT honesty | Fake lower RTT with shorter HELLO timeouts |

## Architecture direction

See **[docs/VPN_ARCHITECTURE_C_PLUS_PLUS.md](docs/VPN_ARCHITECTURE_C_PLUS_PLUS.md)** for:

- X25519 + ChaCha20-Poly1305 vs product Python/Swift residual
- Flutter residual channel / FFI boundaries (**no packet-through-Dart**)
- Leak mitigation vs low-ping profiles
- Recommendation: **do not** full-rewrite nodes in C++ yet; share crypto core first

## Future (engineering)

- Host-side link of this lib from native residual process / Packet Tunnel
- Optional Flutter FFI only when a real call site needs it
