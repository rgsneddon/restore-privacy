# Apple handoff — Restore Privacy 0.4.8

Catalog monopin: **0.4.8**

## Shipped status (Mac rebuild)

| Package | Status |
|---------|--------|
| `restore-privacy-client-0.4.8-macos.zip` | **Developer ID** signed, **notarized + stapled** (notary id `69a13d19-f47e-48bd-9647-404e8872d6de`, Accepted); Gatekeeper `Notarized Developer ID` |
| `restore-privacy-client-0.4.8-ios.zip` | **Apple Distribution / Team-signed** sideload; `CFBundleShortVersionString` **0.4.8**; native channel parity with macOS Connect enable+start / Disconnect stop+wait (iOS Settings Allow for VPN — not macOS Network pane) |

Hosted at GitHub release **0.4.8** and Iceland VPS `/opt/restore-privacy/paid_assets/0.4.8/` (paid fulfilment only).

## Product behaviour (must ship in macOS + iOS builds)

Parity with Windows/Linux desktop (catalog **0.4.8**), plus macOS UX since 0.4.7:

1. Accept end-user licence (local only).
2. Connect allowed = active subscription + keygen activated (forced keygen sheet when needed).
3. **Valid keygen dismisses the sheet** — paste supported; sheet uses paired root navigator push/pop so it cannot stick open.
4. **Connect** re-registers/enables system Packet Tunnel and `startTunnel` so Network VPN turns on with the app.
5. **Disconnect** stops the system Packet Tunnel so Network VPN turns off with the app.
6. EXPIRED renew surface (not keygen) when subscription ends.
7. Device bind after active keygen (`bindDeviceEntitlement` / `devicePubHex`).
8. Privacy-scale Settings lean defaults; multi-peer IS/RO/DE residual catalog.
9. Version monopin **0.4.8**.
10. Public DevID host omits NE; residual on a developer Mac: `scripts/sign_macos_residual_team.py`.

### Since 0.4.7

| Area | Tree must include |
|------|-------------------|
| Catalog pin | `0.4.8` in pubspec + `productVersion` |
| Keygen UX | Paste, auto-verify on paste, dismiss on valid unlock |
| Connect | `enableProductVpnAndStartTunnel` / recreate if Network config deleted |
| Disconnect | `stopAllTunnels` + wait until system VPN down |
| NE honesty | `hostHasPacketTunnelNetworkExtensionEntitlement` messaging |

Verify after Mac build:

```bash
cd client_app
grep productVersion lib/rpt_config.dart   # expect 0.4.8
grep '^version:' pubspec.yaml            # expect 0.4.8+
flutter test test/keygen_paste_test.dart test/connect_status_test.dart
```

## Build on Mac

```bash
git fetch origin && git checkout main   # or tag 0.4.8
cd client_app
flutter pub get
flutter build macos --release
flutter build ios --release --no-codesign

# From repo root:
python scripts/build_release_0.4.8.py --apple-only
# or full catalog (Apple + CF non-Apple):
python scripts/build_release_0.4.8.py
```

## Stage

- `releases/0.4.8/`
- VPS: `/opt/restore-privacy/paid_assets/0.4.8/`
- optional `status_page/assets/0.4.8/`

```bash
python scripts/host_paid_assets_vps.py --stage --upload --version 0.4.8 --force
# If root SSH fails: Host restore-privacy-iceland (raskul) + scp + sudo cp
```

## Residual (developer Mac only)

Public DevID zip is for paid downloaders. For residual public-IP change on a Team-provisioned Mac:

```bash
python3 scripts/sign_macos_residual_team.py \
  --app client_app/build/macos/Build/Products/Release/restore_privacy_client.app
```

## GitHub

```bash
gh release create 0.4.8 \
  releases/0.4.8/restore-privacy-client-0.4.8-macos.zip \
  releases/0.4.8/restore-privacy-client-0.4.8-ios.zip \
  releases/0.4.8/restore-privacy-client-0.4.8-windows-x64-setup.exe \
  releases/0.4.8/restore-privacy-client-0.4.8-android.apk \
  releases/0.4.8/restore-privacy-client-0.4.8-linux-x64.tar.gz \
  --title "0.4.8" \
  --notes-file scripts/RELEASE_NOTES_0.4.8.md
```
