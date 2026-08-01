# Restore Privacy Suite 1.0.2 — Windows breadcrumbs

**Catalog monopin:** **1.0.2**  
**Target PE:** `restore-privacy-client-1.0.2-windows-x64-setup.exe`  
**Helsinki:** `paid_assets/1.0.2/` on `135.181.152.10`

## Pins

| Location | Value |
|----------|--------|
| `client/VERSION` | 1.0.2 |
| `status_page/downloads.py` `RELEASE_VERSION` | 1.0.2 |
| Windows installer embedded product version | 1.0.2 |

## Build (Windows builder machine)

```powershell
cd C:\path\to\restore-privacy
git pull
python scripts\build_windows_multihop.py
# Output → releases\1.0.2\restore-privacy-client-1.0.2-windows-x64-setup.exe
```

## Upload

```powershell
$env:RPT_SSH_HOST="135.181.152.10"
$env:RPT_SSH_USER="root"
$env:RPT_SSH_KEY="$HOME\.ssh\id_ed25519_restore_privacy_eu"
python scripts\host_paid_assets_vps.py --stage --upload --version 1.0.2 --force --install-serve
```

## Full handoff

See `client/windows/WINDOWS_HANDOFF_1.0.2.md` and vault  
`dist/breadcrumbs/current/WINDOWS_HANDOFF.md` (after `breadcrumbs_vault.py stage`).

## Honesty

This tree may ship a **1.0.2-named** Windows installer staged from a prior pin for
catalogue continuity. **Native rebuild on Windows is required** before the PE is
the final paid seal. Do not leave a CF/renamed older PE as the lasting 1.0.2 Windows ship.
