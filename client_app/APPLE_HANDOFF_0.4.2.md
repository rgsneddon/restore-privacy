# Apple handoff — Restore Privacy 0.4.2

Catalog monopin: **0.4.2**

## Product behaviour (must ship in macOS + iOS builds)

Parity with Windows/Linux desktop (catalog **0.4.2** product pin):

1. **Accept end-user licence** (local only).
2. **Connect allowed = active subscription + keygen activated.** Forced keygen unlock when licence is accepted but keygen is missing — `client_app/lib/main.dart` `_showKeygenSheet` / `LicenceGate.needsKeygenUnlock` / `importKeygenAndVerify`. **Not Settings-only.**
3. **EXPIRED renew surface** when subscription is revoked/failed/period-ended — `_showRenewLicenceSheet` / `needsLicenceRenewal` with **renew your licence *here*** and platform Stripe payment portal (`renewLicenceUrl`). Do **not** open keygen modal for EXPIRED.
4. **Device bind after active keygen** — `importKeygenAndVerify` / `refreshEntitlementFromRemote` call `bindDeviceEntitlement` → `POST /api/bind-device-entitlement` with Ed25519 `device_pub` from native `devicePubHex` (`RptVpnChannel` on iOS/macOS; `MainActivity` on Android). Required when node has `RPT_REQUIRE_PAYMENT_ENTITLEMENT=1`.
5. **Download alone does not unlock residual** — node HELLO requires active entitlement + bound device; residual failure copy in `connect_status.dart` guides users back to keygen when remote reset/timeout-class errors appear.
6. Connect only while status **OK** (online re-check); catalog pay is **monthly or yearly** per platform on the status host.
7. **Privacy-scale Settings (0.4.2 lean-off defaults)** — traffic shaping / outer obfuscation / multi-hop toggles with honest explainers; factory defaults **Off** for optional residual scale (core residual always required). **Hot-apply** while connected where the platform residual shell supports it (multi-hop re-establishes residual).
8. **Ping statistics** — device→entry (and device→exit when multi-hop is ON) best-effort RTT from Settings; not a contractual SLA.

Verify after Mac build:

```bash
cd client_app && flutter test test/keygen_bind_device_test.dart
# Confirm iOS/macOS channels implement method "devicePubHex"
grep productVersion lib/rpt_config.dart   # expect 0.4.2
grep '^version:' pubspec.yaml            # expect 0.4.2+
```

## Build on Mac (Developer ID + notarize macOS; Team-signed iOS)

```bash
cd client_app
# Confirm version pins
grep productVersion lib/rpt_config.dart   # expect 0.4.2
grep '^version:' pubspec.yaml            # expect 0.4.2+

flutter pub get
flutter build macos --release
flutter build ios --release --no-codesign   # or full Team sign in Xcode

# Package + sign per APPLE_BUILD.md:
# - macOS: Developer ID Application, notarize, staple → restore-privacy-client-0.4.2-macos.zip
# - iOS: Team-signed sideload package → restore-privacy-client-0.4.2-ios.zip
```

## Stage after Mac build

Copy signed zips to:

- `releases/0.4.2/`
- Iceland VPS: `/opt/restore-privacy/paid_assets/0.4.2/`
  (`python scripts/host_paid_assets_vps.py --stage --upload`)
- (optional) `status_page/assets/0.4.2/` for Render-local fallback

Then buyers get packages via paid fulfilment only (token grant / VPS fetch secret).

Catalog monopin and status-host BUY buttons must stay **0.4.2** (`status_page/downloads.py` `RELEASE_VERSION`, `client/VERSION`, Flutter `productVersion`).

## Honesty — staged Apple packages

Live notarization / App Store submission is **not** performed on Windows CI hosts.
This handoff is the Mac operator path for catalog monopin **0.4.2**.

**Mac rebuild (required for real 0.4.2 Apple packages):** rebuild with
`CFBundleShortVersionString` **0.4.2**, lean-off residual Settings defaults, OK/EXPIRED
licence surface, and product entry + exit ElGamal **pubs** only (no `*.priv`).

Prior **0.4.1** Apple handoff (`APPLE_HANDOFF_0.4.1.md`) remains the last notarized
ship notes until Mac rebuild replaces packages under `0.4.2` filenames.

Re-stage after rebuild:

```bash
python scripts/host_paid_assets_vps.py --stage --upload --version 0.4.2 --force
```

Audit helper:

```bash
python -c "from apple_package_audit import audit_catalog_apple_packages; import json; print(json.dumps(audit_catalog_apple_packages(version='0.4.2'), indent=2))"
```
