# Releases

| Pin | Script |
|-----|--------|
| **0.5.1** (current) | `scripts/build_release_0.5.1.py` |
| **0.5.1 notes** | `scripts/RELEASE_NOTES_0.5.1.md` |
| **0.5.1 Apple handoff** | `client_app/APPLE_HANDOFF_0.5.1.md` |
| **0.5.1 Windows handoff** | `client/windows/WINDOWS_HANDOFF_0.5.1.md` |
| **0.5.0** (prior) | `scripts/build_release_0.5.0.py` |
| **0.5.0 notes** | `scripts/RELEASE_NOTES_0.5.0.md` |
| **0.5.0 Apple handoff** | `client_app/APPLE_HANDOFF_0.5.0.md` |
| **0.4.10** (prior) | `scripts/build_release_0.4.10.py` |
| **0.4.10 Windows multihop PE** | `scripts/build_windows_multihop.py` / `.bat` (Windows x64; `client/windows/WINDOWS_HANDOFF_0.4.10.md`) |
| **0.4.10 notes** | `scripts/RELEASE_NOTES_0.4.10.md` |
| **0.4.10 Apple handoff** | `client_app/APPLE_HANDOFF_0.4.10.md` |
| **0.4.6** (prior) | `scripts/build_release_0.4.6.py` |
| **0.4.5** (prior) | `scripts/build_release_0.4.5.py` |
| **0.4.4** (prior) | `scripts/build_release_0.4.4.py` |
| **0.4.2** (prior) | `scripts/build_release_0.4.2.py` |

Product residual peers: **IS** `82.221.101.241:44044`, **RO** `185.146.232.107:44044`, **US** `5.161.242.85:44044`. See `scripts/RELEASE_NOTES_0.5.1.md`.

### 0.5.1 platform build status (this Windows host ship)

| Asset | Honesty on this ship |
|-------|----------------------|
| Windows setup.exe | **Native multihop PE rebuild** (`build_windows_multihop` / `build_release_0.5.1.py` on Windows x64) |
| Linux tar.gz | **Native rebuild** (`package_linux.py`) |
| Android APK | **Honest carry-forward** residual-wire from **0.5.0** (renamed to 0.5.1) when SDK rebuild absent |
| macOS zip | **Honest carry-forward** from prior Apple zip (catalog filename **0.5.1** only). Internal `CFBundleShortVersionString` may still be pre-0.5.1 (e.g. **0.2.3**). **Not** Developer ID / notarized native 0.5.1 until Mac handoff |
| iOS zip | **Honest carry-forward** from prior Team-signed zip (filename **0.5.1** only). Internal bundle version may still be pre-0.5.1. **Not** native monopin 0.5.1 until Mac Team-sign rebuild |

See `client_app/APPLE_HANDOFF_0.5.1.md` for Mac rebuild/notarize steps. Do not claim native Apple 0.5.1 seals while CF zips are what VPS hosts.

### Security audit timer (0.5.1)

- Period: **1 day** (`status_page/audit_countdown.py`, `scripts/install_security_audit_timer.sh`)
- Display: **days, hours, minutes, seconds** (`Dd HH:MM:SS`)
- Last run: `generated_at` in `status_page/static/security_audit_latest.json`

```bash
python scripts/build_release_0.5.1.py
# Apple-only:
python scripts/build_release_0.5.1.py --apple-only
#   see client_app/APPLE_HANDOFF_0.5.1.md
# Ship scripts refuse *.priv via _assert_no_priv in build_release_0.5.1.py
RPT_SSH_USER=raskul RPT_SSH_SUDO=1 python scripts/host_paid_assets_vps.py --stage --upload --version 0.5.1 --force
```
