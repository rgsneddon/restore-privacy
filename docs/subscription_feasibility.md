# Subscription retention via keygen — feasibility

**Verdict: feasible** for retaining paid subscriptions **if and only if** client
unlock is online-validated against the status host entitlement bound to Stripe
subscription / payment webhooks.

## Why it works
- Checkout mints unique keygen per paid session, stored on `connect_entitlements`.
- Clients enter keygen after licence accept; status host returns active/revoked.
- Connect re-checks remotely so refunds, disputes, failed charges, and
  subscription period end lock the product without a new offline secret.

## What does not work alone
- Offline cryptographic keygen that never re-contacts the host cannot disable
  installs after payment failure. Do not ship offline-only unlock.

## Operator requirements
- Stripe webhooks for checkout complete + failure/refund/subscription lifecycle.
- Optional SMTP env for fulfilment email (keygen + PPI + download link).
- Stripe product should use subscription + 7-day trial for messaging alignment.
