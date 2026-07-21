# How to enable paid downloads (£2.45) — Stripe + Buy Me a Coffee

This status site sells **one package download for £2.45 GBP** via **Stripe Checkout**.
Funds settle in **your Stripe account** when you use **live** API keys.

[Buy Me a Coffee](https://buymeacoffee.com/rgsneddon) is linked as **tip / support only**.
It does **not** unlock the paid download (BMC is not the fulfilment API).

The product GitHub repository is **private**. This site does **not** offer free
permanent installer buttons. Payment grants a **single-use, expiring** download
token; `/download` **proxies** the installer via a server-side GitHub token
(`RPT_GITHUB_TOKEN` / `GITHUB_TOKEN`) or locally staged assets (`RPT_ASSET_DIR`).

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

**Option B (Dashboard one-time price only):**

1. Product catalog → **Add product** → name e.g. `Restore Privacy download`.
2. Price: **£2.45**, currency **GBP**, **one-time** (not recurring / subscription).
3. Copy the **Price id** (`price_…`) into **`STRIPE_CHECKOUT_PRICE_ID`** (not the Payment Link price).

**Do not** put a Payment Link **recurring** price in `STRIPE_PRICE_ID` for downloads.
That causes: *You specified payment mode but passed a recurring price*.
Legacy `STRIPE_PRICE_ID` is ignored for Checkout unless `STRIPE_ALLOW_LEGACY_PRICE_ID=1`.

### 1.4 Webhook (required for fulfilment)

After payment, Stripe must notify this site so a download token is minted.
The receiver already runs on the Render status service (same app as the public page).

1. Developers → **Webhooks** → **Add endpoint**.
2. **Endpoint URL** (production — paste exactly):  
   **`https://restore-privacy-status.onrender.com/webhook/stripe`**
3. Events to send: at least **`checkout.session.completed`**.
4. Copy the **Signing secret** (`whsec_…`) → set **`STRIPE_WEBHOOK_SECRET`** on Render
   (Environment) or paste it in `/admin` → Stripe → Save connection.
5. Confirm `RPT_PUBLIC_BASE_URL` = `https://restore-privacy-status.onrender.com` (no trailing slash).

Do **not** invent a second Render service for webhooks — reuse `restore-privacy-status`.

Local testing: [Stripe CLI](https://stripe.com/docs/stripe-cli)

```bash
stripe listen --forward-to localhost:10000/webhook/stripe
stripe trigger checkout.session.completed
```

### 1.5 Environment variables (Render / VPS)

| Variable | Purpose |
|----------|---------|
| `STRIPE_SECRET_KEY` | `sk_test_…` or `sk_live_…` |
| `STRIPE_WEBHOOK_SECRET` | `whsec_…` from the webhook endpoint |
| `STRIPE_PRICE_ID` | Optional `price_…` for £2.45 GBP |
| `RPT_PUBLIC_BASE_URL` | Public site origin, e.g. `https://restore-privacy-status.onrender.com` (no trailing slash). Used for success/cancel URLs. |
| `RPT_PAYMENT_DATA_DIR` | Optional directory for SQLite grant DB (default: `status_page/data/`) |
| `RPT_DOWNLOAD_TOKEN_TTL_SEC` | Optional token lifetime (default `3600`) |
| `RPT_ADMIN_USER` | Admin username (default `admin`) |
| `RPT_ADMIN_PASSWORD` | Admin password (**required** to enable `/admin`) |
| `RPT_ADMIN_SESSION_SECRET` | Optional session HMAC secret (derived from password if omitted) |

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
3. The status page shows this URL as **tip / support only** (`#bmc-tip-link`).  
   **Paying on BMC does not mint a download token** — use Stripe for gated downloads.

---

## 3. Private admin page (operator only)

This is the **private** architecture on the same Render service — not the public catalog.

1. Admin is enabled by a **password digest** shipped in the app (no plaintext secret in git). Prefer setting `RPT_ADMIN_PASSWORD` (and optional `RPT_ADMIN_USER` / `RPT_ADMIN_SESSION_SECRET`) on Render to override/rotate.
2. Open `https://YOUR-STATUS-HOST/admin` (operator only).
3. Sign in with **status-page** credentials (not your Stripe or BMC dashboard passwords). Username defaults to `admin`.
4. After login you get one admin surface:
   - **Payment processor settings (`#admin-processor-settings`)** — each processor is a **plugin** (Stripe paid downloads, BMC tip-only) listing the **correct env variable names** to enter, readiness, and dashboard links. Forms POST to `/admin/processors/apply` (write-only secrets; never echoed). Applied values update the running process and optional local `status_page/data/processor_env.json` (gitignored). Prefer Render env for production permanence.
   - **Paid download grants** — recent Stripe-verified tokens (platform, filename, amount, used/unused, truncated token, session id) for fulfilment support.
5. **Stripe variables:** `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, optional `STRIPE_PRICE_ID`, `RPT_PUBLIC_BASE_URL`.  
   **BMC variables:** `RPT_BMC_TIP_URL`, optional `RPT_BMC_TIP_LABEL`.

Unauthenticated visitors only see the login form; grants and processor readiness are not public.

Architecture (modules):

| Piece | Role |
|-------|------|
| `admin_panel.py` | Login, session, processor settings view, grants HTML |
| `payments.py` | Stripe Checkout, webhook grant mint, SQLite grants |
| `coffee_link.py` | BMC tip URL (public footer + admin tip identity) |
| `app.py` | Routes: public catalog + gated `/admin*` + webhook |

---

## 4. Routes reference

| Path | Role |
|------|------|
| `/` | Status + paid download buttons (£2.45) |
| `/pay?platform=windows` | Redirects to Stripe payment page for that package |
| `/api/checkout` | JSON POST `{ "platform": "android" }` → `{ url, amount_pence: 245, … }` |
| `/webhook/stripe` | Stripe webhook (signature required) |
| `/download?token=` | Single-use **proxy** download of the paid package (not a free GitHub redirect) |
| `/download/success?session_id=` | After Payment Link redirect — **Download \<platform\> package** button |
| `/admin` | **Private** operator page: processor settings + grants (login required) |
| `/admin/login` | Login form / POST credentials |
| `/admin/logout` | Clear session cookie |

**Payment Link after payment (required for seamless UX):** redirect to  
`https://restore-privacy-status.onrender.com/download/success?session_id={CHECKOUT_SESSION_ID}`

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
