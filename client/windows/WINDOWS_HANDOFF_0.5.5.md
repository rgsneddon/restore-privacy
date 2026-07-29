# Windows handoff — Restore Privacy **0.5.5**

Catalog monopin: **0.5.5**

## Built this

| Platform | File | How |
|----------|------|-----|
| Windows | `restore-privacy-client-0.5.5-windows-x64-setup.exe` | **native** multihop PE — includes `hidden_subprocess` + dual-stack Settings top |
| Linux / Android / Apple | monopin filenames | CF or Mac seal as staged |

## Fixes

- Connect: restore `client.windows.hidden_subprocess` (was ModuleNotFoundError on `configure_address`)
- Settings: IPv4 residual + IPv6 residual are the **top** switches in Browsing speed / privacy scale

## Build

```powershell
python scripts\build_release_0.5.5.py --windows-only
python scripts\host_paid_assets_vps.py --stage --upload --version 0.5.5 --force --allow-missing
```
