# Windows handoff — catalog **0.4.2**

## Why this note exists
The operator laptop for this monorepo ship is **macOS**. A true Windows multihop residual **PE** freeze requires **Windows x64** + PyInstaller.

## Pin
1. Pins `client/VERSION` → `0.4.2`
2. Catalog `status_page/downloads.py` `RELEASE_VERSION` / `RELEASE_TAG` → `0.4.2`
3. Filename: `restore-privacy-client-0.4.2-windows-x64-setup.exe`

## Settings defaults (0.4.2)
Pre-adjustment (factory / missing keys):

| Control | Default |
|---------|---------|
| Run at startup | **Off** |
| Autoconnect on launch | **Off** |
| Residual VPN core | **Always on** (not a user-off toggle) |
| Traffic shaping | **Off** |
| Outer obfuscation | **Off** |
| Multi-hop | **Off** |

## Build on Windows x64
```bat
python scripts\build_windows_multihop.py
rem or:
scripts\build_windows_multihop.bat
rem or:
python scripts\build_release_0.4.2.py --windows-only
```

Then copy the setup into `releases/0.4.2/` and re-run assure / GH release asset upload.

## Residual privilege (no Run as admin every day)
Honest residual (Wintun + dual /1) **always needs OS privilege somewhere**.

Product UX (0.4.2+):
1. Desktop shortcut opens as a **standard user** (not “Run as administrator”).
2. **Connect** prompts UAC once to re-open elevated with `--rpt-auto-connect`, **or**
3. Settings → **Install residual helper (one-time Administrator)** registers a
   scheduled task (`RestorePrivacy\ResidualConnect`) so later Connect uses the
   helper without elevating the whole GUI via the shortcut.

There is **no** fully unprivileged residual public-IP capture on stock Windows.

## Dishonest claims to avoid
- Do **not** claim a Darwin-staged SFX pin rewrite is a full PE rebuild of multihop residual.
- Catalog 0.4.2 filename alone is not proof of native Windows code freeze.
- Do **not** claim residual honesty while skipping Wintun/routes without privilege.
