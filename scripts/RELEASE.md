# Releases

| Pin | Script |
|-----|--------|
| **0.4.7** (current) | `scripts/build_release_0.4.7.py` |
| **0.4.7 Windows multihop PE** | `scripts/build_windows_multihop.py` / `.bat` (Windows x64; `client/windows/WINDOWS_HANDOFF_0.4.7.md`) |
| **0.4.7 notes** | `scripts/RELEASE_NOTES_0.4.7.md` |
| **0.4.7 Apple handoff** | `client_app/APPLE_HANDOFF_0.4.7.md` |
| **0.4.5** (prior) | `scripts/build_release_0.4.5.py` |
| **0.4.4** (prior) | `scripts/build_release_0.4.4.py` |
| **0.4.2** (prior) | `scripts/build_release_0.4.2.py` |

Product residual peers: **IS** `82.221.101.241:44044`, **RO** `185.146.232.107:44044`, **DE** `167.233.224.5:44044`. See `scripts/RELEASE_NOTES_0.4.7.md`.

### 0.4.7 platform build status

| Asset | This Windows host |
|-------|-------------------|
| Windows setup.exe | **Native PE** multihop freeze when rebuild succeeds |
| Linux tar.gz | `package_linux.py` or CF from 0.4.5 |
| Android APK | CF residual-wire from 0.4.5 |
| macOS zip | CF filename pin — **Mac rebuild + notarize required** |
| iOS zip | CF filename pin — **Mac Team-sign required** |

```bash
python scripts/build_release_0.4.7.py
# Mac Apple packages:
#   see client_app/APPLE_HANDOFF_0.4.7.md then re-stage
# Linux package helper: scripts/package_linux.py
# Ship scripts refuse *.priv via _assert_no_priv in build_release_0.4.7.py
gh release create 0.4.7 releases/0.4.7/* --title "0.4.7" --notes-file scripts/RELEASE_NOTES_0.4.7.md
RPT_SSH_USER=raskul RPT_SSH_SUDO=1 python scripts/host_paid_assets_vps.py --stage --upload --version 0.4.7 --force
```
