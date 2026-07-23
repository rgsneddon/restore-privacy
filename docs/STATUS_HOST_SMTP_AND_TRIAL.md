# Status host: fulfilment SMTP + Stripe 7-day trial Payment Link

## Goal

1. Production status host can send **keygen + PPI + download** fulfilment email
   (SMTP env vars on Render).
2. Catalog **Payment Link** is a **subscription** at **£2.45/month GBP** with a
   **7 day trial**, matching homepage copy:
   *Your monthly subscription (£2.45 per month) begins after your 7 day trial*.

## SMTP env keys (shipped reader)

From `status_page/payments.py` → `fulfilment_smtp_env_keys()` /
`fulfilment_smtp_config()`:

| Key | Role | Blueprint |
|-----|------|-----------|
| `RPT_FULFILMENT_SMTP_HOST` | SMTP hostname | `render.yaml` `sync: false` |
| `RPT_FULFILMENT_SMTP_PORT` | Port (default **587**) | `render.yaml` value `587` |
| `RPT_FULFILMENT_SMTP_USER` | SMTP auth user | `sync: false` |
| `RPT_FULFILMENT_SMTP_PASSWORD` | SMTP auth password | `sync: false` |
| `RPT_FULFILMENT_FROM_EMAIL` | From address | default `noreply@restoreprivacy.online` |
| `RPT_FULFILMENT_SMTP_TLS` | STARTTLS (`1` default) | value `1` |

Also listed on `/admin` Stripe processor variables (`processor_plugins.py`).

**Never commit** SMTP passwords or Stripe secrets.

### Deploy SMTP on Render

**Option A — Dashboard**

1. [Render](https://dashboard.render.com) → service **`restore-privacy-status`** → **Environment**.
2. Add the six keys above (paste real host/user/password from your mail provider).
3. Manual **Deploy** (free tier) so the process picks up env.

**Option B — API script**

```powershell
$env:RENDER_API_KEY = 'rnd_...'   # https://dashboard.render.com/u/settings#api-keys
$env:RPT_FULFILMENT_SMTP_HOST = 'smtp.example.com'
$env:RPT_FULFILMENT_SMTP_USER = 'user'
$env:RPT_FULFILMENT_SMTP_PASSWORD = 'secret'
# optional: PORT, FROM_EMAIL, TLS
.\scripts\set_render_fulfilment_smtp.ps1
```

Then:

```text
curl https://restoreprivacy.online/health
curl https://restoreprivacy.online/health/fulfilment
```

## Private Email (Namecheap) production map

Product fulfilment (keygen + PPI + download after Stripe pay) uses **outbound SMTP only**:

| Env key | Value |
|---------|--------|
| `RPT_FULFILMENT_SMTP_HOST` | `mail.privateemail.com` |
| `RPT_FULFILMENT_SMTP_PORT` | `587` (STARTTLS; shipped send path) |
| `RPT_FULFILMENT_SMTP_USER` | `rus@restoreprivacy.online` |
| `RPT_FULFILMENT_SMTP_PASSWORD` | *(Render env only — never commit)* |
| `RPT_FULFILMENT_FROM_EMAIL` | `rus@restoreprivacy.online` |
| `RPT_FULFILMENT_SMTP_TLS` | `1` |

**Incoming** mailbox protocols (operator mail client only — not used by Stripe or status-host send):

| Protocol | Host | Port |
|----------|------|------|
| IMAP | `mail.privateemail.com` | **993** SSL |
| POP3 | `mail.privateemail.com` | **995** SSL |
| SMTP alternate | `mail.privateemail.com` | **465** SMTPS (not the default ship path) |

Stripe Dashboard **customer receipts** are separate: they need a verified custom
email domain for `restoreprivacy.online` / From `rus@…` — Stripe does **not**
log into IMAP/POP with the mailbox password. See Dashboard → Settings → Customer emails.

## Stripe Payment Links — monthly + yearly

### Monthly — £2.45/month + 7-day trial

| Field | Value |
|-------|--------|
| Payment Link id | `plink_1TvTu6JDavQ2TJW6FeL0dIh9` |
| Public URL | `https://buy.stripe.com/cNi7sM4uOeWQ9TBe0q7kc00` |
| Default price id (may change after recreate) | `price_1TvTsaJDavQ2TJW6HZVIG7hg` |
| Target | recurring **GBP**, **unit_amount 245**, interval **month**, trial **7 days** |

### Yearly (operator-configured)

Create a **yearly** recurring price in Stripe Dashboard and a second Payment
Link. Set on Render (or env):

- `STRIPE_PAYMENT_PAGE_URL_YEARLY` (or `RPT_STRIPE_PAYMENT_PAGE_URL_YEARLY`)

Yearly unit amount is **not** hard-coded in the app — use whatever price you
configure in Stripe. If the yearly env is unset, catalog **Yearly** buttons
still work for architecture: they reuse the monthly Payment Link URL with
`client_reference_id=platform|year` (prefer a real yearly link in production).

### Dashboard steps — monthly (no API key)

1. [Stripe Dashboard → Products](https://dashboard.stripe.com/products) — product for Restore Privacy.
2. Add **recurring** price: **£2.45**, currency **GBP**, billing period **Monthly**.
3. [Payment Links](https://dashboard.stripe.com/payment-links) → open
   `plink_1TvTu6JDavQ2TJW6FeL0dIh9` (or the link currently on the status downloads page).
4. Set the line item to the monthly £2.45 price (subscription mode).
5. Under **subscription** / trial options set **trial period = 7 days**.
6. Save. Open the public URL in a private window: checkout should show
   trial then **£2.45/month**.
7. If Stripe issues a **new** Payment Link URL, set on Render:
   - `STRIPE_PAYMENT_PAGE_URL`
   - `STRIPE_PAYMENT_LINK_ID`
   - (yearly) `STRIPE_PAYMENT_PAGE_URL_YEARLY`
   and redeploy.

### API script (when `STRIPE_SECRET_KEY` is available)

```powershell
$env:STRIPE_SECRET_KEY = 'sk_live_...'   # never commit
python scripts/configure_stripe_payment_link_trial.py --out stripe_payment_link_trial.json
# inspect: dry-run first
python scripts/configure_stripe_payment_link_trial.py --dry-run
```

The script reuses or creates a monthly £2.45 price and updates the Payment Link
`subscription_data[trial_period_days]=7`. If Stripe rejects line-item mutation
on the existing link, use Dashboard recreate (steps above) and update env URLs.

## Verification checklist

| Check | How |
|-------|-----|
| Blueprint declares SMTP keys | `render.yaml` contains all `RPT_FULFILMENT_SMTP_*` |
| App reads same keys | `python -c "from payments import fulfilment_smtp_env_keys; print(fulfilment_smtp_env_keys())"` from `status_page/` |
| Host healthy | `GET https://restoreprivacy.online/health` → `{"ok":true}` (twice) |
| Fulfilment probe | `GET https://restoreprivacy.online/health/fulfilment` → `ok: true` |
| Trial configured | Stripe Dashboard checkout preview **or** script readback JSON with `trial_period_days: 7` and `unit_amount: 245` |

## Code map

| Piece | Path |
|-------|------|
| SMTP config | `status_page/payments.py` (`fulfilment_smtp_config`) |
| Desired trial fields | `status_page/payments.py` (`desired_payment_link_trial_fields`) |
| Render blueprint | `render.yaml` |
| Render SMTP deploy | `scripts/set_render_fulfilment_smtp.ps1` |
| Stripe trial configure | `scripts/configure_stripe_payment_link_trial.py` |
| Admin form fields | `status_page/processor_plugins.py` (Stripe plugin) |
