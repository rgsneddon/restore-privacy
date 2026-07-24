# Status host: fulfilment SMTP + site plan page + Stripe subscription Checkout

## Goal

1. Production status host can send **keygen + PPI + download** fulfilment email
   (SMTP env vars on Render).
2. Catalog routes to the site **Select your plan** page (`/pay`) for
   **Monthly VPN plan (£2.45/month)** or **Yearly VPN plan (£27.93/year, 5% off)**
   with **subscription starts when you pay**, then Stripe **subscription** Checkout Session.

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

## Stripe products — Monthly / Yearly VPN plan (no trial)

Catalog **primary path** is site-hosted `/pay` → Checkout Session (not dual
`buy.stripe.com` Payment Links).

| Plan | Product name | Unit amount | Interval | Default price id |
|------|--------------|-------------|----------|------------------|
| Monthly | Monthly VPN plan | **245** pence (£2.45) | month | `price_1TwjilJDavQ2TJW6fyxzCIkA` |
| Yearly | Yearly VPN plan | **2793** pence (£27.93 = 5% off 12×£2.45) | year | `price_1TwjimJDavQ2TJW6wEKr4upj` |

Old product **download a vpn** is archived. Override price ids with
`STRIPE_PRICE_ID_MONTHLY` / `STRIPE_PRICE_ID_YEARLY` if you rotate Dashboard prices.

### Dashboard steps (no API key)

1. [Stripe Dashboard → Products](https://dashboard.stripe.com/products) — create
   **Monthly VPN plan** and **Yearly VPN plan** (or open the shipped products).
2. Recurring prices: **£2.45 GBP / month** and **£27.93 GBP / year** (no trial).
3. Ensure status host has `STRIPE_SECRET_KEY` + webhook so `/pay/checkout` can
   create subscription Checkout Sessions.
4. Confirm catalog tiles open `/pay?platform=…` and the plan page shows
   Select your plan Monthly | Annual with **SAVE 5%** on annual.

### API script (when `STRIPE_SECRET_KEY` is available)

```powershell
$env:STRIPE_SECRET_KEY = 'sk_live_...'   # never commit
python scripts/configure_stripe_payment_link_trial.py --out stripe_payment_link_trial.json
# inspect: dry-run first
python scripts/configure_stripe_payment_link_trial.py --dry-run
```

The script reuses or creates monthly £2.45 and yearly **£27.93** (2793 pence)
prices and asserts **subscription starts when you pay**. Prefer Checkout Session price ids over
legacy Payment Links for catalog.

## Verification checklist

| Check | How |
|-------|-----|
| Blueprint declares SMTP keys | `render.yaml` contains all `RPT_FULFILMENT_SMTP_*` |
| App reads same keys | `python -c "from payments import fulfilment_smtp_env_keys; print(fulfilment_smtp_env_keys())"` from `status_page/` |
| Host healthy | `GET https://restoreprivacy.online/health` → `{"ok":true}` (twice) |
| Fulfilment probe | `GET https://restoreprivacy.online/health/fulfilment` → `ok: true` |
| No trial + monthly/yearly | Desired fields: `trial_period_days` 0; monthly `245`; yearly **`2793`**; products Monthly/Yearly VPN plan |
| Catalog entry | Homepage tiles → `/pay?platform=…` (site plan page) |

## Code map

| Piece | Path |
|-------|------|
| SMTP config | `status_page/payments.py` (`fulfilment_smtp_config`) |
| Desired trial fields | `status_page/payments.py` (`desired_payment_link_trial_fields`) |
| Render blueprint | `render.yaml` |
| Render SMTP deploy | `scripts/set_render_fulfilment_smtp.ps1` |
| Stripe trial configure | `scripts/configure_stripe_payment_link_trial.py` |
| Admin form fields | `status_page/processor_plugins.py` (Stripe plugin) |
