# Release notes — Restore Privacy **0.5.6**

**Catalog monopin:** 0.5.6

## Highlights

- **Apple seal (this Mac):** macOS **Developer ID + notarized** (stapled, Team **SFCBP95595**); iOS **Apple Distribution** Team-signed (Runner + PacketTunnel).
- **Residual dual path:** local `restore_privacy_client.residual-team.app` (Apple Development + `packet-tunnel-provider`) for residual Connect; catalog DevID zip remains AMFI-safe (no host residual NE).
- **Settings:** residual **IPv4 always on** (not adjustable); residual **IPv6** user switch at top of privacy scale (default ON).
- **macOS tray restore:** deminiaturize / dock reopen rehydrates the main window without disconnecting residual.
- **Host stage:** `host_paid_assets_vps.py` prefers sealed `releases/{ver}/` over a stale `status_page/assets` copy.
- **Helsinki pin:** `RPT_CATALOG_VERSION=0.5.6` on `rpt-paid-assets.service`.

## Packages

| Platform | File | Seal notes |
|----------|------|------------|
| macOS | `restore-privacy-client-0.5.6-macos.zip` | DevID + notarized; CFBundle **0.5.6** |
| iOS | `restore-privacy-client-0.5.6-ios.zip` | Apple Distribution Team-sign |
| Linux | `restore-privacy-client-0.5.6-linux-x64.tar.gz` | Native from this Mac |
| Windows | `restore-privacy-client-0.5.6-windows-x64-setup.exe` | CF until Windows-machine seal |
| Android | `restore-privacy-client-0.5.6-android.apk` | CF until Windows-machine seal |

## Operators

```bash
# Mac: Flutter + Apple package/sign + residual Team re-sign
cd client_app && flutter build macos --release && flutter build ios --release --no-codesign && cd ..
python3 scripts/build_release_0.5.6.py --apple-only

# Host Helsinki paid_assets (eu key)
export RPT_SSH_HOST=135.181.152.10 RPT_SSH_USER=root
export RPT_SSH_KEY=~/.ssh/id_ed25519_restore_privacy_eu
python3 scripts/host_paid_assets_vps.py --stage --upload --version 0.5.6 --force

# Residual Connect on build Mac (not catalog zip)
./scripts/open_macos_residual_connect.sh
```

See `client_app/APPLE_HANDOFF_0.5.6.md` and `client/windows/WINDOWS_HANDOFF_0.5.6.md`.
