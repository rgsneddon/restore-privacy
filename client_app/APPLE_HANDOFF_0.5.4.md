# Apple handoff — Restore Privacy **0.5.4**

**Monopin / this build:** `0.5.4`

## Built this (Windows host)

| Platform | Filename | Status |
|----------|----------|--------|
| Windows | `restore-privacy-client-0.5.4-windows-x64-setup.exe` | **native** multihop PE (`window_foreground` freeze fix) |
| Linux | `restore-privacy-client-0.5.4-linux-x64.tar.gz` | CF residual-wire from 0.5.3 (filename monopin) |
| Android | `restore-privacy-client-0.5.4-android.apk` | CF residual-wire from 0.5.3 (filename monopin) |
| macOS | `restore-privacy-client-0.5.4-macos.zip` | **Mac native seal required** (CFBundle must = 0.5.4) |
| iOS | `restore-privacy-client-0.5.4-ios.zip` | **Mac Team-sign required** |

Catalog pin and filenames are **0.5.4** for all five platforms. Apple zips were
**not** present as 0.5.4 on the Windows host at ship time — rebuild on Darwin.
Do **not** rename an older zip and claim native 0.5.4 (CFBundle monopin must match).

## Why 0.5.4

Windows frozen client 0.5.3 crashed:

```text
ModuleNotFoundError: No module named 'client.windows.window_foreground'
```

0.5.4 restores the module and ships a fresh Windows setup. Apple platforms still
need a Mac-native seal under monopin **0.5.4**.

## Publish under monopin **0.5.4**

- Helsinki paid assets: `/opt/restore-privacy/paid_assets/0.5.4/`
- Status assets: `status_page/assets/0.5.4/` (Win/Linux/Android staged from Windows host)
- Breadcrumbs vault: `/opt/restore-privacy/breadcrumbs/current` + `breadcrumbs/0.5.4/`

### Mac rebuild

```bash
cd client_app
flutter build macos --release
flutter build ios --no-codesign
# inject secrets + sign/notarize per APPLE_BUILD.md
python3 scripts/build_release_0.5.4.py --apple-only
# then stage+upload Apple zips:
python3 scripts/host_paid_assets_vps.py --stage --upload --version 0.5.4 --force
python3 scripts/breadcrumbs_vault.py publish --version 0.5.4
```

### Breadcrumbs (this vault)

```bash
python scripts/breadcrumbs_vault.py stage --version 0.5.4
python scripts/breadcrumbs_vault.py publish --version 0.5.4
python scripts/breadcrumbs_vault.py check --fetch
```


## Mac native seal completed (2026-07-29T13:34Z)

| Platform | Filename | Status |
|----------|----------|--------|
| macOS | `restore-privacy-client-0.5.4-macos.zip` | **native** monopin **0.5.4** — `CFBundleShortVersionString` **0.5.4**; Developer ID + **notarized + stapled** |
| iOS | `restore-privacy-client-0.5.4-ios.zip` | **native** monopin **0.5.4** — Team-signed (**Apple Distribution** SFCBP95595) sideload |

Built on Darwin via:

```bash
cd client_app && flutter build macos --release
cd client_app && flutter build ios --release --no-codesign
python3 scripts/build_release_0.5.4.py --apple-only
```

Artifacts: `releases/0.5.4/restore-privacy-client-0.5.4-macos.zip` and
`releases/0.5.4/restore-privacy-client-0.5.4-ios.zip` (+ SHA256SUMS.json).
