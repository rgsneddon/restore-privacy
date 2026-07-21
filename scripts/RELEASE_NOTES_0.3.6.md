# Restore Privacy 0.3.6

## Multi-hop residual (entry → exit)

- **Entry (Iceland):** `82.221.101.241:44044` — `product/node_elgamal.pub` (`1b126abf…`)
- **Exit (Romania):** `185.146.232.107:44044` — `product/exit_node_elgamal.pub` (`a36a3f38…`, ElGamal **policy A**)
- When `RPT_MULTIHOP_ENABLED=1`, residual Connect dials the **exit** hop (last hop);
  status reports **multi-hop active** with residual via the exit.
- Default remains **single-hop** to Iceland unless multi-hop is enabled.
- Honesty: residual-**via-exit** selection (egress IP is the exit VPS). This is **not**
  full intermediate encapsulation through the entry hop (no onion-style middle relay).
- **Node-only** zram + LUKS2 on multi-hop hosts (not on clients).

## Package matrix (honest)

| Platform | Multi-hop residual in 0.3.6 package | Notes |
|----------|-------------------------------------|--------|
| **Linux** x64 tar.gz | **Yes** | Rebuilt with `client/multihop.py` (`MULTI_HOP_ROUTING_IMPLEMENTED=True`), entry + exit pubs under `product/` and `secrets/` |
| **Windows** SFX | Carry-forward | Full native rebuild recommended for multi-hop residual; 0.3.6 catalog pin only |
| **macOS** zip | Carry-forward | Full OS rebuild recommended for multi-hop residual |
| **iOS** zip | Carry-forward | Full OS rebuild recommended for multi-hop residual |
| **Android** APK | Carry-forward | Full OS rebuild recommended for multi-hop residual |

Linux is the **reference** multi-hop residual package for operator tests.

Linux sha256: `bbfb771ff7cabf3584a6ca96e2f25016191e96aea5fcb9cf75217f531bd8596a`

## Catalog / payment

- Catalog monopin **0.3.6**
- Webhook: `https://restoreprivacy.online/webhook/stripe`
- Success: `/download/success?session_id={CHECKOUT_SESSION_ID}`
- Live Pay buttons (`Pay £2.45`, `stripe-live`, `client_reference_id`) + no free permanent public installer links
- Payment secrets remain on Render / local gitignored env only (never committed)

## Operator test checklist

1. Single-hop Connect (default) → residual via Iceland entry
2. Multi-hop on **Linux 0.3.6**: `RPT_MULTIHOP_ENABLED=1` (+ exit pub present) → residual via Romania
3. Paid download for **0.3.6** after assets are on the status host / private GH release
4. Confirm node zram/LUKS2 is **node-only** (entry + exit hosts), not on clients
