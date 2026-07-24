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
| `checkout.session.completed` | Paid checkout → mint one-time download + **activate Connect entitlement** + **unique keygen** + fulfilment email (keygen + PPI + download) |
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

Catalog Payment Links are **subscription** mode. **Monthly** is £2.45/month +
7-day trial; **yearly** uses a separate Payment Link when
`STRIPE_PAYMENT_PAGE_URL_YEARLY` is set (amount from Stripe Dashboard). Trial
starts with `no_payment_required` / £0 + subscription id; after trial, invoices
renew `valid_until`. Refunds/disputes still revoke Connect immediately
(`licence_status` **EXPIRED** on clients).

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


## Keygen unlock (clients)

On `checkout.session.completed` the status host mints a unique **keygen**
(`RPT-KEY-…`) bound to the connect entitlement and includes it in the customer
fulfilment email with **USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY**,
the **PPI**, and the one-time download link.

**Connect allowed = active subscription + keygen activated** (after licence
accept). Download alone does not unlock residual VPN.

Clients: Install → accept licence → enter keygen. Connect re-checks
`/api/connect-entitlement?keygen=…` (returns **`licence_status`**: **OK** or
**EXPIRED**, plus platform **`renew_url`**). Refunds, failed charges, disputes,
and subscription end revoke the entitlement → **EXPIRED** hard-lock with
**renew your licence *here*** and a platform payment portal link until payment
is active again.

SMTP (optional but required to deliver email in production):
`RPT_FULFILMENT_SMTP_HOST`, `RPT_FULFILMENT_SMTP_PORT`, `RPT_FULFILMENT_SMTP_USER`,
`RPT_FULFILMENT_SMTP_PASSWORD`, `RPT_FULFILMENT_FROM_EMAIL`.

## Monthly + yearly Payment Links (env)

| Env | Role |
|-----|------|
| `STRIPE_PAYMENT_PAGE_URL` / `RPT_STRIPE_PAYMENT_PAGE_URL` | Monthly `buy.stripe.com/…` link |
| `STRIPE_PAYMENT_PAGE_URL_YEARLY` / `RPT_STRIPE_PAYMENT_PAGE_URL_YEARLY` | Yearly Payment Link (optional; otherwise monthly URL + `\|year` ref) |
| `STRIPE_PAYMENT_LINK_ID` | Monthly `plink_…` id for admin readiness |

Catalog pay buttons encode `client_reference_id=platform|month` or
`platform|year` for fulfilment.

## Admin licence database (read-only)

`/admin` → **Licence database**: email, KEYGEN, PPI, **OK|EXPIRED** — **view
only**, no amend/edit/revoke controls on that table.

## SMTP fulfilment + Payment Link trial

See [`docs/STATUS_HOST_SMTP_AND_TRIAL.md`](../../docs/STATUS_HOST_SMTP_AND_TRIAL.md)
for Render `RPT_FULFILMENT_SMTP_*` env keys and configuring the catalog monthly
Payment Link for **£2.45/month**
(`scripts/configure_stripe_payment_link_trial.py`).

