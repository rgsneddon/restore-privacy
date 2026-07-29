# Release notes — Restore Privacy **0.5.4**

**Catalog monopin:** 0.5.4  
**Paid installers:** Windows **native** this ship. Linux/Android honest **CF** from 0.5.3 monopin filenames. macOS/iOS after Mac seal (Helsinki breadcrumbs).

## Highlights

- **Windows freeze fix:** restore `client.windows.window_foreground` so the setup no longer dies with `ModuleNotFoundError: No module named 'client.windows.window_foreground'` (import used by `client/windows/app.py`).
- **PyInstaller:** `--hidden-import client.windows.window_foreground` in `scripts/build_release_0.0.8.py`; multihop readiness check requires the module file.
- **Fresh Windows multihop PE** built on Windows x64 via `build_release_0.5.4.py --windows-only` / `build_windows_multihop.py`.

## Packages

| Platform | File | Notes |
|----------|------|--------|
| Windows | `restore-privacy-client-0.5.4-windows-x64-setup.exe` | **native** multihop PE |
| Linux | `restore-privacy-client-0.5.4-linux-x64.tar.gz` | CF from 0.5.3 |
| Android | `restore-privacy-client-0.5.4-android.apk` | CF from 0.5.3 |
| macOS | `restore-privacy-client-0.5.4-macos.zip` | Mac seal when available |
| iOS | `restore-privacy-client-0.5.4-ios.zip` | Mac Team-sign when available |

## Operators

```bash
python scripts/build_release_0.5.4.py --windows-only   # Win host, native PE
python scripts/build_release_0.5.4.py --no-apple       # optional full non-Apple stage
python scripts/host_paid_assets_vps.py --stage --upload --version 0.5.4 --force
python scripts/breadcrumbs_vault.py publish --version 0.5.4
python scripts/run_security_audit.py --write
```
