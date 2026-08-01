# Stripe audit findings (amount_total fix)

## Bugs fixed this pass
1. **USD presentment never unlocked:** completion preferred `metadata.amount_pence=300` over `amount_total≈381` USD cents, so `amount_ok`/`usd_ok` both failed. Now **amount_total** is cash truth; USD monthly/yearly map to GBP catalog grant anchors.
2. **Underpay spoof:** `amount_total=1` + `metadata.amount_pence=300` previously unlocked. amount_total wins → rejected.

## Tests
- `test_usd_builder_shaped_paid_monthly_unlocks` (drives real builder fields + completion)
- `test_amount_total_1_with_metadata_300_does_not_unlock`
