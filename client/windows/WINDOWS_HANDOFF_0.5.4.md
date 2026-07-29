# Windows handoff — Restore Privacy **0.5.4**

Catalog monopin: **0.5.4**

## Built this

| Platform | File | How |
|----------|------|-----|
| Windows | `restore-privacy-client-0.5.4-windows-x64-setup.exe` | **native** multihop PE (`build_release_0.5.4.py --windows-only` / `build_windows_multihop.py`) — includes `client.windows.window_foreground` |
| Linux | `restore-privacy-client-0.5.4-linux-x64.tar.gz` | CF residual-wire from **0.5.3** (filename monopin) |
| Android | `restore-privacy-client-0.5.4-android.apk` | CF residual-wire from **0.5.3** (filename monopin) |
| macOS / iOS | — | Helsinki breadcrumbs → Mac seal |

## Why 0.5.4 (Windows)

Frozen **0.5.3** installer crashed at import:

```text
ModuleNotFoundError: No module named 'client.windows.window_foreground'
```

**0.5.4** restores `client/windows/window_foreground.py`, pins it in the PyInstaller
recipe (`client.windows.window_foreground` hidden-import), and ships a fresh
Windows multihop setup.

## Update these docs

`RELEASE_NOTES_0.5.4.md`, README catalog tables, PRIVACY_POLICY monopin line,
`status_page/downloads.py` `RELEASE_VERSION` — all **0.5.4**.

## Publish all to **0.5.4**

Helsinki `paid_assets/0.5.4/` + `status_page/assets/0.5.4/`. Local staged under
`releases/0.5.4/`.

```powershell
python scripts\build_release_0.5.4.py --windows-only
# optional full non-Apple stage:
# python scripts\build_release_0.5.4.py --no-apple
python scripts\host_paid_assets_vps.py --stage --upload --version 0.5.4 --force
python scripts\breadcrumbs_vault.py publish --version 0.5.4
```
