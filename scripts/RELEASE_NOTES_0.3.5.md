# Restore Privacy 0.3.5

## Catalog pin

- Client monopin and status catalog: **0.3.5**
- Paid download filenames: `restore-privacy-client-0.3.5-{platform}…`
- Production node remains **`82.221.101.241:44044`** (FlokiNET / Iceland)

## Product

- **Live** public catalog **Pay £2.45** buttons (Stripe Payment Link + `client_reference_id` per platform)
- Paid fulfilment: webhook `https://restoreprivacy.online/webhook/stripe` → one-time `/download?token=…`
- Optional empty `STRIPE_CHECKOUT_PRICE_ID` → unit_amount £2.45 Checkout
- macOS: Developer ID + notarized app zip (primary live-test package)
- iOS: Team-signed sideload zip
- Windows / Android / Linux: carry-forward from **0.3.4** with version pin rewrite where needed
- Node residual: zram + LUKS2 node-only (from 0.3.4); clients residual Connect unchanged

## Operator

1. Stage paid assets: `python scripts/stage_paid_assets.py --version 0.3.5`
2. Host installers on Iceland VPS paid-asset store (or status `assets/0.3.5/`)
3. Live test: Pay **macOS** on https://restoreprivacy.online/ → success download of **0.3.5** zip

## Payment paths (unchanged URLs)

| Path | Role |
|------|------|
| `https://restoreprivacy.online/webhook/stripe` | Stripe webhook |
| `/download/success?session_id={CHECKOUT_SESSION_ID}` | Thank-you + grant poll |
| `/download?token=…` | One-time paid installer proxy |
| Pay buttons | `donate.stripe.com/…?client_reference_id=macos` (etc.) |
