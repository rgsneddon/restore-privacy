# Stripe audit findings (amount_total fix)

## Bugs fixed
1. **USD presentment never unlocked:** completion preferred metadata.amount_pence=300 over amount_total≈381 USD cents. Now amount_total is cash truth; USD maps to GBP catalog grant (300/3000).
2. **Underpay spoof:** amount_total=1 + metadata amount_pence=300 no longer unlocks.

## Proof
- Unit: TestAmountTotalOverMetadata (builder-shaped USD + spoof)
- SCRATCH stripe_audit_checkout.txt (fresh RPT_PAYMENT_DATA_DIR) → AMOUNT_TOTAL_GATE_OK
