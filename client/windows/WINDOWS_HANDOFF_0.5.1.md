# Windows handoff — Restore Privacy 0.5.1

Catalog monopin: **0.5.1**

Breadcrumbs for completing **non-Apple** (and Windows PE) packages on a **Windows x64** computer after the Mac ship of Apple residual + monopin pin.

## Already done on Mac (this goal)

- Product monopin **0.5.1** (`client/VERSION`, `status_page/downloads.py` `RELEASE_VERSION`, Flutter `productVersion` / pubspec)
- Discrete **Quit** on Flutter main connection screen (macOS + iOS): tunnel stop → process exit
- Keygen version-agnostic unlock + multi-platform “New version available” banner (prior work in tree)
- Apple packages built via `scripts/build_release_0.5.1.py --apple-only` when Flutter build succeeds
- Docs: `client_app/APPLE_HANDOFF_0.5.1.md`, `scripts/RELEASE_NOTES_0.5.1.md`

## Remaining on Windows computer

| Package | Filename | How to build |
|---------|----------|--------------|
| Windows PE | `restore-privacy-client-0.5.1-windows-x64-setup.exe` | `python scripts/build_windows_multihop.py` **or** `python scripts/build_release_0.5.1.py --windows-only` (x64 only) |
| Linux | `restore-privacy-client-0.5.1-linux-x64.tar.gz` | `python scripts/build_release_0.5.1.py` (Linux package path) or carry-forward from prior pin if rebuild unavailable — prefer **native** rebuild |
| Android | `restore-privacy-client-0.5.1-android.apk` | Flutter Android release when SDK present; else honest CF rename from prior residual-wire APK |

## Exact commands (Windows)

```bat
cd restore-privacy
git pull
type client\VERSION
python scripts\build_release_0.5.1.py --windows-only
python scripts\build_windows_multihop.py
REM full catalog stage when all platforms ready:
python scripts\build_release_0.5.1.py
set RPT_SSH_USER=raskul
set RPT_SSH_SUDO=1
python scripts\host_paid_assets_vps.py --stage --upload --version 0.5.1 --force
```

## Pin checks before publish

```bat
type client\VERSION
findstr RELEASE_VERSION status_page\downloads.py
findstr productVersion client_app\lib\rpt_config.dart
dir releases\0.5.1
```

## Product notes for Windows UI (optional parity)

- Desktop Windows already has Disconnect / window close semantics; Flutter **Quit** is Apple residual main-screen only.
- Ensure paid **Get update** opens absolute `https://restoreprivacy.online/pay?platform=windows…` (not relative `/pay`).
- Same keygen re-applies after upgrading to 0.5.1 while subscription is active.

## VPS path

`/opt/restore-privacy/paid_assets/0.5.1/`

## Git breadcrumbs

- Release script: `scripts/build_release_0.5.1.py`
- Release notes: `scripts/RELEASE_NOTES_0.5.1.md`
- Apple handoff: `client_app/APPLE_HANDOFF_0.5.1.md`
- This file: `client/windows/WINDOWS_HANDOFF_0.5.1.md`
