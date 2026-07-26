# Apple handoff — Restore Privacy 0.4.7

Catalog monopin: **0.4.7**

## Shipped status (Mac rebuild complete)

Native Apple packages for **0.4.7** are built, signed, and hosted:

| Package | Status |
|---------|--------|
| `restore-privacy-client-0.4.7-macos.zip` | **Developer ID** signed, **notarized + stapled** (notary id `955cc8b1-aa51-45ec-8169-f9cc9fbc1950`, Accepted); Gatekeeper `Notarized Developer ID` |
| `restore-privacy-client-0.4.7-ios.zip` | **Apple Distribution / Team-signed** sideload; `CFBundleShortVersionString` **0.4.7** |

Hosted at GitHub release **0.4.7** and Iceland VPS `/opt/restore-privacy/paid_assets/0.4.7/` (paid fulfilment only).

## Product behaviour (must ship in macOS + iOS builds)

Parity with Windows/Linux desktop (catalog **0.4.7** product pin), plus **0.4.7** UI fixes:

1. **Accept end-user licence** (local only).
2. **Connect allowed = active subscription + keygen activated.** Forced keygen unlock when licence is accepted but keygen is missing — `client_app/lib/main.dart` `_showKeygenSheet` / `LicenceGate.needsKeygenUnlock` / `importKeygenAndVerify`. **Not Settings-only.**
3. **Valid keygen dismisses the sheet** — `shouldDismissKeygenSheetAfterUnlock(paymentAllowsConnect: …)` → `Navigator.pop` on success only; invalid keys keep the sheet open.
4. **Window stays open after Connect** — `shouldHideToTrayAfterConnect` / `shouldHideToTrayAfterConnectSuccess` are **false**; product residual success does not auto-hide to menu-bar tray.
5. **EXPIRED renew surface** when subscription is revoked/failed/period-ended — `_showRenewLicenceSheet` / `needsLicenceRenewal` with **renew your licence *here*** and platform Stripe payment portal (`renewLicenceUrl`). Do **not** open keygen modal for EXPIRED.
6. **Device bind after active keygen** — `importKeygenAndVerify` / `refreshEntitlementFromRemote` call `bindDeviceEntitlement` → `POST /api/bind-device-entitlement` with Ed25519 `device_pub` from native `devicePubHex`.
7. **Download alone does not unlock residual** — node HELLO requires active entitlement + bound device.
8. Connect only while status **OK** (online re-check); catalog pay is **monthly or yearly** per platform on the status host.
9. **Privacy-scale Settings** — traffic shaping / outer obfuscation / multi-hop toggles with honest explainers; factory defaults **Off** for optional residual scale (core residual always required).
10. **Ping statistics** — device→entry (and device→exit when multi-hop is ON) best-effort RTT from Settings.
11. **Multi-peer residual catalog** — IS / RO / DE selectable entry; residual-via-exit when multi-hop enabled.
12. **Version monopin 0.4.7** — upgrade banner / paid path must advertise **0.4.7**, not 0.4.6.
13. **macOS Packet Tunnel prep** — pre-register VPN profile before Connect; open System Settings on NE permission failures; prepare success only after Packet Tunnel save.

### Since 0.4.6 (docs / tree)

| Area | What Mac rebuild must include from tree |
|------|----------------------------------------|
| Catalog pin | `0.4.7` in `pubspec.yaml`, `lib/rpt_config.dart` `productVersion` |
| Keygen UX | Dismiss sheet on valid unlock; stay open on invalid |
| Window UX | No auto hide-to-tray after Connect success |
| NE UX | Pre-register + Settings deep-link on permission failures |
| Residual peers | Live monopin hosts IS/RO/DE (product pubs only — no `*.priv`) |

Verify after Mac build:

```bash
cd client_app && flutter test test/keygen_bind_device_test.dart
grep productVersion lib/rpt_config.dart   # expect 0.4.7
grep '^version:' pubspec.yaml            # expect 0.4.7+
```

## Build on Mac (Developer ID + notarize macOS; Team-signed iOS)

```bash
git fetch origin
git checkout main   # or tag 0.4.7 when published
cd client_app
# Confirm version pins
grep productVersion lib/rpt_config.dart   # expect 0.4.7
grep '^version:' pubspec.yaml            # expect 0.4.7+

flutter pub get
flutter build macos --release
flutter build ios --release --no-codesign   # or full Team sign in Xcode

# Package + sign per APPLE_BUILD.md:
# - macOS: Developer ID Application, notarize, staple → restore-privacy-client-0.4.7-macos.zip
# - iOS: Team-signed sideload package → restore-privacy-client-0.4.7-ios.zip

# Optional monorepo helper (from repo root, on Mac after Flutter build):
# python scripts/build_release_0.4.7.py --apple-only
```

## Stage after Mac build

Copy signed zips to:

- `releases/0.4.7/`
- Iceland VPS: `/opt/restore-privacy/paid_assets/0.4.7/`
  (`python scripts/host_paid_assets_vps.py --stage --upload --version 0.4.7 --force`)
- (optional) `status_page/assets/0.4.7/` for Render-local fallback

Then buyers get packages via paid fulfilment only (token grant / VPS fetch secret).

Catalog monopin and status-host BUY buttons must stay **0.4.7** (`status_page/downloads.py` `RELEASE_VERSION`, `client/VERSION`, Flutter `productVersion`).

## GitHub breadcrumbs (tag **0.4.7**)

```bash
gh release create 0.4.7 \
  releases/0.4.7/restore-privacy-client-0.4.7-macos.zip \
  releases/0.4.7/restore-privacy-client-0.4.7-ios.zip \
  releases/0.4.7/restore-privacy-client-0.4.7-windows-x64-setup.exe \
  releases/0.4.7/restore-privacy-client-0.4.7-android.apk \
  releases/0.4.7/restore-privacy-client-0.4.7-linux-x64.tar.gz \
  --title "0.4.7" \
  --notes-file scripts/RELEASE_NOTES_0.4.7.md
```

Filenames must match catalog:

- `restore-privacy-client-0.4.7-macos.zip`
- `restore-privacy-client-0.4.7-ios.zip`

After iOS rebuild confirm CFBundleShortVersionString **0.4.7** in Info.plist.

## Honesty — shipped Apple packages (post-Mac)

| Package | Provenance |
|---------|------------|
| `restore-privacy-client-0.4.7-macos.zip` | **Native** Flutter release build from monopin **0.4.7** tree; Developer ID Application (SFCBP95595); notarized + stapled |
| `restore-privacy-client-0.4.7-ios.zip` | **Native** Flutter release build from monopin **0.4.7** tree; Apple Distribution Team-signed sideload |

App Store submission remains out of scope (sideload / DevID only).
Product entry + exit ElGamal **pubs** only (no `*.priv`) in packages.

Re-stage if rebuilding again:

```bash
python scripts/host_paid_assets_vps.py --stage --upload --version 0.4.7 --force
# If script SSH as root times out: use Host restore-privacy-iceland (raskul) + scp
```

Audit helper:

```bash
python -c "from apple_package_audit import audit_catalog_apple_packages; import json; print(json.dumps(audit_catalog_apple_packages(version='0.4.7'), indent=2))"
```
