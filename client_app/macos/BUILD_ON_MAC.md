# macOS — build on MacBook

Flutter `macos/` scaffold is ready. Full-system VPN requires a **Packet Tunnel Network Extension** (and often a **System Extension** entitlement for production). Sign and notarize on Mac only.

## 1. Open and run

```bash
cd client_app
flutter pub get
flutter run -d macos
# release:
flutter build macos
open build/macos/Build/Products/Release/restore_privacy_client.app
```

Or:

```bash
open macos/Runner.xcworkspace
```

## 2. Signing & entitlements (Xcode)

1. **Runner** → **Signing & Capabilities** → your Team.  
2. Bundle id e.g. `com.yourorg.restoreprivacy.macos`.  
3. Add:
   - **Network Extensions** (Packet Tunnel)  
   - **App Groups** (share secrets with the extension)  
   - For production system-wide VPN: **System Extension** / Network Extension entitlement as required by current macOS versions  
4. Sample entitlement **comments** are in `macos/NativePrep/Runner.entitlements.example` — merge into `Runner/DebugProfile.entitlements` and `Runner/Release.entitlements` in Xcode (do not blindly replace sandbox settings without testing).

## 3. Packet Tunnel extension

1. **File → New → Target → Network Extension → Packet Tunnel Provider**.  
2. Name e.g. `PacketTunnel`.  
3. Add sources from `macos/NativePrep/`:
   - `PacketTunnelProvider.swift` → extension target  
   - `RptVpnChannel.swift` → Runner target  
   - `RptSecrets.swift` → shared / both as needed  
4. Register the Flutter method channel on app launch (see `RptVpnChannel.swift`).  
5. Extension must speak **RPT2** (same as Windows/Android). Outline: `ios/NativePrep/RPT_PROTOCOL.md` (shared).

Until the extension is wired, the channel returns a clear failure map so Flutter stays responsive.

## 4. Method channel contract

Identical to iOS / Android:

| | |
|--|--|
| Channel | `restore_privacy/vpn` |
| Methods | `connect`, `disconnect` |
| Args / results | See `lib/vpn_controller.dart` and `lib/connect_status.dart` |

Endpoint defaults: `lib/rpt_config.dart` → `104.156.224.47:44044`.

## 5. Secrets (required for connect)

The app looks for **both** of these (never `node_elgamal.priv`), in order:

1. `RPT_SECRETS_DIR` environment variable  
2. App Group `group.com.restoreprivacy.shared/secrets/` (when provisioned)  
3. Bundle `Contents/Resources/secrets/` (injected at package time, Android-style)  
4. `~/Library/Application Support/Restore Privacy/secrets/`  
5. **`~/.restore-privacy/secrets/`** (real login home; sandbox home-relative exception)

```bash
mkdir -p ~/.restore-privacy/secrets
# product client key + node public key only:
cp client_ed25519.priv node_elgamal.pub ~/.restore-privacy/secrets/
```

Or inject into the `.app` before signing/notarizing:

```bash
python3 scripts/inject_apple_secrets.py \
  --app client_app/build/macos/Build/Products/Release/restore_privacy_client.app
```

**Never** ship `node_elgamal.priv`.

## 6. Product behavior

Same Flutter UI and auto-connect as Windows/Android (`lib/main.dart`):

- Banner `#000080`, black background, white monospace text  
- Exact scrolling privacy string in `lib/theme.dart`  
- Full tunnel intent `0.0.0.0/0`  
- UK IP gate before tunnel attach  
- AppIcon under `Runner/Assets.xcassets/AppIcon.appiconset/`

## 7. Signing Packet Tunnel for system VPN

- Target already has `CODE_SIGN_ENTITLEMENTS = PacketTunnel/PacketTunnel.entitlements` (packet-tunnel + App Group + sandbox network).  
- Local builds use `CODE_SIGNING_ALLOWED = NO` when no NE profile is available so `flutter build macos` succeeds.  
- For real system VPN: enable Team, set `CODE_SIGNING_ALLOWED = YES`, embed `PacketTunnel.appex`, and grant Network Extension + App Groups in the Developer portal.

## 8. Gatekeeper / malware dialog (distribution)

Downloaded apps must use **Developer ID + notarization**, not ad-hoc signing.
Otherwise macOS shows: *Apple could not verify “restore_privacy_client” is free of malware…*

### Automated (preferred)

After `flutter build macos --release`:

```bash
# From repo root — signs host + PacketTunnel with Developer ID Application,
# submits to notarytool, staples, and writes the release zip:
python3 scripts/sign_and_notarize_macos.py \
  --app client_app/build/macos/Build/Products/Release/restore_privacy_client.app \
  --zip releases/0.0.9/restore-privacy-client-0.0.9-macos.zip
```

Credentials: `RP_NOTARY_KEY` / `RP_NOTARY_KEY_ID` / `RP_NOTARY_ISSUER`, or the
App Store Connect API key under `~/Library/Developer/perccent-codesign/`.
Identity default: `Developer ID Application: Russell Sneddon (SFCBP95595)`.

Release packaging (`scripts/build_release_0.0.9.py`) calls this same path so the
GitHub **macos.zip** is Gatekeeper-safe.

### Manual

```bash
# codesign --options runtime --timestamp --sign "Developer ID Application: …" …
xcrun notarytool submit <zip-of-app> --key … --key-id … --issuer … --wait
xcrun stapler staple restore_privacy_client.app
spctl --assess --type execute -vv restore_privacy_client.app   # expect: accepted, Notarized Developer ID
```

**Windows hosts cannot notarize.**

## 9. Smoke checklist

- [ ] `flutter run -d macos` shows retro UI and auto-connect  
- [ ] Channel responds (extension stub or real tunnel)  
- [ ] With extension signed: full tunnel online via RPT node  
- [ ] Quit / disconnect restores routing  
- [ ] No node private key in the `.app` bundle
