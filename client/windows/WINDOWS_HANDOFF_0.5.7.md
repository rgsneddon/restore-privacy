# Windows handoff — Restore Privacy **0.5.7**

**Catalog monopin:** 0.5.7  
**Helsinki store:** `root@135.181.152.10` · `paid_assets/0.5.7/` · pin `RPT_CATALOG_VERSION=0.5.7`  
**SSH key:** `~/.ssh/id_ed25519_restore_privacy_eu` (same as Mac store key)

## Split ship (0.5.7)

| Platform | Who | Status on Helsinki |
|----------|-----|--------------------|
| **macOS** | Mac (Darwin) | Hosted — DevID + notarized |
| **iOS** | Mac | Hosted — Apple Distribution Team-sign |
| **Android** | Mac | Hosted — native APK (DE pin + IPv4 always-on + IPv6 + Quit) |
| **Linux** | Mac | Hosted — native tarball |
| **Windows** | **This Windows machine** | **Missing** — build PE and re-upload |

Do **not** leave a CF / renamed older PE as the final paid Windows seal.

## Catalog (this monopin)

- Residual peers: **IS / DE / US** — **Romania (RO) deprecated**
- **Default residual entry: Germany (DE)** `178.105.187.178:44044` (`de_node_elgamal.pub`)
- Multi-hop exit: **DE** (same host; `exit_node_elgamal.pub` = DE public material)
- Stale RO prefs normalize → **DE**
- Residual **IPv4 always on** (not a Settings switch); residual **IPv6** remains toggleable

## Build + host (Windows machine)

```powershell
cd C:\path\to\restore-privacy
git pull   # when Mac tree is pushed; or sync monorepo with monopin 0.5.7

python scripts\build_release_0.5.7.py --windows-only

$env:RPT_SSH_HOST="135.181.152.10"
$env:RPT_SSH_USER="root"
$env:RPT_SSH_KEY="$HOME\.ssh\id_ed25519_restore_privacy_eu"
python scripts\host_paid_assets_vps.py --stage --upload --version 0.5.7 --force
```

**Target basename:**

```text
paid_assets/0.5.7/restore-privacy-client-0.5.7-windows-x64-setup.exe
```

After upload, confirm:

```powershell
# sizes/sha match local releases\0.5.7\…-windows-x64-setup.exe
# remote: /opt/restore-privacy/paid_assets/0.5.7/
# unit still has RPT_CATALOG_VERSION=0.5.7
```

## Product pins Windows must embed

| Peer | Host | Public pin (never `.priv`) |
|------|------|----------------------------|
| IS | 82.221.101.241 | `product/node_elgamal.pub` |
| DE (default + exit) | 178.105.187.178 | `product/de_node_elgamal.pub` (+ `exit_node_elgamal.pub` same material) |
| US | 5.161.242.85 | `product/us_node_elgamal.pub` |

## Settings / residual honesty (parity with Mac 0.5.7)

- Residual IPv4 capture always ON
- Residual IPv6 ON/OFF honesty on Connected status
- Entry country dropdown: IS / DE / US only (default DE)

## Breadcrumbs on Helsinki

```text
https://135.181.152.10.sslip.io/breadcrumbs/current/
/opt/restore-privacy/breadcrumbs/current/
/opt/restore-privacy/breadcrumbs/0.5.7/
```

Also see `WINDOWS_HANDOFF.md` snapshot under breadcrumbs when published.

## Tester fulfilment (status host)

Paid downloads and tester mint: **https://restoreprivacy.online/**  
Admin (mint tester licences): **https://restoreprivacy.online/admin/**  
Link generation / free months: **https://restoreprivacy.online/admin/link-generation**
