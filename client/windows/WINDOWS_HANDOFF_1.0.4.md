# Windows brand breadcrumbs checklist — monopin 1.0.4

Generated: 2026-08-01
Monorepo pin: **1.0.4** (Suite free download; KEYGEN £3/month for Connect)

## Goal for Windows machine

Build, sign (Authenticode), stage, and upload **Windows** 1.0.4 packages only.
Mac operators skip Windows in admin package checkboxes — do not fail the job for missing Windows on Mac.

## Required Windows filenames (catalog 1.0.4)

| Product | Filename |
|---------|----------|
| Suite client | `restore-privacy-client-1.0.4-windows-x64-setup.exe` |
| Suite alias | `restore-privacy-suite-1.0.4-windows-x64-setup.exe` |
| Rx browser | `restore-privacy-rx-browser-1.0.4-windows.zip` |
| Browser extension | `restore-privacy-browser-extension-1.0.4.zip` (shared) |
| rpOS | `rpos-0.2.0-windows-x64.zip` |
| Node installer | `restore-privacy-node-installer-1.0.0-windows-x64.zip` |
| rpmail | `rpmail-0.1.0-windows.zip` |
| rpoffice | `rpoffice-0.1.0-windows.zip` |

## Steps (Windows machine)

1. Pull `main` from GitHub: `git pull origin main`
2. Confirm catalog pin: `python -c "import sys; sys.path.insert(0,'status_page'); from downloads import RELEASE_VERSION; print(RELEASE_VERSION)"` → **1.0.4**
3. Build Windows Suite installer (Flutter/Windows packaging path used for prior monopin):
   - Prefer native rebuild under `client_app` / Windows handoff scripts for 1.0.4
   - Output must land as `releases/1.0.4/restore-privacy-client-1.0.4-windows-x64-setup.exe`
4. Authenticode-sign the `.exe` with the product certificate (existing Windows seal process)
5. Stage: copy into `status_page/assets/1.0.4/`
6. Admin **Uploads** page (or CLI):
   - Tick **only Windows** packages in the per-package checkboxes
   - Stage + Upload to Helsinki (force optional)
   - Or CLI:  
     `python scripts/host_paid_assets_vps.py --version 1.0.4 --stage --upload --force --allow-missing`
7. Confirm remote:  
   `ssh root@135.181.152.10 ls -la /opt/restore-privacy/paid_assets/1.0.4/*windows*`

## Resource-lean defaults (do not regress)

- Startup launch: **off**
- Autoconnect on launch: **off**
- Traffic shaping / outer obfuscation / multi-hop: **off** by default

## CHECK BREADCRUMBS

When asked to “check breadcrumbs” on Windows, walk this file top to bottom and confirm each step’s artifact exists with non-zero size under `releases/1.0.4/` and `status_page/assets/1.0.4/`, then re-run selective upload of Windows rows only.
