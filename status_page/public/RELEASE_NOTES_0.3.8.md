# Restore Privacy 0.3.8

**Catalog monopin 0.3.8** — subscription keygen unlock, homepage licence/subscription copy, entry-only wipe display, fulfilment SMTP, audit last-run line.

## Highlights

- **Device bind after keygen (Apple + Android + desktop parity):** after active keygen unlock, clients POST `/api/bind-device-entitlement` with native Ed25519 `device_pub` so residual HELLO works when the node requires payment entitlement.
- **Keygen unlock:** unique RPT-KEY-… minted on paid Stripe checkout; fulfilment email includes keygen + PPI + download link (**USE THIS KEYGEN TO UNLOCK YOUR RESTORE PRIVACY TRIAL**). Clients: Install → accept licence → **forced keygen unlock dialog** (all platforms — not Settings-only) → Connect only while subscription active (online status-host re-check; device bind for residual HELLO; revoke locks product). Download alone does **not** unlock residual.
- **Connect errors:** residual remote reset / timeout messaging guides users to enter keygen and re-verify unlock (including Windows WinError 10054 class failures).
- **Homepage:** £2.45 per month subscription package — one device licence; trial sentence; BMC tip at page bottom.
- **Node wipe UI:** entry-only clear timer (exit wipe countdown removed; weekly service remains entry-only).
- **Security audit:** public audit panel shows **last audit run** datetime below the next-audit timer.
- **SMTP fulfilment:** Render env RPT_FULFILMENT_SMTP_* for customer email after pay.

Carry-forward: multi-hop residual (0.3.6), Windows PE multihop path, paid catalog, dual-node honesty for failover (exit never weekly-wiped).

---

## Multi-hop residual (entry → exit)

- **Entry (Iceland):** `82.221.101.241:44044` — `product/node_elgamal.pub` (`1b126abf…`)
- **Exit (Romania):** `185.146.232.107:44044` — `product/exit_node_elgamal.pub` (`a36a3f38…`, ElGamal **policy A**)
- When `RPT_MULTIHOP_ENABLED=1` (or Flutter `--dart-define=RPT_MULTIHOP_ENABLED=true`), residual Connect dials the **exit** hop; status reports multi-hop active with residual via the exit.
- Default remains **single-hop** to Iceland unless multi-hop is enabled.
- Honesty: residual-**via-exit** selection (egress IP is the exit VPS). This is **not** full intermediate encapsulation through the entry hop.
- **Node-only** zram + LUKS2 on multi-hop hosts (not on clients).

## Package matrix (0.3.8 rebuild)

| Platform | Multi-hop residual | Entry+exit pubs | Notes |
|----------|--------------------|-----------------|--------|
| **Linux** x64 tar.gz | **Yes** | **Yes** | Rebuilt via `package_linux.py` — `MULTI_HOP_ROUTING_IMPLEMENTED=True`, both pubs |
| **Android** APK | **Yes** (residual host + exit pub) | **Yes** | Flutter release rebuild; RptConfig exit host + `exit_node_elgamal.pub` in assets |
| **macOS** zip | **Yes** | **Yes** | Flutter+NativePrep **rebuild** (PacketTunnel + App embed exit host / `exit_node_elgamal.pub` / multihop define); DevID-signed; residual-via-exit when multi-hop enabled |
| **iOS** zip | **Yes** | **Yes** | Flutter+NativePrep **rebuild** (PacketTunnel + App embed exit residual selection); Team-signed sideload |
| **Windows** SFX | **Yes** (residual-via-exit) | **Yes** | **Rebuilt** on Windows x64 via `scripts/build_windows_multihop.py` (PyInstaller onedir + setup). Ships `client/multihop.py` (`MULTI_HOP_ROUTING_IMPLEMENTED=True`), entry + exit ElGamal **public** keys, Wintun. Default single-hop Iceland; `RPT_MULTIHOP_ENABLED=1` residual-via-exit Romania. Not full intermediate encapsulation. |

Windows PE multihop residual is in the paid catalog asset `restore-privacy-client-0.3.8-windows-x64-setup.exe` (see handoff).

## Catalog / payment

- Catalog monopin **0.3.8**
- Webhook: `https://restoreprivacy.online/webhook/stripe`
- Success: `/download/success?session_id={CHECKOUT_SESSION_ID}`
- Live Pay buttons (`Pay £2.45`, `stripe-live`, `client_reference_id`) + no free permanent public installer links
- Paid fulfilment: private GH Release assets and/or `status_page/assets/0.3.8/` + Iceland VPS paid_assets store (`scripts/host_paid_assets_vps.py`)
- Payment secrets remain on Render / local gitignored env only (never committed)

## Operator test checklist

1. Single-hop Connect (default) → residual via Iceland entry  
2. Multi-hop on **Linux 0.3.8**: `RPT_MULTIHOP_ENABLED=1` → residual via Romania  
3. Multi-hop on **Windows 0.3.8** (rebuilt PE): `RPT_MULTIHOP_ENABLED=1` → residual via Romania  
4. Multi-hop on **Android 0.3.8** with multihop define/env when available  
5. Paid download for **0.3.8** after assets are on status host / private GH release / VPS paid_assets  
6. Confirm node zram/LUKS2 is **node-only** (entry + exit hosts)
