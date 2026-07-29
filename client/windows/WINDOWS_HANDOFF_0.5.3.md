# Windows handoff — Restore Privacy **0.5.3**

Catalog monopin: **0.5.3**

## Built this

| Platform | File | How |
|----------|------|-----|
| Windows | `restore-privacy-client-0.5.3-windows-x64-setup.exe` | `build_release_0.5.3.py` multihop PE |
| Linux | `restore-privacy-client-0.5.3-linux-x64.tar.gz` | `package_linux.py` |
| Android | `restore-privacy-client-0.5.3-android.apk` | Flutter `assembleRelease` |
| macOS / iOS | — | Helsinki breadcrumbs → Mac seal |

## Update these docs

`APPLE_HANDOFF_0.5.3.md`, `RELEASE_NOTES_0.5.3.md`, PRIVACY_POLICY, AUDIT, settings explainer, downloads monopin — all **0.5.3**.

## Publish all to **0.5.3**

Helsinki `paid_assets/0.5.3/` + `status_page/assets/0.5.3/`. No separate version invent.

```powershell
python scripts\build_release_0.5.3.py --no-apple
# Win/Android/Linux already on HEL1 paid_assets/0.5.3 from this ship
python scripts\breadcrumbs_vault.py publish --version 0.5.3
```
