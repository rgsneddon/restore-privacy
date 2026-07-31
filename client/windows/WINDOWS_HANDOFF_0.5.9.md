# Windows handoff — Restore Privacy **0.5.9**

**Catalog monopin:** 0.5.9  
**Helsinki store:** `root@135.181.152.10` · `paid_assets/0.5.9/` · pin `RPT_CATALOG_VERSION=0.5.9`  
**SSH key:** `~/.ssh/id_ed25519_restore_privacy_eu` (same as Mac store key)

## Split ship (0.5.9)

| Platform | Who | Status on Helsinki (after Mac ship) |
|----------|-----|-------------------------------------|
| **macOS** | Mac | Hosted after Mac seal |
| **iOS** | Mac | Hosted after Mac seal |
| **Android** | Mac | Hosted after Mac seal |
| **Linux** | Mac | Hosted (Arch-aware tarball) |
| **Windows** | **This Windows machine** | **Build PE and re-upload** |

Do **not** leave a CF / renamed older PE as the final paid Windows seal for 0.5.9.

## Product work in 0.5.9 (must be in tree after `git pull`)

- Residual catalog **IS / DE only** (US peer **retired** — same normalize-to-DE as RO)
- Default residual entry **Germany (DE)**
- Seamless upgrade: active keygen rolls over monopin bumps; do not force re-unlock on version alone
- Windows PE must embed DE residual pub (`de_node_elgamal.pub`) + IS `node_elgamal.pub`
- **Do not** inject `us_node_elgamal.pub` as a live dial peer for Settings

## Seamless VPN config on upgrade (Windows)

Same durable entitlement / prefs path as prior monopin:

1. Leave `%LOCALAPPDATA%` / product user-data **intact** when installing over 0.5.8 (installer must not wipe keygen store or entry_country prefs).
2. After install, first Connect should reuse prior Settings residual entry (stale **US** prefs normalize to **DE**).
3. Keygen: active subscription unlocks without re-paste after monopin bump (`payment_entitlement` version-agnostic).
4. If residual fails after upgrade: confirm DE pin is present in package secrets; re-select Germany; Connect again.

## Catalog pins Windows must embed

| Peer | Host | Public pin |
|------|------|------------|
| IS | 82.221.101.241 | `product/node_elgamal.pub` |
| DE (default + exit) | 178.105.187.178 | `product/de_node_elgamal.pub` |

## Build + host (Windows machine)

```powershell
cd C:\path\to\restore-privacy
git pull

python scripts\build_release_0.5.9.py --windows-only
# preferred native multihop PE:
# python scripts\build_windows_multihop.py

$env:RPT_SSH_HOST="135.181.152.10"
$env:RPT_SSH_USER="root"
$env:RPT_SSH_KEY="$HOME\.ssh\id_ed25519_restore_privacy_eu"
python scripts\host_paid_assets_vps.py --stage --upload --version 0.5.9 --force
```

**Target basename:**

```text
paid_assets/0.5.9/restore-privacy-client-0.5.9-windows-x64-setup.exe
```

Confirm `RPT_CATALOG_VERSION=0.5.9` still set on Helsinki after upload.

## Breadcrumbs vault

```text
https://135.181.152.10.sslip.io/breadcrumbs/current/
/opt/restore-privacy/breadcrumbs/current/
/opt/restore-privacy/breadcrumbs/0.5.9/
```

## Tester fulfilment

https://restoreprivacy.online/ · Admin mint: https://restoreprivacy.online/admin/
