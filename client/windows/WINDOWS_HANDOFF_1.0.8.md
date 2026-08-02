# Windows brand breadcrumbs — monopin 1.0.8

## Context

Mac stages Suite **1.0.8** with first-run **account → seed → licence** before residual permissions, then KEYGEN-free **72h trial** for Connect (device_pub host bind). After trial, KEYGEN required.

- **macOS**: Developer ID + notarize when notarytool succeeds  
- **iOS**: Distribution Team-signed Runner.app zip (inject residual pubs before zip)  
- **Android**: Flutter APK  
- **Windows / Linux**: carry-forward until this machine rebuilds Authenticode PE  

## On the Windows build machine

1. Sync monorepo (`client/VERSION` = `1.0.8`).
2. Build `restore-privacy-client-1.0.8-windows-x64-setup.exe`.
3. Authenticode-sign; stage to `status_page/assets/1.0.8/` and Helsinki paid upload.
4. `python3 scripts/breadcrumbs_vault.py stage --version 1.0.8`

## Target PE

```text
releases/1.0.8/restore-privacy-client-1.0.8-windows-x64-setup.exe
```
