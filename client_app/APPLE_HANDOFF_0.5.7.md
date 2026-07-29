# Apple handoff — Restore Privacy **0.5.7**

**Monopin / this build:** `0.5.7`

## Ship checklist (every Apple build going forward)

| Step | Script / action | Outcome |
|------|-----------------|---------|
| 1. Flutter build | `flutter build macos --release` + `flutter build ios --release --no-codesign` | Release app + Runner.app |
| 2. **Team residual NE re-sign** (required) | `build_release_0.5.7.py --apple-only` runs `apple_ship_gates.run_residual_team_resign` → copy `restore_privacy_client.residual-team.app` signed with **Apple Development** + Mac Team NE profiles | Residual Connect works on **this Mac** |
| 3. **DevID + notarize** (public zip) | Same `--apple-only` then `sign_and_notarize_macos.py` on the **original** Flutter app | Catalog `…-macos.zip` (no host residual NE — AMFI-safe) |
| 4. **iOS Team-sign** | Same `--apple-only` codesigns Runner + PacketTunnel with **Apple Distribution** | Catalog `…-ios.zip` sideload |
| 5. **Host paid assets (macOS + iOS + Linux)** | `host_paid_assets_vps.py --stage --upload --version 0.5.7 --force` with `RPT_SSH_KEY=~/.ssh/id_ed25519_restore_privacy_eu` (root@135.181.152.10) — or `--apple-only --host-paid` after Apple seal; Linux tgz is also staged from this Mac | Helsinki `paid_assets/0.5.7/` basenames `…-macos.zip`, `…-ios.zip`, `…-linux-x64.tar.gz` |
| 6. Catalog pin | `client/VERSION` + `downloads.RELEASE_VERSION` = **0.5.7**; live `/api/catalog-version` after Render deploy | Download links = monopin only |
| 7. **Windows PE (deferred)** | Native PE rebuild/upload from the **Windows machine** (see `WINDOWS_HANDOFF_0.5.7.md` + Helsinki breadcrumbs) | Android already sealed on Mac for 0.5.7; Windows is the remaining host gap |

**Do not skip step 2** for residual Connect testing. Opt-out only for non-residual CI:

```bash
RPT_SKIP_RESIDUAL_TEAM=1 python3 scripts/build_release_0.5.7.py --apple-only
# or: python3 scripts/build_release_0.5.7.py --apple-only --skip-residual-team
```

### One-shot Mac ship (build + host macOS/iOS/Linux)

```bash
cd client_app
flutter build macos --release
flutter build ios --release --no-codesign
cd ..
# Package Apple (+ Linux rebuild when full script runs) then host monopin:
python3 scripts/build_release_0.5.7.py
export RPT_SSH_HOST=135.181.152.10 RPT_SSH_USER=root
export RPT_SSH_KEY=~/.ssh/id_ed25519_restore_privacy_eu
python3 scripts/host_paid_assets_vps.py --stage --upload --version 0.5.7 --force
```

**Helsinki basenames this Mac owns:**

```text
paid_assets/0.5.7/restore-privacy-client-0.5.7-macos.zip
paid_assets/0.5.7/restore-privacy-client-0.5.7-ios.zip
paid_assets/0.5.7/restore-privacy-client-0.5.7-linux-x64.tar.gz
```

Windows/Android native installers: rebuild and re-upload from the Windows host
(`WINDOWS_HANDOFF_0.5.7.md`). Darwin may leave CF placeholders under the same
monopin names; replace them after the PE/APK seal.

Residual app (open this for residual Connect on the build Mac):

```text
client_app/build/macos/Build/Products/Release/restore_privacy_client.residual-team.app
```

Public catalog zip (customers):

```text
releases/0.5.7/restore-privacy-client-0.5.7-macos.zip
```

### Product dual path (honesty)

| Artifact | Residual Packet Tunnel on host? | Use |
|----------|--------------------------------|-----|
| `*.residual-team.app` (Team NE re-sign) | **Yes** | Residual Connect on this Mac |
| Catalog DevID+notarized zip | **No** (by design) | Paid download / distribution |

AMFI kills Developer ID hosts that embed residual `packet-tunnel-provider`. Residual NE requires **Team** profiles.

### Settings (0.5.7)

Residual **IPv4** is **always on** (not adjustable in Settings — full-tunnel IPv4
capture is product residual). Residual **IPv6** remains a user switch at the top
of Settings → privacy scale (default ON; OFF = status claims IPv6 not protected).

### CFBundle gate

`CFBundleShortVersionString` must equal **0.5.7**. Carry-forward renames of older zips are refused.

### Residual Connect on this Mac (not the catalog zip)

Public **Developer ID** downloads omit host `packet-tunnel-provider` (AMFI). Residual
Connect must use the Team residual re-signed app:

```bash
# From monorepo root (re-sign + open):
./scripts/open_macos_residual_connect.sh
```

Or open after ship:

```text
client_app/build/macos/Build/Products/Release/restore_privacy_client.residual-team.app
```

If the node refuses HELLO (UDP timeout): enter the **keygen** from your fulfilment email
(Settings → Payment entitlement / keygen), then Connect again.

### Seal verification (this ship — 2026-07-29, residual IPv4 always-on)

| Artifact | Signing | Team ID | Notes |
|----------|---------|---------|-------|
| Catalog macOS zip | **Developer ID Application** + notarized (stapled) | **SFCBP95595** | `spctl` accepted; CFBundle **0.5.7**; residual IPv4 always-on |
| Residual-team `.app` (local only) | **Apple Development** | **SFCBP95595** | PacketTunnel has `packet-tunnel-provider`; open via `open_macos_residual_connect.sh` |
| Catalog iOS zip | **Apple Distribution** (Runner + PacketTunnel) | **SFCBP95595** | Sideload zip; both host + appex Team-signed |

**Helsinki paid store (root@135.181.152.10):**

```text
/opt/restore-privacy/paid_assets/0.5.7/restore-privacy-client-0.5.7-macos.zip
  bytes=20979936  sha256=15805eecd4ad15d795fa7ce9ae0bfabeb66336c0bd33dc9d4c34930c945573cf
/opt/restore-privacy/paid_assets/0.5.7/restore-privacy-client-0.5.7-ios.zip
  bytes=9349814   sha256=6d09d5744068a67276fc83e5764603c4cdd0ef096ed9b444638914174869999b
RPT_CATALOG_VERSION=0.5.7  (rpt-paid-assets.service)
```

Also present under the same monopin (Win/Android may still be CF until Windows-machine seal):
`…-linux-x64.tar.gz`, `…-windows-x64-setup.exe`, `…-android.apk`.

### Host stage preference

`host_paid_assets_vps.py --stage` prefers **`releases/{ver}/`** over a prior
`status_page/assets/{ver}/` copy so a re-notarize always wins over a stale stage.

### Tray restore (0.5.7)

macOS tray / dock reopen deminiaturizes and rehydrates the main window **without**
disconnecting residual. Prefer residual-team app for residual Connect testing;
catalog DevID zip is for paid distribution only.
