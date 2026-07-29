# Apple handoff — Restore Privacy **0.5.5**

**Monopin / this build:** `0.5.5`

## Ship checklist (every Apple build going forward)

| Step | Script / action | Outcome |
|------|-----------------|---------|
| 1. Flutter build | `flutter build macos --release` + `flutter build ios --release --no-codesign` | Release app + Runner.app |
| 2. **Team residual NE re-sign** (required) | `build_release_0.5.5.py --apple-only` runs `apple_ship_gates.run_residual_team_resign` → copy `restore_privacy_client.residual-team.app` signed with **Apple Development** + Mac Team NE profiles | Residual Connect works on **this Mac** |
| 3. **DevID + notarize** (public zip) | Same `--apple-only` then `sign_and_notarize_macos.py` on the **original** Flutter app | Catalog `…-macos.zip` (no host residual NE — AMFI-safe) |
| 4. **iOS Team-sign** | Same `--apple-only` codesigns Runner + PacketTunnel with **Apple Distribution** | Catalog `…-ios.zip` sideload |
| 5. **Host paid assets** | `build_release_0.5.5.py --apple-only --host-paid` **or** `host_paid_assets_vps.py --stage --upload --version 0.5.5 --force` | Helsinki `paid_assets/0.5.5/` |
| 6. Catalog pin | `client/VERSION` + `downloads.RELEASE_VERSION` = **0.5.5**; live `/api/catalog-version` after Render deploy | Download links = monopin only |

**Do not skip step 2** for residual Connect testing. Opt-out only for non-residual CI:

```bash
RPT_SKIP_RESIDUAL_TEAM=1 python3 scripts/build_release_0.5.5.py --apple-only
# or: python3 scripts/build_release_0.5.5.py --apple-only --skip-residual-team
```

### One-shot Mac ship

```bash
cd client_app
flutter build macos --release
flutter build ios --release --no-codesign
cd ..
python3 scripts/build_release_0.5.5.py --apple-only --host-paid
```

Residual app (open this for residual Connect on the build Mac):

```text
client_app/build/macos/Build/Products/Release/restore_privacy_client.residual-team.app
```

Public catalog zip (customers):

```text
releases/0.5.5/restore-privacy-client-0.5.5-macos.zip
```

### Product dual path (honesty)

| Artifact | Residual Packet Tunnel on host? | Use |
|----------|--------------------------------|-----|
| `*.residual-team.app` (Team NE re-sign) | **Yes** | Residual Connect on this Mac |
| Catalog DevID+notarized zip | **No** (by design) | Paid download / distribution |

AMFI kills Developer ID hosts that embed residual `packet-tunnel-provider`. Residual NE requires **Team** profiles.

### Settings (0.5.5)

Residual **IPv4** / **IPv6** switches are at the **top** of Settings → privacy scale
(with explainers / hover tooltips). Defaults ON.

### CFBundle gate

`CFBundleShortVersionString` must equal **0.5.5**. Carry-forward renames of older zips are refused.
