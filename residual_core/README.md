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
- `pack_keepalive` / `peek_type` — bare `RPT2` frames (parity `node/protocol.py`)
- C ABI in `include/residual_core/residual_core.h` for future Flutter FFI

No sockets, no Flutter, no geo gate — unit-testable offline.

## Architecture direction

See **[docs/VPN_ARCHITECTURE_C_PLUS_PLUS.md](docs/VPN_ARCHITECTURE_C_PLUS_PLUS.md)** for:

- X25519 + ChaCha20-Poly1305 roadmap vs product Python/Swift residual
- Flutter residual channel / FFI boundaries (no packet-through-Dart)
- Leak mitigation vs low-ping profiles
- Recommendation: **do not** full-rewrite nodes in C++ yet; share crypto core first

## Future (engineering)

- X25519 exchange (OpenSSL/libsodium) for full eph DH
- ChaCha20-Poly1305 seal/open path
- Host-side link from native residual process; optional Flutter FFI later
