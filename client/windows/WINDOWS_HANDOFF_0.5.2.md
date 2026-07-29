# Windows handoff — Restore Privacy **0.5.2**

Catalog monopin: **0.5.2**

## Built this

| Platform | File | How |
|----------|------|-----|
| Windows | `restore-privacy-client-0.5.2-windows-x64-setup.exe` | `build_release_0.5.2.py` multihop PE |
| Linux | `restore-privacy-client-0.5.2-linux-x64.tar.gz` | `package_linux.py` |
| Android | `restore-privacy-client-0.5.2-android.apk` | Flutter `assembleRelease` |
| macOS / iOS | — | Helsinki breadcrumbs → Mac seal |

## Update these docs

`APPLE_HANDOFF_0.5.2.md`, `RELEASE_NOTES_0.5.2.md`, PRIVACY_POLICY, AUDIT, settings explainer, downloads monopin — all **0.5.2**.

## Publish all to **0.5.2**

Helsinki `paid_assets/0.5.2/` + `status_page/assets/0.5.2/`. No separate version invent.

```powershell
python scripts\build_release_0.5.2.py --no-apple
# Win/Android/Linux already on HEL1 paid_assets/0.5.2 from this ship
python scripts\breadcrumbs_vault.py publish --version 0.5.2
```
