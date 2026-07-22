# Apple handoff — Restore Privacy 0.3.7

Catalog monopin: **0.3.7**

## Product behaviour (must ship in macOS + iOS builds)

Parity with Windows/Linux desktop unlock:

1. **Accept end-user licence** (local only).
2. **Forced keygen unlock surface** when licence is accepted but payment entitlement is missing — `client_app/lib/main.dart` `_showKeygenSheet` / `LicenceGate.needsKeygenUnlock` / `importKeygenAndVerify`. **Not Settings-only.**
3. **Download alone does not unlock residual** — node HELLO requires active entitlement (status host); residual failure copy in `connect_status.dart` guides users back to keygen when remote reset/timeout-class errors appear.
4. Connect only while subscription active (online re-check).

## Build on Mac (Developer ID + notarize macOS; Team-signed iOS)

```bash
cd client_app
# Confirm version pins
grep productVersion lib/rpt_config.dart   # expect 0.3.7
grep '^version:' pubspec.yaml            # expect 0.3.7+

flutter pub get
flutter build macos --release
flutter build ios --release --no-codesign   # or full Team sign in Xcode

# Package + sign per APPLE_BUILD.md / prior 0.3.x handoffs:
# - macOS: Developer ID Application, notarize, staple → restore-privacy-client-0.3.7-macos.zip
# - iOS: Team-signed sideload package → restore-privacy-client-0.3.7-ios.zip
```

## Stage after Mac build

Copy signed zips to:

- `releases/0.3.7/`
- Iceland VPS: `/opt/restore-privacy/paid_assets/0.3.7/`
- (optional) `status_page/assets/0.3.7/` for Render-local fallback

Then buyers get packages via paid fulfilment only (token grant / VPS fetch secret).

## Honesty

Live notarization / App Store submission is **not** performed on Windows CI hosts. This handoff is the Mac operator path for catalog monopin **0.3.7**.
