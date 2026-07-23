# How to enable paid downloads — Stripe + Buy Me a Coffee

This status site sells **Restore Privacy** as a **Stripe subscription**. Catalog
tiles offer **monthly** (**£2.45/month GBP** + **7-day trial**) and **yearly**
Payment Links per platform. Yearly unit amount is set in Stripe Dashboard /
env (`STRIPE_PAYMENT_PAGE_URL_YEARLY`) — not hard-coded as a fixed £ figure.
Funds settle in **your Stripe account** when you use **live** API keys.

[Buy Me a Coffee](https://buymeacoffee.com/rgsneddon) is linked as **tip / support only**.
It does **not** unlock the paid download (BMC is not the fulfilment API).

The product GitHub repository is **private**. This site does **not** offer free
permanent installer buttons. Payment grants a **single-use, expiring** download
token; `/download` **proxies** the installer via a server-side GitHub token
(`RPT_GITHUB_TOKEN` / `GITHUB_TOKEN`) or locally staged assets (`RPT_ASSET_DIR`).

## Deploy: fulfilment SMTP + Stripe 7-day trial

Operator deploy for production email + Payment Link trial is documented in
[`docs/STATUS_HOST_SMTP_AND_TRIAL.md`](../../docs/STATUS_HOST_SMTP_AND_TRIAL.md):

- Render env: `RPT_FULFILMENT_SMTP_*` (blueprint `render.yaml`; script `scripts/set_render_fulfilment_smtp.ps1`)
- Stripe monthly Payment Link: £2.45/month GBP + **7 day trial** (script `scripts/configure_stripe_payment_link_trial.py` when `STRIPE_SECRET_KEY` is set)
- Stripe yearly Payment Link: set **`STRIPE_PAYMENT_PAGE_URL_YEARLY`** (and optional `RPT_STRIPE_PAYMENT_PAGE_URL_YEARLY`) when a Dashboard yearly price exists

## Customer journey (subscription keygen unlock)

1. Homepage shows **ONLY £2.45 per month — or pay yearly**, dual **Monthly** /
   **Yearly** buttons per platform, trial wording for monthly, then pay-on-Stripe.
2. After successful Stripe pay, the status host:
   - mints a one-time download token
   - activates Connect entitlement for the Checkout session
   - mints a unique **keygen** (`RPT-KEY-…`) bound to that entitlement
   - emails the customer: **keygen + PPI + download link**, with
     **USE THIS KEYGEN TO UNLOCK YOUR RESTORE PRIVACY TRIAL**
3. Client first-use flow on every platform:
   **Install → accept licence terms and conditions → enter keygen → unlock**.
   **Connect allowed = active subscription + keygen activated** (download alone
   does not unlock residual VPN).
4. Clients report status **OK** or **EXPIRED** from `/api/connect-entitlement`.
   **OK** = full entitled use. **EXPIRED** (refund, failed charge, dispute,
   subscription end) hard-locks with **renew your licence *here*** and a
   **platform-specific** payment portal link until payment is active again.

### Feasibility of subscription retention

**Feasible** when unlock is **online-validated** against the status host
(keygen → entitlement row tied to Stripe webhooks). Offline-only forever
keygens cannot reliably lock clients after payment failure. This product uses
online re-check on Connect (`client/payment_entitlement.py` and
`/api/connect-entitlement?keygen=…`).

---

## 1. Stripe — land money in your Stripe account

### 1.1 Create / open Stripe

1. Sign up or log in at [https://dashboard.stripe.com](https://dashboard.stripe.com).
2. Complete business verification as Stripe requires for live payouts.
3. Confirm **GBP** is available (Settings → Business → Account details / bank).

### 1.2 API keys

1. Developers → **API keys**.
2. Copy **Secret key** (`sk_test_…` for testing, `sk_live_…` for production).
3. Optional: Publishable key is not required for this Checkout redirect flow.
4. **Never commit** secret keys to git. Set them only on the host (Render env, etc.).

### 1.3 Product price (£2.45)

**Option A (simplest / default):** leave checkout price env empty.  
The app creates Checkout line items with `mode=payment`, `unit_amount=245`, `currency=gbp`.
Server Checkout always sets `customer_creation=always` so **email is required**.

**Option B (Dashboard one-time price only):**

1. Product catalog → **Add product** → name e.g. `Restore Privacy download`.
2. Price: **£2.45**, currency **GBP**, **one-time** (not recurring / subscription).
3. Copy the **Price id** (`price_…`) into **`STRIPE_CHECKOUT_PRICE_ID`** (not the Payment Link price).

**Do not** put a Payment Link **recurring** price in `STRIPE_PRICE_ID` for downloads.
That causes: *You specified payment mode but passed a recurring price*.
Legacy `STRIPE_PRICE_ID` is ignored for Checkout unless `STRIPE_ALLOW_LEGACY_PRICE_ID=1`.

### 1.3b Payment Link — require customer email (live BUY buttons)

Buyers use the **Stripe subscription Payment Link** (`buy.stripe.com/…`), not server Checkout.
Email is required for **subscription** prices.

1. Dashboard → **Payment links** → open the Restore Privacy **subscription** link  
   (`plink_1TvTu6JDavQ2TJW6FeL0dIh9` / URL on the status downloads page).
2. Confirm the line item is **recurring £2.45/month GBP** with **7-day trial**
   (not a one-time donate amount). Use `scripts/configure_stripe_payment_link_trial.py` when `STRIPE_SECRET_KEY` is available.
3. **⋯** → **Edit** (or open settings for the link).
4. Under **Options** / customer information:
   - Ensure email is collected (subscription links always require it).
   - Prefer **Create a Customer** / **customer_creation = always**.
5. Save. New checkouts pick up the setting immediately (no app deploy needed).

API equivalent (with your live secret key, never commit it):

```bash
curl https://api.stripe.com/v1/payment_links/plink_1TvTu6JDavQ2TJW6FeL0dIh9 \
  -u "sk_live_…:" \
  -d "customer_creation=always"
```

Also confirm **Settings → Customer emails** / Checkout branding still send receipts if you want them.

### 1.4 Webhook (required for fulfilment)

After payment, Stripe must notify this site so a download token is minted **and**
Connect entitlement is activated/revoked (including subscription period end).
The receiver already runs on the Render status service (same app as the public page).

1. Developers → **Webhooks** → **Add endpoint**.
2. **Endpoint URL** (production — paste exactly):  
   **`https://restoreprivacy.online/webhook/stripe`**
3. Events to send: **all events listed in**
   [`STRIPE_WEBHOOK_CHECKLIST.md`](STRIPE_WEBHOOK_CHECKLIST.md)
   (not only `checkout.session.completed` — failures, refunds, subscription
   cancel/period-end, and `invoice.paid` are required for Connect revoke).
4. Copy the **Signing secret** (`whsec_…`) → set **`STRIPE_WEBHOOK_SECRET`** on Render
   (Environment) or paste it in `/admin` → Stripe → Save connection.
5. Confirm `RPT_PUBLIC_BASE_URL` = `https://restoreprivacy.online` (no trailing slash).

**Subscription cancel:** product stays usable until `current_period_end`; after that
Connect and residual HELLO are refused. See the checklist doc.

Do **not** invent a second Render service for webhooks — reuse `restore-privacy-status`.

Local testing: [Stripe CLI](https://stripe.com/docs/stripe-cli)

```bash
stripe listen --forward-to localhost:10000/webhook/stripe
stripe trigger checkout.session.completed
```

### 1.5 Environment variables (Render / VPS)

| Variable | Purpose |
|----------|---------|
| `STRIPE_SECRET_KEY` | `sk_test_…` or `sk_live_…` (Dashboard → Developers → API keys) |
| `STRIPE_WEBHOOK_SECRET` | `whsec_…` from the webhook endpoint (Dashboard → Webhooks → Signing secret) |
| `STRIPE_PAYMENT_PAGE_URL` | Monthly catalog Payment Link URL (`buy.stripe.com/…`); also `RPT_STRIPE_PAYMENT_PAGE_URL` |
| `STRIPE_PAYMENT_PAGE_URL_YEARLY` | Yearly catalog Payment Link URL; also `RPT_STRIPE_PAYMENT_PAGE_URL_YEARLY`. Optional — if unset, yearly tiles reuse the monthly URL with `client_reference_id=platform\|year` |
| `STRIPE_PAYMENT_LINK_ID` | Monthly Payment Link object id (`plink_…`); also `RPT_STRIPE_PAYMENT_LINK_ID` |
| `STRIPE_CHECKOUT_PRICE_ID` | Optional one-time `price_…` only; **leave empty** to use built-in `unit_amount=245` (£2.45) |
| `RPT_PUBLIC_BASE_URL` | Public site origin, e.g. `https://restoreprivacy.online` (no trailing slash). Used for success/cancel URLs. |
| `RPT_ASSET_FETCH_TOKEN` | Shared secret (you choose) for status host → Iceland VPS paid installer fetch; same value on VPS unit |
| `RPT_PAYMENT_DATA_DIR` | Optional directory for SQLite grant DB (default: `status_page/data/`) |
| `RPT_DOWNLOAD_TOKEN_TTL_SEC` | Optional token lifetime (default `3600`) |
| `RPT_FULFILMENT_SMTP_HOST` | Optional SMTP host for customer fulfilment email (keygen + PPI + download) |
| `RPT_FULFILMENT_SMTP_PORT` | SMTP port (default `587`) |
| `RPT_FULFILMENT_SMTP_USER` / `RPT_FULFILMENT_SMTP_PASSWORD` | SMTP auth |
| `RPT_FULFILMENT_FROM_EMAIL` | From address (default `noreply@restoreprivacy.online`) |
| `RPT_FULFILMENT_SMTP_TLS` | `1` (default) enable STARTTLS |
| `RPT_ADMIN_USER` | Admin username (default `admin`) |
| `RPT_ADMIN_PASSWORD` | Admin password (**required** to enable `/admin`) |
| `RPT_ADMIN_SESSION_SECRET` | Optional session HMAC secret (derived from password if omitted) |

**Admin Save behaviour:** secret fields are write-only (always empty on reload). After you paste a key and click **Save**, the table badge flips to **set**. Leave a field blank on a later Save to **keep** the stored value — blanks never wipe secrets. Values go to process env + gitignored `status_page/data/processor_env.json`. On free Render, also set the same keys under **Environment** so redeploys keep them.

### 1.6 Test mode vs live

1. Use **test** keys + test card `4242 4242 4242 4242` until the flow works.
2. Switch webhook to the live endpoint, set **live** secret key + live webhook secret.
3. Confirm a real £2.45 payment appears in the Stripe Dashboard **Payments** list and payouts schedule.

### 1.7 Success / cancel URLs

Checkout success URL pattern (set automatically from `RPT_PUBLIC_BASE_URL`):

- Success: `/download/success?session_id={CHECKOUT_SESSION_ID}&platform=…`
- Cancel: `/download/cancel?platform=…`

After payment, Stripe redirects to the success page with **`session_id`**. That page:

1. Looks up the webhook-minted grant by Checkout session id (polls a few seconds if the webhook is slightly late).
2. Shows a **one-time** link: `/download?token=…` (`#success-download-link`).

You may also surface the token from admin grants if a buyer contacts support.

---

## 2. Buy Me a Coffee — tips (not paid download)

1. Claim or log into [https://buymeacoffee.com/rgsneddon](https://buymeacoffee.com/rgsneddon).
2. Complete payout settings in the BMC creator dashboard so tips land in your linked account.
3. The VPN APP Shop shows this URL as **tip / support only** (`#bmc-tip-link`).  
   **Paying on BMC does not mint a download token** — use Stripe for gated downloads.

---

## 3. Private admin page (operator only)

This is the **private** architecture on the same Render service — not the public catalog.

1. Admin is enabled by a **password digest** shipped in the app (no plaintext secret in git). Prefer setting `RPT_ADMIN_PASSWORD` (and optional `RPT_ADMIN_USER` / `RPT_ADMIN_SESSION_SECRET`) on Render to override/rotate.
2. Open `https://YOUR-STATUS-HOST/admin` (operator only).
3. Sign in with **VPN APP Shop** credentials (not your Stripe or BMC dashboard passwords). Username defaults to `admin`.
4. After login you get one admin surface:
   - **Payment processor settings (`#admin-processor-settings`)** — each processor is a **plugin** (Stripe paid downloads, BMC tip-only) listing the **correct env variable names** to enter, readiness, and dashboard links. Forms POST to `/admin/processors/apply` (write-only secrets; never echoed). Applied values update the running process and optional local `status_page/data/processor_env.json` (gitignored). Prefer Render env for production permanence.
   - **Licence database (`#admin-licences`)** — **read-only** table of customer **email**, **KEYGEN**, **PPI**, and status **OK|EXPIRED** (plus platform). **Info only — no edit, revoke, or amend controls** on this table.
   - **Paid download grants** — recent Stripe-verified tokens (platform, filename, amount, used/unused, truncated token, session id) for fulfilment support.
5. **Stripe variables:** `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PAYMENT_PAGE_URL`, optional `STRIPE_PAYMENT_PAGE_URL_YEARLY`, optional `STRIPE_CHECKOUT_PRICE_ID`, `RPT_PUBLIC_BASE_URL`.  
   **VPS assets:** `RPT_ASSET_FETCH_TOKEN` (and optional `RPT_VPS_ASSET_BASE`).  
   **BMC variables:** `RPT_BMC_TIP_URL`, optional `RPT_BMC_TIP_LABEL`.

Unauthenticated visitors only see the login form; grants, licence rows, and processor readiness are not public.

Architecture (modules):

| Piece | Role |
|-------|------|
| `admin_panel.py` | Login, session, processor settings, read-only licence DB, grants HTML |
| `payments.py` | Stripe Payment Links / Checkout, webhook grant mint, keygen, licence_status OK\|EXPIRED |
| `downloads.py` | Public catalog: monthly + yearly pay tiles per platform |
| `coffee_link.py` | BMC tip URL (public footer + admin tip identity) |
| `app.py` | Routes: public catalog + gated `/admin*` + webhook |

---

## 4. Routes reference

| Path | Role |
|------|------|
| `/` | Status + monthly/yearly paid download buttons per platform |
| `/pay?platform=windows` | Redirects to Stripe payment page for that package |
| `/api/checkout` | JSON POST `{ "platform": "android" }` → `{ url, amount_pence: 245, … }` |
| `/webhook/stripe` | Stripe webhook (signature required) |
| `/download?token=` | Single-use **proxy** download of the paid package (not a free GitHub redirect) |
| `/download/success?session_id=` | After Payment Link redirect — **Download \<platform\> package** button |
| `/admin` | **Private** operator page: processor settings + grants (login required) |
| `/admin/login` | Login form / POST credentials |
| `/admin/logout` | Clear session cookie |

**Payment Link after payment (required for seamless UX):** redirect to  
`https://restoreprivacy.online/download/success?session_id={CHECKOUT_SESSION_ID}`  

Paste **exactly** that (no trailing `&platform=`). Stripe cannot expand a
platform placeholder. Each homepage BUY tile already opens the Payment Link
with `?client_reference_id=<platform>`; the success page resolves that from
the Checkout Session so the thank-you URL becomes
`/download/success?session_id=cs_…&platform=windows` (etc.).

**Private source repo:** make GitHub **private**, then either set **`RPT_GITHUB_TOKEN`** on Render **or** stage packages  
(`python scripts/stage_paid_assets.py` → `status_page/assets/0.3.0/`). See `docs/PRIVATE_REPO_AND_PAID_DOWNLOADS.md`.

---

## 5. Security notes

- Never commit `sk_live_`, `whsec_`, or admin passwords.
- Webhook **must** verify `Stripe-Signature` (implemented in `payments.py`).
- Tokens are single-use and time-limited; invalid/expired tokens do not download.
- Public status HTML must not expose free permanent `releases/download` installer buttons.
- With a **private** repo, unpaid browsers cannot fetch installers; paid buyers get them only via token + server proxy.

## Success page UX

After payment redirect, `/download/success` shows **Thank you**, names the **platform package you paid for**, auto-starts the one-time `/download?token=…` installer (proxy stream), and instructs **run as administrator**. A fallback **Download \<platform\> package** button remains if the browser blocks auto-download.
