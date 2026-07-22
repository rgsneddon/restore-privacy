# Apple handoff — Restore Privacy 0.3.8

Catalog monopin: **0.3.8**

## Product behaviour (must ship in macOS + iOS builds)

Parity with Windows/Linux desktop unlock:

1. **Accept end-user licence** (local only).
2. **Forced keygen unlock surface** when licence is accepted but payment entitlement is missing — `client_app/lib/main.dart` `_showKeygenSheet` / `LicenceGate.needsKeygenUnlock` / `importKeygenAndVerify`. **Not Settings-only.**
3. **Device bind after active keygen** — `importKeygenAndVerify` / `refreshEntitlementFromRemote` call `bindDeviceEntitlement` → `POST /api/bind-device-entitlement` with Ed25519 `device_pub` from native `devicePubHex` (`RptVpnChannel` on iOS/macOS; `MainActivity` on Android). Required when node has `RPT_REQUIRE_PAYMENT_ENTITLEMENT=1`.
4. **Download alone does not unlock residual** — node HELLO requires active entitlement + bound device; residual failure copy in `connect_status.dart` guides users back to keygen when remote reset/timeout-class errors appear.
5. Connect only while subscription active (online re-check).

Verify after Mac build:

```bash
cd client_app && flutter test test/keygen_bind_device_test.dart
# Confirm iOS/macOS channels implement method "devicePubHex"
```

## Build on Mac (Developer ID + notarize macOS; Team-signed iOS)

```bash
cd client_app
# Confirm version pins
grep productVersion lib/rpt_config.dart   # expect 0.3.8
grep '^version:' pubspec.yaml            # expect 0.3.8+

flutter pub get
flutter build macos --release
flutter build ios --release --no-codesign   # or full Team sign in Xcode

# Package + sign per APPLE_BUILD.md / prior 0.3.x handoffs:
# - macOS: Developer ID Application, notarize, staple → restore-privacy-client-0.3.8-macos.zip
# - iOS: Team-signed sideload package → restore-privacy-client-0.3.8-ios.zip
```

## Stage after Mac build

Copy signed zips to:

- `releases/0.3.8/`
- Iceland VPS: `/opt/restore-privacy/paid_assets/0.3.8/`
- (optional) `status_page/assets/0.3.8/` for Render-local fallback

Then buyers get packages via paid fulfilment only (token grant / VPS fetch secret).

## Honesty

Live notarization / App Store submission is **not** performed on Windows CI hosts. This handoff is the Mac operator path for catalog monopin **0.3.8**.
