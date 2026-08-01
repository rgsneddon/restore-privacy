# Windows handoff — Restore Privacy Suite **1.0.2**

**Catalog monopin:** 1.0.2  
**Helsinki store:** `root@135.181.152.10` · `paid_assets/1.0.2/` · pin `RPT_CATALOG_VERSION=1.0.2`  
**SSH key:** `~/.ssh/id_ed25519_restore_privacy_eu` (same as Mac store key)

## Split ship (1.0.2)

| Platform | Who | Status |
|----------|-----|--------|
| **macOS** | Mac | Native Flutter build when seal available; else CFBundle must equal **1.0.2** before Helsinki publish |
| **iOS** | Mac | Team-sign / handoff zip |
| **Android** | Mac | Flutter APK with `--build-name=1.0.2` |
| **Linux** | Mac | tarball (may be carry-forward until native rebuild) |
| **Windows** | **This Windows machine** | **Build PE and re-upload** (do not leave CF/renamed older PE as final seal) |

## Product pins Windows must embed

| File / constant | Value |
|-----------------|-------|
| `client/VERSION` | **1.0.2** |
| `status_page/downloads.py` `RELEASE_VERSION` / `RELEASE_TAG` | **1.0.2** |
| `client/windows/installer.py` `PRODUCT_VERSION_EMBEDDED` (or equivalent) | **1.0.2** |
| `client_app` pubspec / suite monopin | **1.0.2** |

## Catalog peer pubs

| Peer | Host | Public pin |
|------|------|------------|
| IS | 82.221.101.241 | `product/node_elgamal.pub` |
| DE (default + exit) | 178.105.187.178 | `product/de_node_elgamal.pub` |
| US | 5.161.242.85 | `product/us_node_elgamal.pub` |

## Build + host (Windows machine)

```powershell
cd C:\path\to\restore-privacy
git pull

# Preferred native multihop PE (product version 1.0.2):
python scripts\build_windows_multihop.py
# Or suite-focused path if present:
# python scripts\build_suite_1.0.2.py
# python scripts\build_release_1.0.2.py --windows-only

# Confirm basename:
# releases\1.0.2\restore-privacy-client-1.0.2-windows-x64-setup.exe

$env:RPT_SSH_HOST="135.181.152.10"
$env:RPT_SSH_USER="root"
$env:RPT_SSH_KEY="$HOME\.ssh\id_ed25519_restore_privacy_eu"
# Optional shared token (same as Render asset fetch):
# $env:RPT_ASSET_FETCH_TOKEN="…"

python scripts\host_paid_assets_vps.py --stage --upload --version 1.0.2 --force --install-serve
```

**Target basename (Helsinki):**

```text
paid_assets/1.0.2/restore-privacy-client-1.0.2-windows-x64-setup.exe
```

Also stage suite alias if used by free storefront:

```text
restore-privacy-suite-1.0.2-windows-x64-setup.exe
```

Confirm `RPT_CATALOG_VERSION=1.0.2` (or equivalent) still set on Helsinki after upload.

## Free / catalog download routes

- Status host free route: `/suite/download?platform=windows`
- Paid fulfilment: Helsinki paid-assets + status proxy (`open_release_asset`)
- Public docs: `docs/SUITE_FREE_DOWNLOAD.md`

## Companion packages (already packageable on any host)

Not Windows-PE dependent; Mac operator can rebuild/upload:

- Rx browser multi-platform under `releases/1.0.2/restore-privacy-rx-browser-1.0.2-*.zip|tar.gz`
- rpOS desktop: `releases/rpos/0.2.0/rpos-0.2.0-*` (includes RxShell)
- Pens · Tables · Slides: `releases/rpos-apps/0.1.0/*-installer.zip`
- rpOffice / rpMail desktop archives under `releases/rpoffice/0.1.0/`, `releases/rpmail/0.1.0/`

Full brand inventory:

```powershell
python scripts\brand_package_inventory.py
# or:
python -c "import sys; sys.path.insert(0,'scripts'); from brand_package_inventory import list_brand_installer_packages; print(len(list_brand_installer_packages()))"
```

## Breadcrumbs vault

```text
https://135.181.152.10.sslip.io/breadcrumbs/current/
/opt/restore-privacy/breadcrumbs/current/
/opt/restore-privacy/breadcrumbs/1.0.2/
```

Local stage:

```powershell
python scripts\breadcrumbs_vault.py stage
python scripts\breadcrumbs_vault.py publish
```

## Honesty

- **Windows:** native rebuild required on this machine for an honest 1.0.2 PE seal (multihop markers + embedded product version).
- Catalog may temporarily host a **carry-forward** Windows basename from a prior pin for store continuity — **replace** with the native PE before calling the Windows seal final.
- Do **not** claim Corel/Microsoft trademarks; Suite brands remain residual VPN + free office pillars.

## Tester fulfilment

https://restoreprivacy.online/ · Admin mint: https://restoreprivacy.online/admin/

---

> **Breadcrumbs vault (Helsinki)** is the source of truth for “what to update” on this monopin. Do **not** treat a private GitHub pull of this file as the primary task queue.
> Fetch: `https://135.181.152.10.sslip.io/breadcrumbs/current/manifest.json` with `X-RPT-Asset-Token`.
