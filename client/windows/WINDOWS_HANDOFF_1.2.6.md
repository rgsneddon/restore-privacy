# Windows brand breadcrumbs — monopin 1.2.6

**Audience:** Windows x64 build machine. Native-rebuild the Windows PE for 1.2.6.

**Catalog monopin:** `1.2.6`

**Target PE:** `releases\1.2.6\restore-privacy-client-1.2.6-windows-x64-setup.exe`

Helsinki breadcrumbs (`WINDOWS_HANDOFF.md` in the vault) is the live instruction set — not a GitHub queue.

## Product truth

Residual VPN. Catalog entries: **Germany (DE)** default and **Singapore (SG)** (`5.223.48.8`, pin `sg_node_elgamal.pub`). Iceland / United States / Romania are **not** offered. Tray exactly `Privacy, Restored`. Quit lower-left disconnect-then-exit. Kill-switch ON requires typing `KILLSWITCH`.

## Singapore catalog (required on this PE)

The Windows PE **must** ship `product/sg_node_elgamal.pub` and show Singapore in the entry-country menu. Choosing Singapore dials `5.223.48.8:44044` with the SG pin (never the DE pin or Iceland `node_elgamal.pub`).

Python seed lists that must include `sg_node_elgamal.pub`:

- `client/residual_pub_ensure.py` `CATALOG_PUBLIC_PUBS`
- `client/secrets_loader.py` `CATALOG_NODE_PUB_NAMES`

Do **not** overwrite the Helsinki **1.2.5** Windows PE from a Mac. This 1.2.6 PE is built only on the Windows machine and uploaded to `paid_assets/1.2.6/` (new folder). Helsinki `paid_assets/1.2.5/restore-privacy-client-1.2.5-windows-x64-setup.exe` stays until this 1.2.6 upload replaces the Downloads Map Windows row.

```bat
python scripts\build_windows_multihop.py --version 1.2.6
python scripts\host_paid_assets_vps.py --stage --upload --version 1.2.6 --force
```

## Deltas since 1.2.5

| Area | Change |
|------|--------|
| Catalog pin | `client/VERSION` **1.2.6** |
| Live residual peers | Germany (default) + Singapore; Iceland forgotten as a live connectivity option |
| HELLO pin | `5.223.48.8` → `sg_node_elgamal.pub` on every client surface |
| Audit | Probe schedule / fail-safe / published view = DE+SG only |
| Attach / DATA / IPv6 / tray / DNS | Same 1.2.5 attach honesty — keep those PE fixes |

## Build

```bat
cd /d C:\Users\rgsne\restore_privacy
git pull
type client\VERSION
rem MUST print: 1.2.6
python scripts\build_windows_multihop.py --version 1.2.6
```

Output: `releases\1.2.6\restore-privacy-client-1.2.6-windows-x64-setup.exe`

Unsigned PE is allowed when Authenticode funds are unavailable (same as 1.2.5).

## Host

```bat
python scripts\host_paid_assets_vps.py --stage --upload --version 1.2.6 --force
```

Helsinki: `/opt/restore-privacy/paid_assets/1.2.6/restore-privacy-client-1.2.6-windows-x64-setup.exe`

After upload, the Downloads Map Windows row moves from 1.2.5 to 1.2.6. Do **not** delete or overwrite `paid_assets/1.2.5/` Windows from this Mac.

## Observe (same as 1.2.5)

After KEYGEN/trial Connect, hash `client_ed25519.priv` under `%USERPROFILE%\.restore-privacy\secrets` and `%LOCALAPPDATA%\Programs\RestorePrivacy\secrets` — they must match. Singapore Connect must HELLO with `sg_node_elgamal.pub`.
