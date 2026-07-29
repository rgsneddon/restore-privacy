# Apple handoff — Restore Privacy **0.5.3**

**Monopin / this build:** `0.5.3`

## Built this (Windows host)

| Platform | Filename | Status |
|----------|----------|--------|
| Windows | `restore-privacy-client-0.5.3-windows-x64-setup.exe` | Built this ship (multihop PE) |
| Linux | `restore-privacy-client-0.5.3-linux-x64.tar.gz` | Built this ship |
| Android | `restore-privacy-client-0.5.3-android.apk` | Staged residual-wire from 0.5.2 (same wire) |
| macOS | `restore-privacy-client-0.5.3-macos.zip` | **Mac native seal required** (CFBundle must = 0.5.3) |
| iOS | `restore-privacy-client-0.5.3-ios.zip` | **Mac Team-sign required** |

Catalog pin and filenames are **0.5.3** for all five platforms. Apple zips were
**not** present as 0.5.3 on the Windows host at ship time — rebuild on Darwin.

## Publish under monopin **0.5.3**

- Helsinki: `/opt/restore-privacy/paid_assets/0.5.3/`
- Status: `status_page/assets/0.5.3/` (Win/Linux/Android staged)

### Mac rebuild

```bash
cd client_app
flutter build macos --release
flutter build ios --no-codesign
# inject secrets + sign/notarize per APPLE_BUILD.md
python3 scripts/build_release_0.5.3.py --apple-only
```
