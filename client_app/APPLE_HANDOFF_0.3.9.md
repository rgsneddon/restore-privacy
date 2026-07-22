# Apple handoff — Restore Privacy 0.3.9

Catalog monopin: **0.3.9**

## Product behaviour (must ship in macOS + iOS builds)

Parity with Windows/Linux desktop (catalog 0.3.9 product pin):

1. **Accept end-user licence** (local only).
2. **Forced keygen unlock surface** when licence is accepted but payment entitlement is missing — `client_app/lib/main.dart` `_showKeygenSheet` / `LicenceGate.needsKeygenUnlock` / `importKeygenAndVerify`. **Not Settings-only.**
3. **Device bind after active keygen** — `importKeygenAndVerify` / `refreshEntitlementFromRemote` call `bindDeviceEntitlement` → `POST /api/bind-device-entitlement` with Ed25519 `device_pub` from native `devicePubHex` (`RptVpnChannel` on iOS/macOS; `MainActivity` on Android). Required when node has `RPT_REQUIRE_PAYMENT_ENTITLEMENT=1`.
4. **Download alone does not unlock residual** — node HELLO requires active entitlement + bound device; residual failure copy in `connect_status.dart` guides users back to keygen when remote reset/timeout-class errors appear.
5. Connect only while subscription active (online re-check).
6. **Privacy-scale Settings (0.3.9)** — traffic shaping / outer obfuscation / multi-hop toggles with honest explainers; **hot-apply** while connected where the platform residual shell supports it (multi-hop re-establishes residual).
7. **Ping statistics (0.3.9)** — device→entry (and device→exit when multi-hop is ON) best-effort RTT from Settings; not a contractual SLA.

Verify after Mac build:

```bash
cd client_app && flutter test test/keygen_bind_device_test.dart
# Confirm iOS/macOS channels implement method "devicePubHex"
grep productVersion lib/rpt_config.dart   # expect 0.3.9
grep '^version:' pubspec.yaml            # expect 0.3.9+
```

## Build on Mac (Developer ID + notarize macOS; Team-signed iOS)

```bash
cd client_app
# Confirm version pins
grep productVersion lib/rpt_config.dart   # expect 0.3.9
grep '^version:' pubspec.yaml            # expect 0.3.9+

flutter pub get
flutter build macos --release
flutter build ios --release --no-codesign   # or full Team sign in Xcode

# Package + sign per APPLE_BUILD.md / prior 0.3.x handoffs:
# - macOS: Developer ID Application, notarize, staple → restore-privacy-client-0.3.9-macos.zip
# - iOS: Team-signed sideload package → restore-privacy-client-0.3.9-ios.zip
```

## Stage after Mac build

Copy signed zips to:

- `releases/0.3.9/`
- Iceland VPS: `/opt/restore-privacy/paid_assets/0.3.9/`
  (`python scripts/host_paid_assets_vps.py --stage --upload`)
- (optional) `status_page/assets/0.3.9/` for Render-local fallback

Then buyers get packages via paid fulfilment only (token grant / VPS fetch secret).

Catalog monopin and status-host BUY buttons must stay **0.3.9** (`status_page/downloads.py` `RELEASE_VERSION`, `client/VERSION`, Flutter `productVersion`).

## Honesty

Live notarization / App Store submission is **not** performed on Windows CI hosts. This handoff is the Mac operator path for catalog monopin **0.3.9**. Staged zips under `status_page/assets/0.3.9/` may be rebuild placeholders until a Mac operator re-signs/notarizes; re-run upload after Mac package refresh.
