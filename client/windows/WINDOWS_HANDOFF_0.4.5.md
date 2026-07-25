# Windows handoff — catalog **0.4.5**

## Why this note exists
The operator laptop for this monorepo ship is **macOS**. A true Windows multihop residual **PE** freeze requires **Windows x64** + PyInstaller.

## Pin
1. Pins `client/VERSION` → `0.4.5`
2. Catalog `status_page/downloads.py` `RELEASE_VERSION` / `RELEASE_TAG` → `0.4.5`
3. Filename: `restore-privacy-client-0.4.5-windows-x64-setup.exe`

## Settings defaults (0.4.5)
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
python scripts\build_release_0.4.5.py --windows-only
```

Then copy the setup into `releases/0.4.5/` and re-run assure / GH release asset upload.

## Residual privilege (no Run as admin every day)
Honest residual (Wintun + dual /1) **always needs OS privilege somewhere**.

Product UX (0.4.5+):
1. Desktop shortcut opens as a **standard user** (not “Run as administratorâ€).
2. **Connect** uses `connect_residual_privilege_dispatch()` when the GUI is
   non-admin — never falls through to `start_full_tunnel` as a standard user.
3. If the residual helper task is installed, Connect **always** runs
   `run_residual_helper_connect()` (schtasks `/Run` on
   `RestorePrivacy\ResidualConnect`). It does **not** skip that path just
   because `product_connect_requires_admin_process()` is False (that flag only
   means “this window need not elevateâ€).
4. Without a helper, Connect prompts UAC once to re-open elevated with
   `--rpt-auto-connect`.
5. Settings → **Install residual helper (one-time Administrator)** registers the
   scheduled task so later Connects use the helper without elevating the whole
   GUI via the shortcut.

There is **no** fully unprivileged residual public-IP capture on stock Windows.

## Dishonest claims to avoid
- Do **not** claim a Darwin-staged SFX pin rewrite is a full PE rebuild of multihop residual.
- Catalog 0.4.5 filename alone is not proof of native Windows code freeze.
- Do **not** claim residual honesty while skipping Wintun/routes without privilege.

