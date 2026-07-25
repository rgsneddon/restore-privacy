# Apple handoff — Restore Privacy 0.4.6

Catalog monopin: **0.4.6**

Windows may have staged **carry-forward** macOS/iOS zips renamed to 0.4.6 for catalog
filenames. **Replace** them with DevID-notarized macOS + Team-signed iOS before
buyers should treat Apple packages as native 0.4.6 product builds.

## Product behaviour (must ship in macOS + iOS builds)

Parity with Windows/Linux desktop (catalog **0.4.6** product pin):

1. **Accept end-user licence** (local only).
2. **Connect allowed = active subscription + keygen activated.** Forced keygen unlock when licence is accepted but keygen is missing — `client_app/lib/main.dart` `_showKeygenSheet` / `LicenceGate.needsKeygenUnlock` / `importKeygenAndVerify`. **Not Settings-only.**
3. **EXPIRED renew surface** when subscription is revoked/failed/period-ended — `_showRenewLicenceSheet` / `needsLicenceRenewal` with **renew your licence *here*** and platform Stripe payment portal (`renewLicenceUrl`). Do **not** open keygen modal for EXPIRED.
4. **Device bind after active keygen** — `importKeygenAndVerify` / `refreshEntitlementFromRemote` call `bindDeviceEntitlement` → `POST /api/bind-device-entitlement` with Ed25519 `device_pub` from native `devicePubHex` (`RptVpnChannel` on iOS/macOS; `MainActivity` on Android). Required when node has `RPT_REQUIRE_PAYMENT_ENTITLEMENT=1`.
5. **Download alone does not unlock residual** — node HELLO requires active entitlement + bound device; residual failure copy in `connect_status.dart` guides users back to keygen when remote reset/timeout-class errors appear.
6. Connect only while status **OK** (online re-check); catalog pay is **monthly or yearly** per platform on the status host.
7. **Privacy-scale Settings** — traffic shaping / outer obfuscation / multi-hop toggles with honest explainers; factory defaults **Off** for optional residual scale (core residual always required). **Hot-apply** while connected where the platform residual shell supports it (multi-hop re-establishes residual).
8. **Ping statistics** — device→entry (and device→exit when multi-hop is ON) best-effort RTT from Settings; not a contractual SLA.
9. **Multi-peer residual catalog** — IS / RO / DE selectable entry; residual-via-exit when multi-hop enabled (not full onion encapsulation).
10. **Version monopin 0.4.6** — upgrade banner / paid path must advertise **0.4.6**, not 0.4.5.

### Since 0.4.5 (docs / web / operator — rebuild picks up tree)

| Area | What Mac rebuild must include from tree |
|------|----------------------------------------|
| Catalog pin | `0.4.6` in `pubspec.yaml`, `lib/rpt_config.dart` `productVersion` |
| Residual peers | Live monopin hosts IS/RO/DE (product pubs only — no `*.priv`) |
| Status site | Wipe “ALL NODES” copy + admin fleet capacity probes are **status-host** side; clients still use title-only public status |
| AUDIT | Public audit HTML solid RAG swatches (status host `public_docs.py`) — no client change required |
| Capacity | Optional client probe path needs same `RPT_CAPACITY_TOKEN` as residual nodes when operator enables near-capacity migration |

Verify after Mac build:

```bash
cd client_app && flutter test test/keygen_bind_device_test.dart
# Confirm iOS/macOS channels implement method "devicePubHex"
grep productVersion lib/rpt_config.dart   # expect 0.4.6
grep '^version:' pubspec.yaml            # expect 0.4.6+
```

## Build on Mac (Developer ID + notarize macOS; Team-signed iOS)

```bash
git fetch origin
git checkout release-0.4.6   # or tag 0.4.6 when published
cd client_app
# Confirm version pins
grep productVersion lib/rpt_config.dart   # expect 0.4.6
grep '^version:' pubspec.yaml            # expect 0.4.6+

flutter pub get
flutter build macos --release
flutter build ios --release --no-codesign   # or full Team sign in Xcode

# Package + sign per APPLE_BUILD.md:
# - macOS: Developer ID Application, notarize, staple → restore-privacy-client-0.4.6-macos.zip
# - iOS: Team-signed sideload package → restore-privacy-client-0.4.6-ios.zip

# Optional monorepo helper (from repo root, on Mac after Flutter build):
# python scripts/build_release_0.4.6.py --apple-only
```

## Stage after Mac build

Copy signed zips to:

- `releases/0.4.6/`
- Iceland VPS: `/opt/restore-privacy/paid_assets/0.4.6/`
  (`python scripts/host_paid_assets_vps.py --stage --upload --version 0.4.6 --force`)
- (optional) `status_page/assets/0.4.6/` for Render-local fallback

Then buyers get packages via paid fulfilment only (token grant / VPS fetch secret).

Catalog monopin and status-host BUY buttons must stay **0.4.6** (`status_page/downloads.py` `RELEASE_VERSION`, `client/VERSION`, Flutter `productVersion`).

## GitHub breadcrumbs (tag **0.4.6**)

```bash
# After Mac rebuild of real signed zips (replace CF placeholders if present):
gh release create 0.4.6 \
  releases/0.4.6/restore-privacy-client-0.4.6-macos.zip \
  releases/0.4.6/restore-privacy-client-0.4.6-ios.zip \
  releases/0.4.6/restore-privacy-client-0.4.6-windows-x64-setup.exe \
  releases/0.4.6/restore-privacy-client-0.4.6-android.apk \
  releases/0.4.6/restore-privacy-client-0.4.6-linux-x64.tar.gz \
  --title "0.4.6" \
  --notes-file scripts/RELEASE_NOTES_0.4.6.md
```

Filenames must match catalog:

- `restore-privacy-client-0.4.6-macos.zip`
- `restore-privacy-client-0.4.6-ios.zip`

After iOS rebuild confirm CFBundleShortVersionString **0.4.6** in Info.plist.

## Honesty — staged Apple packages (pre-Mac)

| Package | Provenance on Windows ship host |
|---------|--------------------------------|
| `restore-privacy-client-0.4.6-macos.zip` | **Carry-forward** filename pin from 0.4.5 until Mac rebuild + DevID + notarize |
| `restore-privacy-client-0.4.6-ios.zip` | **Carry-forward** filename pin from 0.4.5 until Mac Team-signed rebuild |

App Store submission remains out of scope (sideload / DevID only).
Product entry + exit ElGamal **pubs** only (no `*.priv`) in packages.

Re-stage after rebuild:

```bash
python scripts/host_paid_assets_vps.py --stage --upload --version 0.4.6 --force
```

Audit helper:

```bash
python -c "from apple_package_audit import audit_catalog_apple_packages; import json; print(json.dumps(audit_catalog_apple_packages(version='0.4.6'), indent=2))"
```
