# Stripe audit findings

## Bugs found this pass
1. **`trial_ok` loophole (fixed):** `payment_status=paid` with `amount_total=0` unlocked KEYGEN via `amount == 0` branch. Now trial requires `payment_status == "no_payment_required"` and amount 0/absent only.
2. **Grant amount fallback (hardened):** Removed open `amount > 0` grant_pence path; non-matching gated sessions fail closed with `return None`.

## Already closed (prior commits, re-verified)
- Yearly underpay (1p/999p) with subscription does not unlock
- Monthly underpay (1p/150p/999p) with subscription does not unlock
- invoice.paid non-catalog (1/999) does not renew Connect
- Commercial £3000 one-time does not unlock KEYGEN catalog path
- Catalog builders: subscription mode, 300/3000 pence, trial_period_days=3

## Residual notes (not bugs)
- Paid session with amount 3000 and monthly interval still unlocks as yearly catalog amount (honest £30 cash) — acceptable.
- USD presentment uses relative cents (±2) via existing usd_ok path.
