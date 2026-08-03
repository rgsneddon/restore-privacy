# Windows + Linux/Arch handoff — monopin 1.1.5

**Audience:** Windows x64 build machine operator (and Arch/Linux rebuild agent).

**Catalog monopin:** `1.1.5` (`client/VERSION` must match).

## Product truth (1.1.5)

| Topic | Product |
|-------|---------|
| Shell | **Residual VPN only** — no Evolve / % / rpAI / Backup chrome |
| First-use | Licence (scroll-to-bottom) → KEYGEN **or** continue 72h trial → main VPN |
| Return | Trial remaining or KEYGEN required; **no** username/password |
| Quit | **Lower-left**; disconnect residual **then** full process exit |
| System tray | Exactly **`Privacy, Restored`** (comma + capital R) — durable forward monopin string |
| Self-update push | Fail-closed / removed |

## CRITICAL — Windows PE must be native-rebuilt on Windows

Mac agents **cannot** cross-build Windows PE (PyInstaller). Catalog basenames must **not** ship ancient PE payloads (e.g. `RestorePrivacy-0.5.8.exe` / pre-1.1.5 tray `rpT0`).

### Rebuild command (Windows x64 only)

```bat
git pull
type client\VERSION
rem must print 1.1.5

python scripts\build_windows_multihop.py --version 1.1.5
rem or: scripts\build_windows_multihop.bat

rem Authenticode-sign the produced setup EXE
rem Output:
rem   releases\1.1.5\restore-privacy-client-1.1.5-windows-x64-setup.exe
```

Readiness without build:

```bat
python scripts\build_windows_multihop.py --check-only --version 1.1.5
```

### Verify before upload

1. `TRAY_DISPLAY_NAME` in frozen tree / strings search shows **`Privacy, Restored`** (not `rpT0`, not uncomma'd `Privacy Restored`).
2. Quit is lower-left; disconnect then exit.
3. SHA-256 of signed setup differs from prior monopin carry-forward PE.
4. Upload via `python scripts/host_paid_assets_vps.py --stage --upload --version 1.1.5 --force`.

## Linux / Arch (done on Mac agent when packaging Python residual)

```bash
# pin
cat client/VERSION   # 1.1.5

python3 scripts/package_linux.py
# -> releases/1.1.5/restore-privacy-client-1.1.5-linux-x64.tar.gz

# install.sh desktop entry Name= must be exactly:
#   Privacy, Restored
```

Arch: use staged tree under `releases/1.1.5/arch` or `scripts/package_arch_linux.py` after Name= fix.

## macOS / iOS / Android

```bash
python3 scripts/build_suite_1.1.5.py
# or Flutter:
cd client_app && flutter build apk --release --build-name=1.1.5
cd client_app && flutter build macos --release --build-name=1.1.5
# codesign Developer ID; notarytool when credentials present
```

## Target basenames

```text
releases/1.1.5/restore-privacy-client-1.1.5-windows-x64-setup.exe
releases/1.1.5/restore-privacy-client-1.1.5-android.apk
releases/1.1.5/restore-privacy-client-1.1.5-macos.zip
releases/1.1.5/restore-privacy-client-1.1.5-ios.zip
releases/1.1.5/restore-privacy-client-1.1.5-linux-x64.tar.gz
```

Also: `status_page/assets/1.1.5/` and Helsinki `paid_assets/1.1.5/`.

## Residual fleet

IS + DE residual peers; US retired. KEYGEN / 72h device trial unchanged.
