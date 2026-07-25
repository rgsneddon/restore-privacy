# Apple handoff Ã¢â‚¬â€ Restore Privacy 0.4.5

Catalog monopin: **0.4.5**

## Product behaviour (must ship in macOS + iOS builds)

Parity with Windows/Linux desktop (catalog **0.4.5** product pin):

1. **Accept end-user licence** (local only).
2. **Connect allowed = active subscription + keygen activated.** Forced keygen unlock when licence is accepted but keygen is missing Ã¢â‚¬â€ `client_app/lib/main.dart` `_showKeygenSheet` / `LicenceGate.needsKeygenUnlock` / `importKeygenAndVerify`. **Not Settings-only.**
3. **EXPIRED renew surface** when subscription is revoked/failed/period-ended Ã¢â‚¬â€ `_showRenewLicenceSheet` / `needsLicenceRenewal` with **renew your licence *here*** and platform Stripe payment portal (`renewLicenceUrl`). Do **not** open keygen modal for EXPIRED.
4. **Device bind after active keygen** Ã¢â‚¬â€ `importKeygenAndVerify` / `refreshEntitlementFromRemote` call `bindDeviceEntitlement` Ã¢â€ ’ `POST /api/bind-device-entitlement` with Ed25519 `device_pub` from native `devicePubHex` (`RptVpnChannel` on iOS/macOS; `MainActivity` on Android). Required when node has `RPT_REQUIRE_PAYMENT_ENTITLEMENT=1`.
5. **Download alone does not unlock residual** Ã¢â‚¬â€ node HELLO requires active entitlement + bound device; residual failure copy in `connect_status.dart` guides users back to keygen when remote reset/timeout-class errors appear.
6. Connect only while status **OK** (online re-check); catalog pay is **monthly or yearly** per platform on the status host.
7. **Privacy-scale Settings (0.4.5 lean-off defaults)** Ã¢â‚¬â€ traffic shaping / outer obfuscation / multi-hop toggles with honest explainers; factory defaults **Off** for optional residual scale (core residual always required). **Hot-apply** while connected where the platform residual shell supports it (multi-hop re-establishes residual).
8. **Ping statistics** Ã¢â‚¬â€ deviceÃ¢â€ ’entry (and deviceÃ¢â€ ’exit when multi-hop is ON) best-effort RTT from Settings; not a contractual SLA.

Verify after Mac build:

```bash
cd client_app && flutter test test/keygen_bind_device_test.dart
# Confirm iOS/macOS channels implement method "devicePubHex"
grep productVersion lib/rpt_config.dart   # expect 0.4.5
grep '^version:' pubspec.yaml            # expect 0.4.5+
```

## Build on Mac (Developer ID + notarize macOS; Team-signed iOS)

```bash
cd client_app
# Confirm version pins
grep productVersion lib/rpt_config.dart   # expect 0.4.5
grep '^version:' pubspec.yaml            # expect 0.4.5+

flutter pub get
flutter build macos --release
flutter build ios --release --no-codesign   # or full Team sign in Xcode

# Package + sign per APPLE_BUILD.md:
# - macOS: Developer ID Application, notarize, staple Ã¢â€ ’ restore-privacy-client-0.4.5-macos.zip
# - iOS: Team-signed sideload package Ã¢â€ ’ restore-privacy-client-0.4.5-ios.zip
```

## Stage after Mac build

Copy signed zips to:

- `releases/0.4.5/`
- Iceland VPS: `/opt/restore-privacy/paid_assets/0.4.5/`
  (`python scripts/host_paid_assets_vps.py --stage --upload`)
- (optional) `status_page/assets/0.4.5/` for Render-local fallback

Then buyers get packages via paid fulfilment only (token grant / VPS fetch secret).

Catalog monopin and status-host BUY buttons must stay **0.4.5** (`status_page/downloads.py` `RELEASE_VERSION`, `client/VERSION`, Flutter `productVersion`).

## GitHub breadcrumbs (tag **0.4.5**)

```bash
# After Mac rebuild of real signed zips (replace CF placeholders if present):
gh release create 0.4.5 \
  releases/0.4.5/restore-privacy-client-0.4.5-macos.zip \
  releases/0.4.5/restore-privacy-client-0.4.5-ios.zip \
  releases/0.4.5/restore-privacy-client-0.4.5-windows-x64-setup.exe \
  releases/0.4.5/restore-privacy-client-0.4.5-android.apk \
  releases/0.4.5/restore-privacy-client-0.4.5-linux-x64.tar.gz \
  --title "0.4.5" \
  --notes-file scripts/RELEASE_NOTES_0.4.5.md
```

Filenames must match catalog:
- `restore-privacy-client-0.4.5-macos.zip`
- `restore-privacy-client-0.4.5-ios.zip`

Windows operator may already have staged CF zips under those names; **replace** them with DevID-notarized / Team-signed builds before tagging GitHub if buyers need honest Apple packages.

## Honesty — staged Apple packages (0.4.5 Mac rebuild)

**Status (2026-07-25 Mac operator):**

| Package | Provenance |
|---------|------------|
| `restore-privacy-client-0.4.5-macos.zip` | Flutter rebuild + **Developer ID Application** + **notary Accepted** + **stapled** (submission `dcb07f98-7b2b-45c2-8173-ee4865df464e`) |
| `restore-privacy-client-0.4.5-ios.zip` | Flutter rebuild + **Apple Distribution** Team-signed sideload; `CFBundleShortVersionString` **0.4.5** |

App Store submission is still out of scope (sideload / DevID only).
Product entry + exit ElGamal **pubs** only (no `*.priv`) in packages.

Re-stage after rebuild:

```bash
python scripts/host_paid_assets_vps.py --stage --upload --version 0.4.5 --force
```

Audit helper:

```bash
python -c "from apple_package_audit import audit_catalog_apple_packages; import json; print(json.dumps(audit_catalog_apple_packages(version='0.4.5'), indent=2))"
```

