# Restore Privacy 0.3.6

## Multi-hop residual (entry → exit)

- **Entry (Iceland):** `82.221.101.241:44044`
- **Exit (Romania):** `185.146.232.107:44044`
- When `RPT_MULTIHOP_ENABLED=1`, residual Connect dials the **exit** hop (last hop);
  status reports **multi-hop active** with residual via the exit.
- Default remains **single-hop** to Iceland unless multi-hop is enabled.
- Exit uses **ElGamal policy A** (exit-only key); clients load `product/exit_node_elgamal.pub` for residual HELLO to Romania.
- **Node-only** zram + LUKS2 on multi-hop hosts (not on clients).

## Catalog / payment

- Catalog monopin **0.3.6**
- Webhook: `https://restoreprivacy.online/webhook/stripe`
- Success: `/download/success?session_id={CHECKOUT_SESSION_ID}`
- Live Pay buttons + `client_reference_id` per platform
- No free permanent public installer links

## Operator test (tomorrow)

1. Single-hop Connect (default) → residual via Iceland
2. Multi-hop: set `RPT_MULTIHOP_ENABLED=1` (and exit pub present) → residual via Romania
3. Paid macOS download for **0.3.6** after deploy of packages
