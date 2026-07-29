# Apple handoff — Restore Privacy **0.5.5**

**Monopin / this build:** `0.5.5`

## Windows host ship

| Platform | Filename | Status |
|----------|----------|--------|
| Windows | `restore-privacy-client-0.5.5-windows-x64-setup.exe` | **native** multihop PE (`hidden_subprocess` Connect fix + dual-stack Settings top) |
| Linux | `restore-privacy-client-0.5.5-linux-x64.tar.gz` | staged monopin (CF if not native rebuild) |
| Android | `restore-privacy-client-0.5.5-android.apk` | staged monopin (CF if not native rebuild) |
| macOS | `restore-privacy-client-0.5.5-macos.zip` | **Mac native seal required** (CFBundle must = 0.5.5) |
| iOS | `restore-privacy-client-0.5.5-ios.zip` | **Mac Team-sign required** |

## Mac rebuild

```bash
python3 scripts/build_release_0.5.5.py --apple-only
python3 scripts/host_paid_assets_vps.py --stage --upload --version 0.5.5 --force
python3 scripts/breadcrumbs_vault.py publish --version 0.5.5
```
