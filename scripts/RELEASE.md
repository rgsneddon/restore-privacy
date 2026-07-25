# Releases

| Pin | Script |
|-----|--------|
| **0.4.5** (current) | `scripts/build_release_0.4.5.py` |
| **0.4.5 Windows multihop PE** | `scripts/build_windows_multihop.py` / `.bat` (Windows x64; `client/windows/WINDOWS_HANDOFF_0.4.5.md`) |
| **0.4.5 notes** | `scripts/RELEASE_NOTES_0.4.5.md` |
| **0.4.5 Apple handoff** | `client_app/APPLE_HANDOFF_0.4.5.md` |
| **0.4.4** (prior) | `scripts/build_release_0.4.4.py` |
| **0.4.2** (prior) | `scripts/build_release_0.4.2.py` |

Product node: **82.221.101.241:44044**. See `scripts/RELEASE_NOTES_0.4.5.md`.

### 0.4.5 platform build status

| Asset | This Windows host |
|-------|-------------------|
| Windows setup.exe | **Native PE** multihop freeze |
| Linux tar.gz | package_linux or CF from 0.4.4 |
| Android APK | CF residual-wire from 0.4.4 |
| macOS zip | CF filename pin - **Mac rebuild + notarize required** |
| iOS zip | CF filename pin - **Mac Team-sign required** |

```bash
python scripts/build_release_0.4.5.py
# Mac Apple packages:
#   see client_app/APPLE_HANDOFF_0.4.5.md then re-stage
gh release create 0.4.5 releases/0.4.5/* --title "0.4.5" --notes-file scripts/RELEASE_NOTES_0.4.5.md
```
