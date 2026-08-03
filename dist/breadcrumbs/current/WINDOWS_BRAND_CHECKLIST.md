# Windows brand breadcrumbs checklist — monopin 1.1.7

Generated: 2026-08-03T22:56:42Z
Large-drive dest: `{RPT_WINDOWS_DRIVE}` (configured=False, reachable=False)
Monorepo mirror path: `{RPT_WINDOWS_DRIVE}/restore-privacy`

## Operator mandate

- Duplicate the **full monorepo** and **every brand installer slot** onto the Windows larger drive (`RPT_WINDOWS_DRIVE` / `--dest`).
- **Native PE seal** for monopin **1.1.7** on this Windows machine (`scripts\\build_windows_multihop.py`).
- Upload sealed PE (+ brand packages as needed) to Helsinki `paid_assets/1.1.7/`.

## Large-drive mirror

```powershell
# Prefer env on the large drive root, e.g. D:\RestorePrivacyMirror
$env:RPT_WINDOWS_DRIVE = "D:\RestorePrivacyMirror"
python scripts\windows_brand_mirror.py plan
python scripts\windows_brand_mirror.py apply --dest $env:RPT_WINDOWS_DRIVE
```

Brand slots in inventory: **35** (kinds: browser, node_installer, node_operator, rpmail, rpoffice, rpos, rpos_app, suite_client)
Present on source host: **5** / 35  ·  Missing source: **30**  ·  Already on dest: **0**

## Brand inventory (all installer slots)

| Kind | Product | Platform | Filename | Source | Dest |
|------|---------|----------|----------|--------|------|
| suite_client | Restore Privacy Suite | windows | `restore-privacy-client-1.1.7-windows-x64-setup.exe` | yes | — |
| suite_client | Restore Privacy Suite | android | `restore-privacy-client-1.1.7-android.apk` | yes | — |
| suite_client | Restore Privacy Suite | macos | `restore-privacy-client-1.1.7-macos.zip` | yes | — |
| suite_client | Restore Privacy Suite | ios | `restore-privacy-client-1.1.7-ios.zip` | yes | — |
| suite_client | Restore Privacy Suite | linux | `restore-privacy-client-1.1.7-linux-x64.tar.gz` | yes | — |
| browser | Browser Extension (MV3) | chromium | `restore-privacy-browser-extension-1.1.7.zip` | MISSING | — |
| browser | Rx Privacy Browser | default | `restore-privacy-rx-browser-1.1.7.zip` | MISSING | — |
| browser | Rx Privacy Browser | macos | `restore-privacy-rx-browser-1.1.7-macos.zip` | MISSING | — |
| browser | Rx Privacy Browser | windows | `restore-privacy-rx-browser-1.1.7-windows.zip` | MISSING | — |
| browser | Rx Privacy Browser | linux-x86_64 | `restore-privacy-rx-browser-1.1.7-linux-x86_64.tar.gz` | MISSING | — |
| browser | Rx Privacy Browser | linux-aarch64 | `restore-privacy-rx-browser-1.1.7-linux-aarch64.tar.gz` | MISSING | — |
| browser | Rx Privacy Browser | linux-x86_64-zip | `restore-privacy-rx-browser-1.1.7-linux-x86_64.zip` | MISSING | — |
| browser | Rx Privacy Browser | ios | `restore-privacy-rx-browser-1.1.7-ios.zip` | MISSING | — |
| browser | Rx Privacy Browser | android | `restore-privacy-rx-browser-1.1.7-android.zip` | MISSING | — |
| rpos | rpOS | windows | `rpos-0.2.1-windows-x64.zip` | MISSING | — |
| rpos | rpOS | macos | `rpos-0.2.1-macos.zip` | MISSING | — |
| rpos | rpOS | linux-x86_64 | `rpos-0.2.1-linux-x86_64.tar.gz` | MISSING | — |
| rpos | rpOS | linux-aarch64 | `rpos-0.2.1-linux-aarch64.tar.gz` | MISSING | — |
| rpos_app | Pens | pens | `pens-0.1.1-installer.zip` | MISSING | — |
| rpos_app | Tables | tables | `tables-0.1.1-installer.zip` | MISSING | — |
| rpos_app | Slides | slides | `slides-0.1.1-installer.zip` | MISSING | — |
| node_installer | Node Installer | linux | `restore-privacy-node-installer-1.0.1-linux-x64.tar.gz` | MISSING | — |
| node_installer | Node Installer | macos | `restore-privacy-node-installer-1.0.1-macos.zip` | MISSING | — |
| node_installer | Node Installer | windows | `restore-privacy-node-installer-1.0.1-windows-x64.zip` | MISSING | — |
| node_installer | Node Installer | android | `restore-privacy-node-installer-1.0.1-android.zip` | MISSING | — |
| node_installer | Node Installer | ios | `restore-privacy-node-installer-1.0.1-ios.zip` | MISSING | — |
| node_operator | Node Operator | linux | `restore-privacy-node-operator-1.0.1-linux-x64.tar.gz` | MISSING | — |
| rpmail | rpMail | windows | `rpmail-0.1.1-windows.zip` | MISSING | — |
| rpmail | rpMail | macos | `rpmail-0.1.1-macos.zip` | MISSING | — |
| rpmail | rpMail | linux-x86_64 | `rpmail-0.1.1-linux-x86_64.tar.gz` | MISSING | — |
| rpmail | rpMail | linux-aarch64 | `rpmail-0.1.1-linux-aarch64.tar.gz` | MISSING | — |
| rpoffice | rpOffice | windows | `rpoffice-0.1.1-windows.zip` | MISSING | — |
| rpoffice | rpOffice | macos | `rpoffice-0.1.1-macos.zip` | MISSING | — |
| rpoffice | rpOffice | linux-x86_64 | `rpoffice-0.1.1-linux-x86_64.tar.gz` | MISSING | — |
| rpoffice | rpOffice | linux-aarch64 | `rpoffice-0.1.1-linux-aarch64.tar.gz` | MISSING | — |

## Native Windows PE seal

- Script: `scripts/build_windows_multihop.py`
- Output: `releases/1.1.7/restore-privacy-client-1.1.7-windows-x64-setup.exe`
- Upload target: `paid_assets/1.1.7/`

```powershell
cd {RPT_WINDOWS_DRIVE}/restore-privacy
git pull
python scripts\build_windows_multihop.py
$env:RPT_SSH_HOST="135.181.152.10"
$env:RPT_SSH_USER="root"
$env:RPT_SSH_KEY="$HOME\.ssh\id_ed25519_restore_privacy_eu"
python scripts\host_paid_assets_vps.py --stage --upload --version 1.1.7 --force --install-serve
```

## Steps

1. Mount/set large drive → `RPT_WINDOWS_DRIVE`
2. `python scripts\windows_brand_mirror.py apply` (repos + brand binaries)
3. Verify monorepo markers + brand files on the drive
4. Build native PE; re-apply mirror so the seal lands on the large drive
5. Upload to Helsinki; `python scripts\breadcrumbs_vault.py stage` / publish

## Notes

- Set RPT_WINDOWS_DRIVE to the large Windows drive root (or pass --dest).
- Mirror monorepo + all brand installers before native PE rebuild.
- Native PE seal must run on Windows; replace carry-forward PE before final ship.
- After PE build, re-run brand mirror apply so the large drive holds the seal.
- Helsinki breadcrumbs: dist/breadcrumbs/current/WINDOWS_HANDOFF.md (monopin 1.1.7).
