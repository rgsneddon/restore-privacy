# Subscription keygen unlock — product notes

## Customer flow

1. Pay on [restoreprivacy.online](https://restoreprivacy.online/) (homepage copy:
   **£2.45 per package** → **Your monthly subscription (£2.45 per month) begins after your 7 day trial** → pay on Stripe).
2. Status host on `checkout.session.completed`:
   - mints one-time download token
   - activates Connect entitlement for the Checkout session
   - mints unique **keygen** (`RPT-KEY-XXXX-XXXX-XXXX`) bound to that entitlement
   - sends fulfilment email with **keygen + PPI + download link** and the sentence
     **USE THIS KEYGEN TO UNLOCK YOUR RESTORE PRIVACY TRIAL**
3. Client: **Install → accept licence terms → enter keygen → unlock Connect**.
4. Connect re-checks `/api/connect-entitlement?keygen=…` (or session id). Only an
   **active** entitlement unlocks residual use.

## Payment failure / subscription end

Stripe webhooks (refund, dispute, failed charge, subscription deleted / period end)
revoke the entitlement. The same keygen then returns `connect_allowed=false` and
clients lock Connect until a new successful payment / active period.

## Feasibility of subscription retention

**Feasible** when unlock stays **online-validated** against the status host
entitlement row (Stripe-backed). Offline-only keygens cannot reliably disable
clients after payment failure — do not ship offline forever unlock.

Operator: configure Stripe subscription + 7-day trial on the Payment Link for
messaging alignment; set `RPT_FULFILMENT_SMTP_*` env vars so fulfilment email
actually delivers in production.

## Code map

| Area | Module |
|------|--------|
| Homepage price copy | `status_page/downloads.py` |
| Keygen mint / email / revoke | `status_page/payments.py` |
| API lookup | `GET /api/connect-entitlement?keygen=` |
| Python clients | `client/licence_gate.py`, `client/payment_entitlement.py`, Windows/Linux Settings |
| Flutter | `client_app/lib/licence_gate.dart`, `settings_screen.dart` |
| Operator docs | `status_page/docs/PAID_DOWNLOADS_HOWTO.md`, `STRIPE_WEBHOOK_CHECKLIST.md` |
