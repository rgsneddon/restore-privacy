# Subscription keygen unlock — product notes

## Customer flow

1. Install the Suite free. Residual Connect includes a free **3-day (72-hour)
   device trial** (**no card**, no KEYGEN). After the trial ends, residual
   Connect needs a **paid KEYGEN / active subscription**.
2. Buy a KEYGEN on [restoreprivacy.online](https://restoreprivacy.online/) when
   ready: Homepage / `/pay` offer **Monthly VPN plan (£3.00)** (one month) and
   **Yearly VPN plan (£30.00)** (one year). Checkout bills the subscription
   **immediately** (no Stripe free trial — residual free trial is in-app only).
   Customers can **enable or disable auto-renew** before checkout (default: on).
3. Status host on `checkout.session.completed`:
   - mints a **12-hour** download token (reusable until expiry)
   - activates Connect entitlement with **`valid_until`** = Stripe period end
     or calendar **one month / one year** (never unlimited for paid catalog)
   - applies auto-renew preference on the Stripe Subscription
     (`cancel_at_period_end` when auto-renew is off)
   - mints unique **keygen** (`RPT-KEY-…`) bound to that entitlement
   - records **PPI** (product purchase identifier) for operator recovery
   - sends fulfilment email with **keygen + PPI + download link**
4. Client: **Install → accept licence → free residual trial (72h) → enter KEYGEN
   after trial (or anytime) → Connect**.
5. Connect re-checks `/api/connect-entitlement?keygen=…` (or session id). The host
   returns **`licence_status`**: **OK** or **EXPIRED** (trial path uses
   device-entitlement / trial tables until KEYGEN is active).

## Connect allowed = active subscription + keygen activated

| Requirement | Meaning |
|-------------|---------|
| End-user licence accepted | Local acceptance only (not uploaded) |
| Subscription **OK** | Active Stripe-backed entitlement; **`valid_until` not passed**; not revoked/failed |
| **Keygen activated** | User entered valid `RPT-KEY-…` on this install |

**Period end without renewal:** licence becomes **EXPIRED**, Connect is denied,
and residual use is hard-locked until a successful renewal / new paid period
(`invoice.paid` extends `valid_until`).

**Download alone does not unlock residual VPN.** A thank-you
`payment_entitlement.json` with session id only is **not** enough — the app
forces a keygen unlock surface before residual HELLO.

**OK** → full entitled app use (Connect / residual when OS permission allows).  
**EXPIRED** → hard lock: **renew your licence *here*** with a **platform-specific**
Stripe payment portal link (monthly/yearly for that device platform), not a bare
catalog homepage without platform identity.

## Payment failure / subscription end

Stripe webhooks (refund, dispute, failed charge, subscription deleted / period end)
revoke the entitlement. **`valid_until` past** without renewal also yields
**EXPIRED** (even if status was still `active`). Clients re-check on Connect:
status becomes **EXPIRED**, `connect_allowed=false`, and the renew surface opens
(keygen alone will not restore access until payment is active again).

**Auto-renew off:** Stripe `cancel_at_period_end` — access remains until the paid
period ends, then EXPIRED; no further charges after that period.

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
