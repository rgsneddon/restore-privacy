# Mac / iOS handoff for Restore Privacy **0.1.7**

This Windows host staged the release zips and ships current Flutter + NativePrep source in the git repo. **Team signing, Packet Tunnel entitlements, and notarization must be completed on a Mac.**

## Whatâ€™s in this folder

| File | Notes |
|------|--------|
| `restore-privacy-client-0.1.7-macos.zip` | Staged package for Mac work (may be prior-build payload renamed for catalog continuity) |
| `restore-privacy-client-0.1.7-ios.zip` | Staged sideload package (same) |
| `SHA256SUMS.json` / `manifest.json` | Hashes and sizes |

**Fresh source of truth for Apple work:** git clone `main` (tag `0.1.7`) and open:

- `client_app/` â€” Flutter app (shared UI, Settings, Connect/Disconnect)
- `client_app/apple_shared/Rpt2/` â€” shared Swift RPT stack
- `client_app/ios/` + `client_app/macos/` â€” Xcode projects, Packet Tunnel targets, NativePrep

## On your Mac

```bash
git clone https://github.com/rgsneddon/restore-privacy.git
cd restore-privacy
git checkout 0.1.7   # or main after release
cd client_app
flutter pub get
# macOS
flutter build macos --release
# then sign/notarize:
python3 ../scripts/sign_and_notarize_macos.py --app build/macos/Build/Products/Release/restore_privacy_client.app
# iOS (device / sideload)
flutter build ios --no-codesign
# open ios/Runner.xcworkspace in Xcode for Team + Packet Tunnel entitlements
```

## Docs

- [`client_app/APPLE_BUILD.md`](../../client_app/APPLE_BUILD.md)
- [`client_app/macos/BUILD_ON_MAC.md`](../../client_app/macos/BUILD_ON_MAC.md)
- [`client_app/ios/BUILD_ON_MAC.md`](../../client_app/ios/BUILD_ON_MAC.md)

## Secrets (never commit priv)

- Ship **only** `node_elgamal.pub` in packages when needed.
- Device Ed25519 is generated on first run.
- Never ship `node_elgamal.priv` or a shared `client_ed25519.priv`.

## Product behaviour to preserve on Apple

- Manual Connect / Disconnect by default  
- Settings opt-in: run at startup + autoconnect on launch (defaults off)  
- Residual public IP only when Packet Tunnel is active (honest status)  
- Minimize/background should not stop the tunnel until Disconnect  
