# Releases

| Pin | Script |
|-----|--------|
| **0.4.4** (current) | `scripts/build_release_0.4.4.py` |
| **0.4.4 Windows multihop PE** | `scripts/build_windows_multihop.py` / `.bat` (Windows x64; `client/windows/WINDOWS_HANDOFF_0.4.4.md`) |
| **0.4.4 notes** | `scripts/RELEASE_NOTES_0.4.4.md` |
| **0.4.4 Apple handoff** | `client_app/APPLE_HANDOFF_0.4.4.md` |
| **0.4.2** (prior) | `scripts/build_release_0.4.2.py` |

Product node: **82.221.101.241:44044**. See `scripts/RELEASE_NOTES_0.4.4.md`.

### 0.4.4 platform build status

| Asset | This Windows host |
|-------|-------------------|
| Windows setup.exe | **Native PE** multihop freeze |
| Linux tar.gz | package_linux or CF from 0.4.2 |
| Android APK | CF residual-wire from 0.4.2 |
| macOS zip | CF filename pin — **Mac rebuild + notarize required** |
| iOS zip | CF filename pin — **Mac Team-sign required** |

```bash
python scripts/build_release_0.4.4.py
# Mac Apple packages:
#   see client_app/APPLE_HANDOFF_0.4.4.md then re-stage
gh release create 0.4.4 releases/0.4.4/* --title "0.4.4" --notes-file scripts/RELEASE_NOTES_0.4.4.md
```
