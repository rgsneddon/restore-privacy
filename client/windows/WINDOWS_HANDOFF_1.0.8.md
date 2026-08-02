# Windows brand breadcrumbs — monopin 1.0.8

## Context (trial architecture + Stripe)

Mac stages Suite **1.0.8** with:

1. **First-run:** account → 12-word seed → licence **before** residual VPN permissions  
2. **In-app residual trial:** KEYGEN-free **72 hours (3 days)** bound to `device_pub` (+ durable `install_id`); **no card**  
3. **After trial:** residual Connect blocked until **paid KEYGEN / active subscription**  
4. **Stripe KEYGEN Checkout:** **`trial_period_days = 0`** — subscription bills immediately (trial is **not** on payment plans)  
5. **Anti-reinstall (host):** same `device_pub` or same `install_id` cannot claim a second full trial after expiry (operator-only detail — not public copy)

## On the Windows build machine

1. Sync monorepo (`client/VERSION` = `1.0.8`).  
2. Build `restore-privacy-client-1.0.8-windows-x64-setup.exe`.  
3. Authenticode-sign; stage to `status_page/assets/1.0.8/` and Helsinki paid upload.  
4. `python3 scripts/breadcrumbs_vault.py stage --version 1.0.8` (if used).

## Target PE

```text
releases/1.0.8/restore-privacy-client-1.0.8-windows-x64-setup.exe
```

## Operator note (Stripe Dashboard)

Code no longer sends `subscription_data[trial_period_days]` when catalog wants 0.
If live Dashboard prices still show a Stripe trial, reconfigure prices / stop
attaching trial on Checkout so live matches code. Residual free trial remains
host `device_trial` only.

## Related commits (this goal series)

- Trial-then-pay copy + install_id mitigation  
- Stripe catalog trial days → 0; public reinstall caveats removed from privacy  
