# Release 0.4.1

## Catalog
- Product monopin **0.4.1** (client/VERSION, status downloads, Flutter pubspec)
- Monthly **£2.45** / yearly **£29.40** GBP anchors with **local-currency display** and Stripe USD presentment fallback
- Public site brand **RESTORE PRIVACY VPN**, neon panel borders, no lightweight tagline

## Node residual speed
- Larger UDP SO_RCVBUF/SO_SNDBUF (default 4 MiB) via `node/udp_fast_path.py`
- Multi-datagram drain per select wake (lower queue latency under load)
- Analysis: `docs/NODE_SPEED_0.4.1.md`

## Incomplete platform builds (breadcrumb)
This operator host is **macOS (Darwin)**. Full freezes:

| Platform | 0.4.1 status |
|----------|----------------|
| **Linux** | Build with `scripts/build_release_0.4.1.py` / package_linux on this host when tooling present |
| **Android** | Flutter APK when Android SDK present |
| **macOS** | Flutter + DevID/notarize when signing secrets present |
| **iOS** | Flutter + Team-signed sideload when secrets present |
| **Windows** | **Not fully PE-frozen on Darwin** — build on **Windows x64**: `python scripts/build_windows_multihop.py` or `scripts\build_windows_multihop.bat` (see `client/windows/WINDOWS_HANDOFF_0.4.0.md`, pin `client/VERSION` → 0.4.1). Carry-forward or omit until PE exists. |

Never claim multihop residual PE or notarized Apple packages that this host did not produce.

## Operator
```bash
python scripts/build_release_0.4.1.py
gh release create 0.4.1 releases/0.4.1/* --title "0.4.1" --notes-file scripts/RELEASE_NOTES_0.4.1.md
python scripts/host_paid_assets_vps.py --stage   # then --upload when SSH works
```

## Build provenance (this ship)

| Asset | Provenance |
|-------|------------|
| macOS zip | Fresh DevID sign + notary on Darwin (0.4.1) |
| iOS zip | Team re-sign package on Darwin (0.4.1) |
| Linux tar.gz | Rebuilt via package_linux.py (0.4.1) |
| Android APK | **Carry-forward** residual-wire APK from 0.4.0 filename rewrite — rebuild on host with Android SDK for native 0.4.1 Flutter freeze |
| Windows setup.exe | **Carry-forward** from 0.4.0 PE (SFX pin rewrite only on Darwin) — **full multihop PE requires Windows x64** (`scripts/build_windows_multihop.py`) |

