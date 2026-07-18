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

**Already in-repo** (host + extension):

| Bundle | ID |
|--------|-----|
| Host | `com.restoreprivacy.restorePrivacyClient` |
| PacketTunnel | `com.restoreprivacy.restorePrivacyClient.PacketTunnel` |
| App Group | `group.com.restoreprivacy.shared` |
| Team | `SFCBP95595` |

- Host: `Runner/DebugProfile.entitlements` + `Runner/Release.entitlements` include `packet-tunnel-provider` + App Group.  
- Extension: `PacketTunnel/PacketTunnel.entitlements` same NE + App Group.  

**Your steps:** Developer portal App IDs → Xcode Team + Automatic Signing → set PacketTunnel `CODE_SIGNING_ALLOWED=YES` for real VPN. Full ordered list: [APPLE_BUILD.md — Operator checklist](../APPLE_BUILD.md#operator-checklist--enable-real-packet-tunnel-vpn).

## 3. Packet Tunnel extension

The **PacketTunnel** target already exists (`NativePrep/PacketTunnelProvider.swift` + embed phase). Do **not** add a second NE target unless you rename bundle IDs everywhere (`RptVpnChannel.providerBundleId` must match).

## 4. Method channel contract

Identical to iOS / Android:

| | |
|--|--|
| Channel | `restore_privacy/vpn` |
| Methods | `connect`, `disconnect` |
| Args / results | See `lib/vpn_controller.dart` and `lib/connect_status.dart` |

Endpoint defaults: `lib/rpt_config.dart` → `104.156.224.47:44044`.

**Residual public IP:** product “Connected” requires Packet Tunnel `.connected`. A host-side RPT2 HELLO alone is diagnostic (`ok: false`) and does **not** change your ISP egress IP — enable Network Extension signing/entitlements for full-system VPN.

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
  --zip releases/0.1.0/restore-privacy-client-0.1.0-macos.zip
```

Credentials: `RP_NOTARY_KEY` / `RP_NOTARY_KEY_ID` / `RP_NOTARY_ISSUER`, or the
App Store Connect API key under `~/Library/Developer/perccent-codesign/`.
Identity default: `Developer ID Application: Russell Sneddon (SFCBP95595)`.

Release packaging (`scripts/build_release_0.1.0.py`) calls this same path so the
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
