# Subscription keygen unlock — product notes

## Customer flow

1. Pay on [restoreprivacy.online](https://restoreprivacy.online/). Catalog tiles
   offer **Monthly £2.45** and **Yearly** per platform (Stripe subscription
   Payment Links; yearly amount is operator/Stripe-configured). Homepage copy
   includes **ONLY £2.45 per month — or pay yearly**, trial language for the
   monthly plan, and pay-on-Stripe wording.
2. Status host on `checkout.session.completed`:
   - mints one-time download token
   - activates Connect entitlement for the Checkout session
   - mints unique **keygen** (`RPT-KEY-XXXX-XXXX-XXXX`) bound to that entitlement
   - records **PPI** (product purchase identifier) for operator recovery
   - sends fulfilment email with **keygen + PPI + download link** and the sentence
     **USE THIS KEYGEN TO UNLOCK YOUR RESTORE PRIVACY TRIAL**
3. Client: **Install → accept licence terms → enter keygen → unlock Connect**.
4. Connect re-checks `/api/connect-entitlement?keygen=…` (or session id). The host
   returns **`licence_status`**: **OK** or **EXPIRED**.

## Connect allowed = active subscription + keygen activated

| Requirement | Meaning |
|-------------|---------|
| End-user licence accepted | Local acceptance only (not uploaded) |
| Subscription **OK** | Active Stripe-backed entitlement; period not ended; not revoked/failed |
| **Keygen activated** | User entered valid `RPT-KEY-…` on this install |

**Download alone does not unlock residual VPN.** A thank-you
`payment_entitlement.json` with session id only is **not** enough — the app
forces a keygen unlock surface before residual HELLO.

**OK** → full entitled app use (Connect / residual when OS permission allows).  
**EXPIRED** → hard lock: **renew your licence *here*** with a **platform-specific**
Stripe payment portal link (monthly/yearly for that device platform), not a bare
catalog homepage without platform identity.

## Payment failure / subscription end

Stripe webhooks (refund, dispute, failed charge, subscription deleted / period end)
revoke the entitlement. Clients re-check on Connect: status becomes **EXPIRED**,
`connect_allowed=false`, and the renew surface opens (keygen alone will not
restore access until payment is active again).

## Admin (operator) — read-only licence database

Admin `/admin` → **Licence database** shows **email**, **KEYGEN**, **PPI**, and
status **OK|EXPIRED** (plus platform) for information only.

- **Read-only** — no edit, revoke, or amend controls on that table.
- Separate admin tools (re-issue by PPI, failsafe KEYGEN mint) exist elsewhere;
  they are **not** amend powers on the licence table itself.

## Feasibility of subscription retention

**Feasible** when unlock stays **online-validated** against the status host
entitlement row (Stripe-backed). Offline-only keygens cannot reliably disable
clients after payment failure — do not ship offline forever unlock.

Operator: configure monthly + yearly Stripe Payment Links; set
`STRIPE_PAYMENT_PAGE_URL` (monthly) and `STRIPE_PAYMENT_PAGE_URL_YEARLY`
(yearly — optional; without it yearly tiles reuse the monthly link with a
`|year` client_reference_id marker). Set `RPT_FULFILMENT_SMTP_*` so fulfilment
email delivers in production.

## Code map

| Area | Module |
|------|--------|
| Homepage monthly/yearly tiles | `status_page/downloads.py` |
| Keygen mint / email / revoke / licence status | `status_page/payments.py` |
| API lookup | `GET /api/connect-entitlement?keygen=` (returns `licence_status`, `renew_url`) |
| Admin read-only licence table | `status_page/admin_panel.py` |
| Python clients (OK/EXPIRED, renew *here*) | `client/licence_gate.py`, `client/payment_entitlement.py`, Windows/Linux apps |
| Flutter | `client_app/lib/licence_gate.dart`, `main.dart` |
| Operator docs | `status_page/docs/PAID_DOWNLOADS_HOWTO.md`, `STRIPE_WEBHOOK_CHECKLIST.md` |
