# Apple handoff — Restore Privacy 0.4.8

Catalog monopin: **0.4.8**

## Shipped status (Windows host)

Packages staged from the Windows ship host are **carry-forward filename pins** from **0.4.6** unless a Mac rebuild has replaced them. Do **not** claim new notarization/Team-sign until this Mac checklist completes.

| Package | Status |
|---------|--------|
| `restore-privacy-client-0.4.8-macos.zip` | **CF** until Mac: Developer ID + notarize + staple |
| `restore-privacy-client-0.4.8-ios.zip` | **CF** until Mac: Apple Distribution / Team-signed sideload |

After Mac rebuild: host at GitHub release **0.4.8** and VPS `/opt/restore-privacy/paid_assets/0.4.8/` (paid fulfilment only).

## Product behaviour (must ship in macOS + iOS builds)

Parity with Windows/Linux desktop (catalog **0.4.8** product pin):

1. **Accept end-user licence** (local only).
2. **Connect allowed = active subscription + keygen activated.** Forced keygen unlock when licence is accepted but keygen is missing.
3. **EXPIRED renew surface** when subscription is revoked/failed/period-ended.
4. **Device bind after active keygen** when node requires payment entitlement.
5. **Download alone does not unlock residual.**
6. Connect only while status **OK**; catalog pay monthly or yearly.
7. **Privacy-scale Settings** — privacy-scale toggles for traffic shaping / outer obfuscation / multi-hop with honest explainers; optional scale **Off** by default; hot-apply where supported.
8. **Main-shell country picker** above Connect: **IS / RO / DE** with flags; default **IS**.
9. Banner: **Virtual Private Network** (not “UK VPN”).
10. **Version monopin 0.4.8** — upgrade banner / paid path must advertise **0.4.8**; iOS/macOS marketing version must match monopin (`CFBundleShortVersionString` **0.4.8**).
11. **Device bind after active keygen** — `POST /api/bind-device-entitlement` with Ed25519 `device_pub` from native channel when residual node requires payment entitlement.

### Since 0.4.6 (rebuild picks up tree)

| Area | What Mac rebuild must include from tree |
|------|----------------------------------------|
| Catalog pin | `0.4.8` in `pubspec.yaml`, `lib/rpt_config.dart` `productVersion` |
| Country picker | `lib/main.dart` + `country_select.dart` IS/RO/DE flags above Connect |
| Banner | `kBannerTitle` Virtual Private Network |
| Residual peers | Live monopin hosts IS/RO/DE (product pubs only — no `*.priv`) |

## Mac rebuild (operator)

```bash
cd client_app
flutter build macos --release
flutter build ios --no-codesign
# then scripts/build_release_0.4.8.py --apple-only on Mac with signing secrets
# or inject_apple_secrets + sign_and_notarize_macos / Team-sign iOS
```

See prior `APPLE_HANDOFF_0.4.6.md` for signing identity details if still current.
