# Apple handoff — Restore Privacy **0.5.2**

**Monopin / this build:** `0.5.2`

## Built this (already done on Windows host)

| Platform | Filename | Status |
|----------|----------|--------|
| Windows | `restore-privacy-client-0.5.2-windows-x64-setup.exe` | Built/staged this ship |
| Linux | `restore-privacy-client-0.5.2-linux-x64.tar.gz` | Built/staged this ship |
| Android | `restore-privacy-client-0.5.2-android.apk` | Built/staged this ship |
| macOS | `restore-privacy-client-0.5.2-macos.zip` | **Mac native seal required** |
| iOS | `restore-privacy-client-0.5.2-ios.zip` | **Mac Team-sign required** |

## Update these docs (to monopin **0.5.2**)

- This file: `client_app/APPLE_HANDOFF_0.5.2.md`
- `scripts/RELEASE_NOTES_0.5.2.md` / `status_page/public/RELEASE_NOTES_0.5.2.md`
- `PRIVACY_POLICY.md` (catalog pin line)
- `AUDIT.md` / `status_page/public/AUDIT.md` (catalog package table)
- `status_page/settings_explainer.py` (Settings guide posture)
- `status_page/downloads.py` `RELEASE_VERSION` / `client/VERSION` / Flutter `pubspec.yaml`

## Publish all to the version number of this build (**0.5.2**)

Stage/upload **every** platform package under:

- Helsinki: `/opt/restore-privacy/paid_assets/0.5.2/`
- Status: `status_page/assets/0.5.2/`

Do **not** invent another version number. Do **not** wait for a separate “commit the pin” command — monopin is **0.5.2** for this build.

### Mac rebuild (required for honest CFBundle)

```bash
cd client_app
flutter build macos --release
# inject secrets + sign/notarize per APPLE_BUILD.md
python3 scripts/build_release_0.5.2.py --apple-only

flutter build ios --no-codesign
# Team-sign Packet Tunnel + host; zip as restore-privacy-client-0.5.2-ios.zip
```

Then:

```bash
python3 scripts/host_paid_assets_vps.py --stage --upload --version 0.5.2 --force
python3 scripts/breadcrumbs_vault.py publish
```

## Product notes in this monopin

- Admin **clear all licences** (BETA table cleanup)
- Dual-stack IPv4/IPv6 Settings (default both ON) + lean residual shape/obfs/multihop OFF
- Audit page last-run from `security_audit_latest.json` after every `run_security_audit.py --write`
- Settings disconnect-before-save while connected

## Helsinki breadcrumbs (source of truth for Mac tasks)

```bash
python3 scripts/breadcrumbs_vault.py check --fetch
# or: GET …/breadcrumbs/current/manifest.json with X-RPT-Asset-Token
```

GitHub APPLE_HANDOFF pull is **not** the primary task queue.
