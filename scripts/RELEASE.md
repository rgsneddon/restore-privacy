# Releases

| Pin | Script |
|-----|--------|
| **0.5.0** (current) | `scripts/build_release_0.5.0.py` |
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

Product residual peers: **IS** `82.221.101.241:44044`, **RO** `185.146.232.107:44044`, **US** `5.161.242.85:44044`. See `scripts/RELEASE_NOTES_0.5.0.md`.

### 0.5.0 platform build status

| Asset | This Mac host |
|-------|---------------|
| macOS zip | **Developer ID + notarized** when secrets present |
| iOS zip | **Team-signed sideload** when secrets present |
| Windows / Android / Linux | Honest carry-forward from **0.4.10** until native rebuild |

### Security audit timer (0.5.0)

- Period: **1 day** (`status_page/audit_countdown.py`, `scripts/install_security_audit_timer.sh`)
- Display: **days, hours, minutes, seconds** (`Dd HH:MM:SS`)
- Last run: `generated_at` in `status_page/static/security_audit_latest.json`

```bash
python scripts/build_release_0.5.0.py
# Apple-only:
python scripts/build_release_0.5.0.py --apple-only
#   see client_app/APPLE_HANDOFF_0.5.0.md
# Ship scripts refuse *.priv via _assert_no_priv in build_release_0.5.0.py
RPT_SSH_USER=raskul RPT_SSH_SUDO=1 python scripts/host_paid_assets_vps.py --stage --upload --version 0.5.0 --force
```
