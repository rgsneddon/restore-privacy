# Apple handoff — Restore Privacy **0.5.5**

**Monopin / this build:** `0.5.5`

## Settings (all platforms)
Residual **IPv4** / **IPv6** switches are at the **top** of Settings → privacy scale
(with explainers / hover tooltips). Defaults ON. Honest residual attach when either
toggle is off.

## Mac rebuild

```bash
cd client_app
flutter build macos --release
flutter build ios --release --no-codesign
cd ..
python3 scripts/build_release_0.5.5.py --apple-only
```

CFBundleShortVersionString must equal **0.5.5**. Refuse carry-forward renames.
