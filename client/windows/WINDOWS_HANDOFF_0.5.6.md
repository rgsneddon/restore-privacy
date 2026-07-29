# Windows handoff — Restore Privacy **0.5.6**

Catalog monopin: **0.5.6**

## Split ship (0.5.6)

| Platform | Who | File / host path |
|----------|-----|------------------|
| **macOS / iOS / Linux** | Mac | Helsinki `paid_assets/0.5.6/…-macos.zip`, `…-ios.zip`, `…-linux-x64.tar.gz` (already hosted from Darwin) |
| **Windows / Android** | **This Windows machine** | Native PE + APK → re-upload same monopin basenames |

Do **not** leave Darwin carry-forward Win/Android as the final paid seal.

## Build + host (Windows machine)

```powershell
python scripts\build_release_0.5.6.py --windows-only
# Android native APK when ready, then:
$env:RPT_SSH_HOST="135.181.152.10"
$env:RPT_SSH_USER="root"
$env:RPT_SSH_KEY="$HOME\.ssh\id_ed25519_restore_privacy_eu"   # or store key that works as root@Helsinki
python scripts\host_paid_assets_vps.py --stage --upload --version 0.5.6 --force
```

## Fixes carried in monopin 0.5.6 tree

- Connect: `client.windows.hidden_subprocess` (configure_address)
- Settings: IPv4 residual + IPv6 residual are the **top** switches in privacy scale
