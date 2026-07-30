# Windows handoff — Restore Privacy **0.5.8**

**Catalog monopin:** 0.5.8  
**Helsinki store:** `root@135.181.152.10` · `paid_assets/0.5.8/` · pin `RPT_CATALOG_VERSION=0.5.8`  
**SSH key:** `~/.ssh/id_ed25519_restore_privacy_eu` (same as Mac store key)

## Split ship (0.5.8)

| Platform | Who | Status on Helsinki (after Mac ship) |
|----------|-----|-------------------------------------|
| **macOS** | Mac | Hosted after Mac seal |
| **iOS** | Mac | Hosted after Mac seal |
| **Android** | Mac | Hosted after Mac seal |
| **Linux** | Mac | Hosted (Arch-aware tarball) |
| **Windows** | **This Windows machine** | **Build PE and re-upload** |

Do **not** leave a CF / renamed older PE as the final paid Windows seal for 0.5.8.

## Product work in 0.5.8 (must be in tree after `git pull`)

- Upgrade CTA → monopin download (not `/pay`); mint with local keygen when present
- Keygen/licence durable rollover across monopin upgrades
- Dataplane idle backoff (Python residual)
- Arch/CachyOS install path in Linux package (Windows PE still Windows-only residual)

## Catalog pins Windows must embed

| Peer | Host | Public pin |
|------|------|------------|
| IS | 82.221.101.241 | `product/node_elgamal.pub` |
| DE (default + exit) | 178.105.187.178 | `product/de_node_elgamal.pub` |
| US | 5.161.242.85 | `product/us_node_elgamal.pub` |

## Build + host (Windows machine)

```powershell
cd C:\path\to\restore-privacy
git pull

python scripts\build_release_0.5.8.py --windows-only
# preferred native multihop PE:
# python scripts\build_windows_multihop.py

$env:RPT_SSH_HOST="135.181.152.10"
$env:RPT_SSH_USER="root"
$env:RPT_SSH_KEY="$HOME\.ssh\id_ed25519_restore_privacy_eu"
python scripts\host_paid_assets_vps.py --stage --upload --version 0.5.8 --force
```

**Target basename:**

```text
paid_assets/0.5.8/restore-privacy-client-0.5.8-windows-x64-setup.exe
```

Confirm `RPT_CATALOG_VERSION=0.5.8` still set on Helsinki after upload.

## Breadcrumbs vault

```text
https://135.181.152.10.sslip.io/breadcrumbs/current/
/opt/restore-privacy/breadcrumbs/current/
/opt/restore-privacy/breadcrumbs/0.5.8/
```

## Tester fulfilment

https://restoreprivacy.online/ · Admin mint: https://restoreprivacy.online/admin/
