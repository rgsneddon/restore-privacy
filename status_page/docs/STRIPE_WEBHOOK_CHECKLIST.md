# Stripe Dashboard webhook checklist

Paste this into **Stripe Dashboard → Developers → Webhooks → Add endpoint**
(or edit the existing `restoreprivacy.online` endpoint).

## Endpoint URL

```
https://restoreprivacy.online/webhook/stripe
```

Signing secret (`whsec_…`) → Render env **`STRIPE_WEBHOOK_SECRET`** only (never commit).

Success return URL template:

```
https://restoreprivacy.online/download/success?session_id={CHECKOUT_SESSION_ID}

**Do not** add `&platform=` (or empty `platform=`) to this URL. Stripe only
substitutes `{CHECKOUT_SESSION_ID}`. Platform is set by each BUY tile as
`client_reference_id=windows` (etc.) on the Payment Link; the success page
reads it from the Checkout Session and fills the browser URL.
```

## Events to select (required)

| Event | Purpose |
|-------|---------|
| `checkout.session.completed` | Paid checkout → mint one-time download + **activate Connect entitlement** |
| `checkout.session.async_payment_failed` | Async pay fail → **revoke Connect** |
| `checkout.session.expired` | Expired unpaid checkout → revoke if any |
| `payment_intent.payment_failed` | Card/charge fail → **revoke Connect** |
| `charge.failed` | Charge fail → revoke |
| `charge.refunded` | Refund → **revoke Connect** (status `revoked`) |
| `charge.dispute.created` | Dispute → revoke |
| `invoice.payment_failed` | Invoice fail (subscription dunning). If the subscription still has remaining paid period (`valid_until`), Connect stays usable until that time; otherwise revoke |
| `invoice.paid` | Invoice paid → renew subscription `valid_until` / keep active |
| `customer.subscription.updated` | Cancel-at-period-end → **keep usable until `current_period_end`** |
| `customer.subscription.deleted` | Subscription ended → **revoke Connect** (end of period after cancel, or immediate cancel) |

Source of truth in code: `status_page/payments.py` → `STRIPE_WEBHOOK_EVENTS` and
`STRIPE_WEBHOOK_EVENT_PURPOSE`. Admin `/admin` processor panel also shows the endpoint URL.

## Subscription cancel behaviour

1. Customer cancels with **cancel at period end** → Stripe sends
   `customer.subscription.updated` (`cancel_at_period_end=true`).
2. Status host keeps Connect entitlement **active** with `valid_until = current_period_end`.
3. App and residual **node** keep working until that timestamp.
4. When the period ends, Stripe sends `customer.subscription.deleted` → Connect is
   **revoked** (client gate + bound device removed; node HELLO refuses that device).

One-time Payment Link downloads (current default £2.45) have no period end unless
refunded/disputed (immediate revoke).

## Node residual HELLO

After pay, the app binds the local device Ed25519 public key to the Checkout
session (`POST /api/bind-device-entitlement`). The product node checks
`GET /api/device-entitlement?device_pub=…` and **silently drops** CLIENT_HELLO when
not entitled (`RPT_REQUIRE_PAYMENT_ENTITLEMENT=1` on the node process).

## Local test (optional)

```bash
stripe listen --forward-to localhost:10000/webhook/stripe
stripe trigger checkout.session.completed
```
