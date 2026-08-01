# Stripe audit findings — amount_total sole cash truth

## Status: gaps closed

### Fix (shipped `process_checkout_completed_event`)
- **Sole cash truth:** unlock uses Stripe `amount_total` only.
- **`metadata.amount_pence` ignored** for unlock gates (builders pin GBP 300 even on USD).
- **Paid + missing amount_total** → fail closed (cannot use metadata spoof).
- **USD:** `amount_total` ≈ FX(£3)/FX(£30) cents (±2) → unlock; grant books GBP 300/3000.
- **Underpay spoof:** `amount_total=1` + `metadata.amount_pence=300` → no token, no `connect_allowed`.

### Verification (isolated payment DB + unique session ids)
- USD builder-shaped paid monthly → unlock, grant_pence=300
- amount_total=1 + meta 300 → spoof never grants connect_allowed
- invoice.paid amount_paid 1/999 after trial → rejected_non_catalog_amount
- invoice.paid 300 → renewed + catalog sale

### Tests
- `TestAmountTotalOverMetadata` (USD unlock, total=1 meta=300 deny, paid missing total deny)
- Full KEYGEN + subscription + pay-plan suites green
