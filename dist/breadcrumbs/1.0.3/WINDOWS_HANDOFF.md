# Windows brand breadcrumbs checklist — monopin 1.0.3

Generated: 2026-08-01
Monorepo pin: **1.0.3** (Suite free download; KEYGEN £3/month for Connect)

## Goal for Windows machine

Build, sign (Authenticode), stage, and upload **Windows** 1.0.3 packages only.
Mac operators skip Windows in admin package checkboxes — do not fail the job for missing Windows on Mac.

## Required Windows filenames (catalog 1.0.3)

| Product | Filename |
|---------|----------|
| Suite client | `restore-privacy-client-1.0.3-windows-x64-setup.exe` |
| Suite alias | `restore-privacy-suite-1.0.3-windows-x64-setup.exe` |
| Rx browser | `restore-privacy-rx-browser-1.0.3-windows.zip` |
| Browser extension | `restore-privacy-browser-extension-1.0.3.zip` (shared) |
| rpOS | `rpos-0.2.0-windows-x64.zip` |
| Node installer | `restore-privacy-node-installer-1.0.0-windows-x64.zip` |
| rpmail | `rpmail-0.1.0-windows.zip` |
| rpoffice | `rpoffice-0.1.0-windows.zip` |

## Steps (Windows machine)

1. Pull `main` from GitHub: `git pull origin main`
2. Confirm catalog pin: `python -c "import sys; sys.path.insert(0,'status_page'); from downloads import RELEASE_VERSION; print(RELEASE_VERSION)"` → **1.0.3**
3. Build Windows Suite installer (Flutter/Windows packaging path used for prior monopin):
   - Prefer native rebuild under `client_app` / Windows handoff scripts for 1.0.3
   - Output must land as `releases/1.0.3/restore-privacy-client-1.0.3-windows-x64-setup.exe`
4. Authenticode-sign the `.exe` with the product certificate (existing Windows seal process)
5. Stage: copy into `status_page/assets/1.0.3/`
6. Admin **Uploads** page (or CLI):
   - Tick **only Windows** packages in the per-package checkboxes
   - Stage + Upload to Helsinki (force optional)
   - Or CLI:  
     `python scripts/host_paid_assets_vps.py --version 1.0.3 --stage --upload --force --allow-missing`
7. Confirm remote:  
   `ssh root@135.181.152.10 ls -la /opt/restore-privacy/paid_assets/1.0.3/*windows*`

## Resource-lean defaults (do not regress)

- Startup launch: **off**
- Autoconnect on launch: **off**
- Traffic shaping / outer obfuscation / multi-hop: **off** by default

## CHECK BREADCRUMBS

When asked to “check breadcrumbs” on Windows, walk this file top to bottom and confirm each step’s artifact exists with non-zero size under `releases/1.0.3/` and `status_page/assets/1.0.3/`, then re-run selective upload of Windows rows only.

---

> **Breadcrumbs vault (Helsinki)** is the source of truth for “what to update” on this monopin. Do **not** treat a private GitHub pull of this file as the primary task queue.
> Fetch: `https://135.181.152.10.sslip.io/breadcrumbs/current/manifest.json` with `X-RPT-Asset-Token`.

---

## Brand-wide large-drive mirror (all installer slots)

The Windows **larger drive** must hold a working monorepo copy **and** every brand
asset from the inventory — not only the Suite Windows setup.exe.

| | |
|--|--|
| **Env** | `RPT_WINDOWS_DRIVE` (or `--dest`) = large-drive root |
| **Monorepo dest** | `{RPT_WINDOWS_DRIVE}/restore-privacy` |
| **Brand slots** | **35** (browser, node_installer, node_operator, rpmail, rpoffice, rpos, rpos_app, suite_client) |
| **Monopin** | **1.0.3** |

```powershell
$env:RPT_WINDOWS_DRIVE = "D:\RestorePrivacyMirror"   # larger drive
python scripts\windows_brand_mirror.py plan
python scripts\windows_brand_mirror.py apply --dest $env:RPT_WINDOWS_DRIVE
```

Inventory kinds covered: suite_client, browser/Rx, rpos, rpos_app (Pens/Tables/Slides),
node_installer, node_operator, rpmail, rpoffice.

Full checklist: vault `WINDOWS_BRAND_CHECKLIST.md` / `windows_brand_mirror.json`
(after `python scripts\breadcrumbs_vault.py stage`).

Native PE remains required: `scripts\build_windows_multihop.py` →
`releases\1.0.3\restore-privacy-client-1.0.3-windows-x64-setup.exe`.
