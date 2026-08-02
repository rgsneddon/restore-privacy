# Status host: fulfilment SMTP + site plan page + Stripe subscription Checkout

## Goal

1. Production status host can send **keygen + PPI + download** fulfilment email
   (SMTP env vars on Render).
2. Catalog routes to the site **Select your plan** page (`/pay`) for
   **Monthly VPN plan (£3.00/month)** or **Yearly VPN plan (£30.00/year)**
   with a **3-day free trial** (no money taken until after the trial ends), then Stripe **subscription** Checkout Session.

## SMTP env keys (shipped reader)

**One config drives two product mail paths:**

| Path | Module | Behaviour |
|------|--------|-----------|
| Keygen / fulfilment after Stripe | `payments.send_fulfilment_email` | Customer download + KEYGEN email |
| Support tickets (open + close) | `support_tickets.send_support_ticket_email` | Staff notify (`rus@`) + close notify to customer |

Both call `fulfilment_smtp_config()` / `RPT_FULFILMENT_SMTP_*` (and admin
`processor_env.json` when set). There is **no** separate support SMTP secret.

Readiness: `GET /health/fulfilment` and `?smtp_probe=1` report `smtp_status` /
`smtp_probe` **and** `support_ticket_email_enabled` / `support_ticket_smtp`.

From `status_page/payments.py` → `fulfilment_smtp_env_keys()` /
`fulfilment_smtp_config()`:

| Key | Role | Blueprint |
|-----|------|-----------|
| `RPT_FULFILMENT_SMTP_HOST` | SMTP hostname | `render.yaml` `sync: false` |
| `RPT_FULFILMENT_SMTP_PORT` | Port (default **587**) | `render.yaml` value `587` |
| `RPT_FULFILMENT_SMTP_USER` | SMTP auth user | `sync: false` |
| `RPT_FULFILMENT_SMTP_PASSWORD` | SMTP auth password | `sync: false` |
| `RPT_FULFILMENT_FROM_EMAIL` | From address | **Must be owned by the SMTP user** (use `rus@restoreprivacy.online` with PrivateEmail). Default falls back to SMTP user / `rus@…` — **not** `noreply@` (providers return **553** if From is foreign). |
| `RPT_FULFILMENT_SMTP_TLS` | STARTTLS (`1` default) | value `1` |

Also listed on `/admin` Stripe processor variables (`processor_plugins.py`).

**PrivateEmail 553:** login can succeed while `send_message` fails if From is e.g. `noreply@…` but auth user is `rus@…`. Set `RPT_FULFILMENT_FROM_EMAIL=rus@restoreprivacy.online` (same as USER). The send path also coerces From to the authenticated user when they differ.

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

### Two emails after pay (do not confuse them)

| Channel | What the customer gets | Download token? |
|---------|------------------------|-----------------|
| **Stripe receipt / invoice** | Payment PDF, amount, “Questions? Contact us…” | **No** — Stripe cannot host `/download?token=…` |
| **Status-host fulfilment SMTP** | Keygen + PPI + **absolute download link** + **12-hour** retry advice | **Yes** — only place the installer link is emailed |

After `checkout.session.completed`, the status host builds and sends the fulfilment
email (`build_fulfilment_email_payload` / `send_fulfilment_email`) when SMTP is
configured and Checkout has a customer email. Body includes
`DOWNLOAD_LINK_VALIDITY_ADVICE` (12 hours, re-download if interrupted) and
`Questions? Contact us at rus@restoreprivacy.online`. From display name **RASKUL**,
Reply-To **rus@restoreprivacy.online**.

### Stripe public brand (receipt footer “Russell Sneddon” → RASKUL)

Stripe shows the account **public business name** on Checkout and receipt footers.
Set it to **RASKUL** and support email to **rus@restoreprivacy.online**:

1. [Public details](https://dashboard.stripe.com/settings/public) → **Public business name** = `RASKUL`
2. Same page / Customer emails → **Support email** = `rus@restoreprivacy.online` (Questions? Contact us at…)
3. Optional API (when `STRIPE_SECRET_KEY` is set):

```bash
python scripts/configure_stripe_public_profile.py --dry-run
python scripts/configure_stripe_public_profile.py
```

Platform accounts may 403 some Account API fields — finish remaining fields in Dashboard.
Shipped guide: `payments.stripe_public_business_guide()`.

Stripe Dashboard **customer receipts** still need a verified custom email domain for
`restoreprivacy.online` / From `rus@…` — Stripe does **not** log into IMAP/POP with
the mailbox password. See Dashboard → Settings → Customer emails and the full DNS
table (ownership TXT, mail-from/DKIM CNAMEs, **DMARC** at `_dmarc`, Checkout `pay.`
rows) in
[STRIPE_CUSTOM_DOMAINS_AND_BRANDING.md](STRIPE_CUSTOM_DOMAINS_AND_BRANDING.md) §0.
Verify with `python scripts/verify_stripe_email_domain_dns.py`.

## Stripe products — Monthly / Yearly VPN plan (3-day free trial)

Catalog **primary path** is site-hosted `/pay` → Checkout Session (not dual
`buy.stripe.com` Payment Links).

| Plan | Product name | Unit amount | Interval | Default price id |
|------|--------------|-------------|----------|------------------|
| Monthly | Monthly VPN plan | **300** pence (£3.00) | month | `price_1Tz8mgJDavQ2TJW6M6mB9c7x` |
| Yearly | Yearly VPN plan | **3000** pence (£30.00 fixed yearly) | year | `price_1Tz8miJDavQ2TJW6T0G7B1iD` |

Old product **download a vpn** is archived. Override price ids with
`STRIPE_PRICE_ID_MONTHLY` / `STRIPE_PRICE_ID_YEARLY` if you rotate Dashboard prices.

### Dashboard steps (no API key)

1. [Stripe Dashboard → Products](https://dashboard.stripe.com/products) — create
   **Monthly VPN plan** and **Yearly VPN plan** (or open the shipped products).
2. Recurring prices: **£3.00 GBP / month** and **£30.00 GBP / year**. Catalog Checkout applies a **3-day free trial**.
3. Ensure status host has `STRIPE_SECRET_KEY` + webhook so `/pay/checkout` can
   create subscription Checkout Sessions.
4. Confirm catalog tiles open `/pay?platform=…` and the plan page shows
   Select your plan Monthly | Annual with **SAVE ~17%** on annual (vs 12 × monthly).

### API script (when `STRIPE_SECRET_KEY` is available)

```powershell
$env:STRIPE_SECRET_KEY = 'sk_live_...'   # never commit
python scripts/configure_stripe_payment_link_trial.py --out stripe_payment_link_trial.json
# inspect: dry-run first
python scripts/configure_stripe_payment_link_trial.py --dry-run
```

The script reuses or creates monthly £3.00 and yearly **£30.00** (3000 pence)
prices and asserts catalog **trial_period_days = 3** on Checkout. Prefer Checkout Session price ids over
legacy Payment Links for catalog.

## Verification checklist

| Check | How |
|-------|-----|
| Blueprint declares SMTP keys | `render.yaml` contains all `RPT_FULFILMENT_SMTP_*` |
| App reads same keys | `python -c "from payments import fulfilment_smtp_env_keys; print(fulfilment_smtp_env_keys())"` from `status_page/` |
| Host healthy | `GET https://restoreprivacy.online/health` → `{"ok":true}` (twice) |
| Fulfilment probe | `GET https://restoreprivacy.online/health/fulfilment` → `ok: true` |
| 3-day trial + monthly/yearly | Desired fields: `trial_period_days` **3**; monthly `300`; yearly **`3000`**; products Monthly/Yearly VPN plan |
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
