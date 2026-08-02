# Windows brand breadcrumbs checklist — monopin 1.0.5

Generated: 2026-08-02T07:56:24Z
Large-drive dest: `{RPT_WINDOWS_DRIVE}` (configured=False, reachable=False)
Monorepo mirror path: `{RPT_WINDOWS_DRIVE}/restore-privacy`

## Operator mandate

- Duplicate the **full monorepo** and **every brand installer slot** onto the Windows larger drive (`RPT_WINDOWS_DRIVE` / `--dest`).
- **Native PE seal** for monopin **1.0.5** on this Windows machine (`scripts\\build_windows_multihop.py`).
- Upload sealed PE (+ brand packages as needed) to Helsinki `paid_assets/1.0.5/`.

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
| suite_client | Restore Privacy Suite | windows | `restore-privacy-client-1.0.5-windows-x64-setup.exe` | yes | — |
| suite_client | Restore Privacy Suite | android | `restore-privacy-client-1.0.5-android.apk` | yes | — |
| suite_client | Restore Privacy Suite | macos | `restore-privacy-client-1.0.5-macos.zip` | yes | — |
| suite_client | Restore Privacy Suite | ios | `restore-privacy-client-1.0.5-ios.zip` | yes | — |
| suite_client | Restore Privacy Suite | linux | `restore-privacy-client-1.0.5-linux-x64.tar.gz` | yes | — |
| browser | Browser Extension (MV3) | chromium | `restore-privacy-browser-extension-1.0.5.zip` | yes | — |
| browser | Rx Privacy Browser | default | `restore-privacy-rx-browser-1.0.5.zip` | yes | — |
| browser | Rx Privacy Browser | macos | `restore-privacy-rx-browser-1.0.5-macos.zip` | yes | — |
| browser | Rx Privacy Browser | windows | `restore-privacy-rx-browser-1.0.5-windows.zip` | yes | — |
| browser | Rx Privacy Browser | linux-x86_64 | `restore-privacy-rx-browser-1.0.5-linux-x86_64.tar.gz` | yes | — |
| browser | Rx Privacy Browser | linux-aarch64 | `restore-privacy-rx-browser-1.0.5-linux-aarch64.tar.gz` | yes | — |
| browser | Rx Privacy Browser | linux-x86_64-zip | `restore-privacy-rx-browser-1.0.5-linux-x86_64.zip` | yes | — |
| browser | Rx Privacy Browser | ios | `restore-privacy-rx-browser-1.0.5-ios.zip` | yes | — |
| browser | Rx Privacy Browser | android | `restore-privacy-rx-browser-1.0.5-android.zip` | yes | — |
| rpos | rpOS | windows | `rpos-0.2.1-windows-x64.zip` | yes | — |
| rpos | rpOS | macos | `rpos-0.2.1-macos.zip` | yes | — |
| rpos | rpOS | linux-x86_64 | `rpos-0.2.1-linux-x86_64.tar.gz` | yes | — |
| rpos | rpOS | linux-aarch64 | `rpos-0.2.1-linux-aarch64.tar.gz` | yes | — |
| rpos_app | Pens | pens | `pens-0.1.1-installer.zip` | yes | — |
| rpos_app | Tables | tables | `tables-0.1.1-installer.zip` | yes | — |
| rpos_app | Slides | slides | `slides-0.1.1-installer.zip` | yes | — |
| node_installer | Node Installer | linux | `restore-privacy-node-installer-1.0.1-linux-x64.tar.gz` | yes | — |
| node_installer | Node Installer | macos | `restore-privacy-node-installer-1.0.1-macos.zip` | yes | — |
| node_installer | Node Installer | windows | `restore-privacy-node-installer-1.0.1-windows-x64.zip` | yes | — |
| node_installer | Node Installer | android | `restore-privacy-node-installer-1.0.1-android.zip` | yes | — |
| node_installer | Node Installer | ios | `restore-privacy-node-installer-1.0.1-ios.zip` | yes | — |
| node_operator | Node Operator | linux | `restore-privacy-node-operator-1.0.1-linux-x64.tar.gz` | yes | — |
| rpmail | rpMail | windows | `rpmail-0.1.1-windows.zip` | yes | — |
| rpmail | rpMail | macos | `rpmail-0.1.1-macos.zip` | yes | — |
| rpmail | rpMail | linux-x86_64 | `rpmail-0.1.1-linux-x86_64.tar.gz` | yes | — |
| rpmail | rpMail | linux-aarch64 | `rpmail-0.1.1-linux-aarch64.tar.gz` | yes | — |
| rpoffice | rpOffice | windows | `rpoffice-0.1.1-windows.zip` | yes | — |
| rpoffice | rpOffice | macos | `rpoffice-0.1.1-macos.zip` | yes | — |
| rpoffice | rpOffice | linux-x86_64 | `rpoffice-0.1.1-linux-x86_64.tar.gz` | yes | — |
| rpoffice | rpOffice | linux-aarch64 | `rpoffice-0.1.1-linux-aarch64.tar.gz` | yes | — |

## Native Windows PE seal

- Script: `scripts/build_windows_multihop.py`
- Output: `releases/1.0.5/restore-privacy-client-1.0.5-windows-x64-setup.exe`
- Upload target: `paid_assets/1.0.5/`

```powershell
cd {RPT_WINDOWS_DRIVE}/restore-privacy
git pull
python scripts\build_windows_multihop.py
$env:RPT_SSH_HOST="135.181.152.10"
$env:RPT_SSH_USER="root"
$env:RPT_SSH_KEY="$HOME\.ssh\id_ed25519_restore_privacy_eu"
python scripts\host_paid_assets_vps.py --stage --upload --version 1.0.5 --force --install-serve
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
- Helsinki breadcrumbs: dist/breadcrumbs/current/WINDOWS_HANDOFF.md (monopin 1.0.5).
