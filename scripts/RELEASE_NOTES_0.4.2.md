# Release 0.4.2

## Catalog
- Product monopin **0.4.2** (client/VERSION, status downloads, Flutter pubspec / RptConfig)
- **Settings pre-adjustment defaults (lean residual):** run at startup **off**, autoconnect on launch **off**, residual VPN core **always on**, traffic shaping **off**, outer obfuscation **off**, multi-hop **off**
- Monthly **£2.45** / yearly GBP anchors unchanged (local-currency display + Stripe USD presentment fallback)
- **Browser extension (MV3):** `browser_extension/` + release asset `restore-privacy-browser-extension-0.4.2.zip` — **browser-scoped** Connect/Disconnect via `chrome.proxy` (local SOCKS path). **Not** OS residual TUN / Packet Tunnel / Wintun; native paid clients remain the system residual product. Load unpacked in Chromium-class browsers (and custom browsers that support MV3).

## Incomplete platform builds (breadcrumb)
This operator host is **macOS (Darwin)**. Honesty table for **0.4.2** freezes:

| Platform | 0.4.2 status |
|----------|----------------|
| **Linux** | Rebuilt via `scripts/package_linux.py` / `build_release_0.4.2.py` when tooling present on this host |
| **Android** | **Not fully Flutter-frozen here** unless Android SDK present — residual-wire APK may be **carry-forward** from 0.4.1 with 0.4.2 filename pin only |
| **macOS** | Flutter + DevID/notarize when signing secrets present; otherwise carry-forward / omit with this note |
| **iOS** | Flutter + Team-signed sideload when secrets present; otherwise carry-forward / omit with this note |
| **Windows** | **Not fully PE-frozen on Darwin** — build on **Windows x64**: `python scripts/build_windows_multihop.py` or `scripts\build_windows_multihop.bat` (see `client/windows/WINDOWS_HANDOFF_0.4.2.md`, pin `client/VERSION` → 0.4.2). Carry-forward SFX pin rewrite only on Darwin is **not** a native multihop PE rebuild. |

Never claim multihop residual PE or notarized Apple packages that this host did not produce.

## Operator
```bash
python scripts/build_release_0.4.2.py
gh release create 0.4.2 releases/0.4.2/* --title "0.4.2" --notes-file scripts/RELEASE_NOTES_0.4.2.md
python scripts/host_paid_assets_vps.py --stage   # then --upload when SSH works
```

## Build provenance (this ship)

| Asset | Provenance |
|-------|------------|
| macOS zip | Fresh Flutter freeze + DevID + notary (Accepted); CFBundle pin **0.4.2** |
| iOS zip | Fresh Flutter freeze + Team-signed sideload; marketing pin **0.4.2** |
| Linux tar.gz | Rebuilt via package_linux.py (0.4.2) |
| Android APK | **Carry-forward** residual-wire APK from 0.4.1 filename rewrite — not a full Flutter APK rebuild on this host |
| Windows setup.exe | **Carry-forward** from 0.4.1 PE (SFX pin rewrite failed/not applied on Darwin) — **full multihop PE requires Windows x64** (`scripts/build_windows_multihop.py`) |
| Browser extension zip | MV3 package from `browser_extension/` (proxy Connect/Disconnect; browser-scope only) |
