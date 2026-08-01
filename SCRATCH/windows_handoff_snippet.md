# WINDOWS_HANDOFF brand-mirror snippet

41:python scripts\build_windows_multihop.py
42-# Or suite-focused path if present:
43-# python scripts\build_suite_1.0.2.py
44-# python scripts\build_release_1.0.2.py --windows-only
--
103:$env:RPT_WINDOWS_DRIVE = "D:\RestorePrivacyMirror"
104:python scripts\windows_brand_mirror.py plan
105:python scripts\windows_brand_mirror.py apply --dest $env:RPT_WINDOWS_DRIVE --execute
106-```
107-
108-Vault files after `python scripts\breadcrumbs_vault.py stage`:
--
111:- `dist/breadcrumbs/current/windows_brand_mirror.json`
112-- `releases/1.0.2/WINDOWS_BREADCRUMBS.md`
113-
114-## Breadcrumbs vault
--
146:## Brand-wide large-drive mirror (all installer slots)
147-
148-The Windows **larger drive** must hold a working monorepo copy **and** every brand
149-asset from the inventory — not only the Suite Windows setup.exe.
--
153:| **Env** | `RPT_WINDOWS_DRIVE` (or `--dest`) = large-drive root |
154:| **Monorepo dest** | `{RPT_WINDOWS_DRIVE}/restore-privacy` |
155-| **Brand slots** | **35** (browser, node_installer, node_operator, rpmail, rpoffice, rpos, rpos_app, suite_client) |
156-| **Monopin** | **1.0.2** |
157-
--
159:$env:RPT_WINDOWS_DRIVE = "D:\RestorePrivacyMirror"   # larger drive
160:python scripts\windows_brand_mirror.py plan
161:python scripts\windows_brand_mirror.py apply --dest $env:RPT_WINDOWS_DRIVE
162-```
163-
164-Inventory kinds covered: suite_client, browser/Rx, rpos, rpos_app (Pens/Tables/Slides),
--
167:Full checklist: vault `WINDOWS_BRAND_CHECKLIST.md` / `windows_brand_mirror.json`
168-(after `python scripts\breadcrumbs_vault.py stage`).
169-
170:Native PE remains required: `scripts\build_windows_multihop.py` →
171-`releases\1.0.2\restore-privacy-client-1.0.2-windows-x64-setup.exe`.

--- WINDOWS_BRAND_CHECKLIST head ---
# Windows brand breadcrumbs checklist — monopin 1.0.2

Generated: 2026-08-01T07:50:36Z
Large-drive dest: `{RPT_WINDOWS_DRIVE}` (configured=False, reachable=False)
Monorepo mirror path: `{RPT_WINDOWS_DRIVE}/restore-privacy`

## Operator mandate

- Duplicate the **full monorepo** and **every brand installer slot** onto the Windows larger drive (`RPT_WINDOWS_DRIVE` / `--dest`).
- **Native PE seal** for monopin **1.0.2** on this Windows machine (`scripts\\build_windows_multihop.py`).
- Upload sealed PE (+ brand packages as needed) to Helsinki `paid_assets/1.0.2/`.

## Large-drive mirror

```powershell
# Prefer env on the large drive root, e.g. D:\RestorePrivacyMirror
$env:RPT_WINDOWS_DRIVE = "D:\RestorePrivacyMirror"
python scripts\windows_brand_mirror.py plan
python scripts\windows_brand_mirror.py apply --dest $env:RPT_WINDOWS_DRIVE
```

Brand slots in inventory: **35** (kinds: browser, node_installer, node_operator, rpmail, rpoffice, rpos, rpos_app, suite_client)
Present on source host: **35** / 35  ·  Missing source: **0**  ·  Already on dest: **0**

## Brand inventory (all installer slots)

| Kind | Product | Platform | Filename | Source | Dest |
|------|---------|----------|----------|--------|------|
| suite_client | Restore Privacy Suite | windows | `restore-privacy-client-1.0.2-windows-x64-setup.exe` | yes | — |
| suite_client | Restore Privacy Suite | android | `restore-privacy-client-1.0.2-android.apk` | yes | — |
| suite_client | Restore Privacy Suite | macos | `restore-privacy-client-1.0.2-macos.zip` | yes | — |
| suite_client | Restore Privacy Suite | ios | `restore-privacy-client-1.0.2-ios.zip` | yes | — |
| suite_client | Restore Privacy Suite | linux | `restore-privacy-client-1.0.2-linux-x64.tar.gz` | yes | — |
| browser | Browser Extension (MV3) | chromium | `restore-privacy-browser-extension-1.0.2.zip` | yes | — |
| browser | Rx Privacy Browser | default | `restore-privacy-rx-browser-1.0.2.zip` | yes | — |
| browser | Rx Privacy Browser | macos | `restore-privacy-rx-browser-1.0.2-macos.zip` | yes | — |
| browser | Rx Privacy Browser | windows | `restore-privacy-rx-browser-1.0.2-windows.zip` | yes | — |
| browser | Rx Privacy Browser | linux-x86_64 | `restore-privacy-rx-browser-1.0.2-linux-x86_64.tar.gz` | yes | — |
| browser | Rx Privacy Browser | linux-aarch64 | `restore-privacy-rx-browser-1.0.2-linux-aarch64.tar.gz` | yes | — |
| browser | Rx Privacy Browser | linux-x86_64-zip | `restore-privacy-rx-browser-1.0.2-linux-x86_64.zip` | yes | — |
| browser | Rx Privacy Browser | ios | `restore-privacy-rx-browser-1.0.2-ios.zip` | yes | — |
| browser | Rx Privacy Browser | android | `restore-privacy-rx-browser-1.0.2-android.zip` | yes | — |
| rpos | rpOS | windows | `rpos-0.2.0-windows-x64.zip` | yes | — |
| rpos | rpOS | macos | `rpos-0.2.0-macos.zip` | yes | — |
| rpos | rpOS | linux-x86_64 | `rpos-0.2.0-linux-x86_64.tar.gz` | yes | — |
| rpos | rpOS | linux-aarch64 | `rpos-0.2.0-linux-aarch64.tar.gz` | yes | — |
| rpos_app | Pens | pens | `pens-0.1.0-installer.zip` | yes | — |
| rpos_app | Tables | tables | `tables-0.1.0-installer.zip` | yes | — |
| rpos_app | Slides | slides | `slides-0.1.0-installer.zip` | yes | — |
| node_installer | Node Installer | linux | `restore-privacy-node-installer-1.0.0-linux-x64.tar.gz` | yes | — |
| node_installer | Node Installer | macos | `restore-privacy-node-installer-1.0.0-macos.zip` | yes | — |
| node_installer | Node Installer | windows | `restore-privacy-node-installer-1.0.0-windows-x64.zip` | yes | — |
| node_installer | Node Installer | android | `restore-privacy-node-installer-1.0.0-android.zip` | yes | — |
| node_installer | Node Installer | ios | `restore-privacy-node-installer-1.0.0-ios.zip` | yes | — |
| node_operator | Node Operator | linux | `restore-privacy-node-operator-1.0.0-linux-x64.tar.gz` | yes | — |
| rpmail | rpMail | windows | `rpmail-0.1.0-windows.zip` | yes | — |
| rpmail | rpMail | macos | `rpmail-0.1.0-macos.zip` | yes | — |
| rpmail | rpMail | linux-x86_64 | `rpmail-0.1.0-linux-x86_64.tar.gz` | yes | — |
| rpmail | rpMail | linux-aarch64 | `rpmail-0.1.0-linux-aarch64.tar.gz` | yes | — |
| rpoffice | rpOffice | windows | `rpoffice-0.1.0-windows.zip` | yes | — |

--- releases WINDOWS_BREADCRUMBS head ---
# Windows brand breadcrumbs checklist — monopin 1.0.2

Generated: 2026-08-01T07:50:36Z
Large-drive dest: `{RPT_WINDOWS_DRIVE}` (configured=False, reachable=False)
Monorepo mirror path: `{RPT_WINDOWS_DRIVE}/restore-privacy`

## Operator mandate

- Duplicate the **full monorepo** and **every brand installer slot** onto the Windows larger drive (`RPT_WINDOWS_DRIVE` / `--dest`).
- **Native PE seal** for monopin **1.0.2** on this Windows machine (`scripts\\build_windows_multihop.py`).
- Upload sealed PE (+ brand packages as needed) to Helsinki `paid_assets/1.0.2/`.

## Large-drive mirror

```powershell
# Prefer env on the large drive root, e.g. D:\RestorePrivacyMirror
$env:RPT_WINDOWS_DRIVE = "D:\RestorePrivacyMirror"
python scripts\windows_brand_mirror.py plan
python scripts\windows_brand_mirror.py apply --dest $env:RPT_WINDOWS_DRIVE
```

Brand slots in inventory: **35** (kinds: browser, node_installer, node_operator, rpmail, rpoffice, rpos, rpos_app, suite_client)
Present on source host: **35** / 35  ·  Missing source: **0**  ·  Already on dest: **0**

## Brand inventory (all installer slots)

| Kind | Product | Platform | Filename | Source | Dest |
|------|---------|----------|----------|--------|------|
| suite_client | Restore Privacy Suite | windows | `restore-privacy-client-1.0.2-windows-x64-setup.exe` | yes | — |
| suite_client | Restore Privacy Suite | android | `restore-privacy-client-1.0.2-android.apk` | yes | — |
| suite_client | Restore Privacy Suite | macos | `restore-privacy-client-1.0.2-macos.zip` | yes | — |
| suite_client | Restore Privacy Suite | ios | `restore-privacy-client-1.0.2-ios.zip` | yes | — |
| suite_client | Restore Privacy Suite | linux | `restore-privacy-client-1.0.2-linux-x64.tar.gz` | yes | — |
| browser | Browser Extension (MV3) | chromium | `restore-privacy-browser-extension-1.0.2.zip` | yes | — |
| browser | Rx Privacy Browser | default | `restore-privacy-rx-browser-1.0.2.zip` | yes | — |
| browser | Rx Privacy Browser | macos | `restore-privacy-rx-browser-1.0.2-macos.zip` | yes | — |
| browser | Rx Privacy Browser | windows | `restore-privacy-rx-browser-1.0.2-windows.zip` | yes | — |
| browser | Rx Privacy Browser | linux-x86_64 | `restore-privacy-rx-browser-1.0.2-linux-x86_64.tar.gz` | yes | — |
| browser | Rx Privacy Browser | linux-aarch64 | `restore-privacy-rx-browser-1.0.2-linux-aarch64.tar.gz` | yes | — |
| browser | Rx Privacy Browser | linux-x86_64-zip | `restore-privacy-rx-browser-1.0.2-linux-x86_64.zip` | yes | — |
