# Stripe Custom domains, custom email domain, DMARC, and branding

This note answers: what
[Custom domains](https://dashboard.stripe.com/settings/custom-domains)
does, how to verify **Customer emails** custom domain DNS (ownership / mail-from /
DKIM), how to publish **DMARC**, whether payments feel “seamless”, and how to
brand Checkout as close as possible to https://restoreprivacy.online/
(logo + colours).

Shipped code constants (palette + asset paths + DNS helpers) live in
`status_page/payments.py` → `stripe_checkout_branding_guide()`,
`stripe_email_domain_dns_expected()`, `dmarc_policy_expected()`.

**DNS zone:** `restoreprivacy.online`  
**Nameservers (live):** `dns1.registrar-servers.com` / `dns2.registrar-servers.com` (Namecheap).  
**Mailbox provider:** PrivateEmail (`mx1`/`mx2.privateemail.com`, SPF
`include:spf.privateemail.com`) — keep for `rus@` + status-host SMTP; do **not**
replace root SPF when adding Stripe email CNAMEs.

---

## 0. Operator DNS map (Namecheap Advanced DNS)

Paste values **from Stripe Dashboard** where marked *(Dashboard)*. Never invent
ACME / ownership / DKIM targets offline. Namecheap **Host** = left label only
(provider appends `.restoreprivacy.online` — **do not double-append**).

### A) Checkout custom domain (`pay.`)

Dashboard: [Custom domains](https://dashboard.stripe.com/settings/custom-domains)

| Type | Host (Namecheap) | Value | Purpose |
|------|------------------|-------|---------|
| **CNAME** | `pay` | `hosted-checkout.stripecdn.com` | `pay.restoreprivacy.online` → Stripe Checkout CDN |
| **TXT** | `_acme-challenge.pay` | *(Dashboard → View instructions)* | ACME / TLS ownership |

### B) Customer emails custom domain

Dashboard: [Customer emails](https://dashboard.stripe.com/settings/emails) → add
`restoreprivacy.online` → **View instructions**. Docs:
[Custom email domain](https://docs.stripe.com/get-started/account/email-domain).

| Category | Type | Host (Namecheap) | Value | Purpose |
|----------|------|------------------|-------|---------|
| Ownership | **TXT** | *(from Dashboard)* | *(from Dashboard)* | Stripe proof-of-ownership |
| Mail From | **CNAME** | *(from Dashboard, e.g. bounce…)* | *(from Dashboard)* | Bounce / mail-from for SPF path |
| DKIM | **CNAME** | *(from Dashboard, often `*._domainkey`…)* | *(from Dashboard)* | Message signing (usually several rows) |

**Rules**

- CNAME host must not already have A/AAAA/MX/TXT at the **same** name.
- Do not Cloudflare-proxy (orange cloud) Stripe CNAMEs if NS ever moves to CF.
- TTL Automatic or 5 minutes while verifying; can take up to **72 hours**.
- After Stripe shows **Verified**, leave records in place (Stripe re-checks).

### C) DMARC (required for Stripe custom email domain)

Stripe requires a DMARC policy and does **not** support strict SPF alignment —
**do not** set `aspf=s`.

| Type | Host (Namecheap) | Value |
|------|------------------|-------|
| **TXT** | `_dmarc` | `v=DMARC1; p=none; rua=mailto:rus@restoreprivacy.online; pct=100` |

Start with `p=none` (monitor). Later raise to `quarantine` / `reject` when
reports look clean. This coexists with existing PrivateEmail SPF/MX.

### D) Existing mail (leave alone unless Dashboard explicitly says otherwise)

| Type | Host | Value (live) | Purpose |
|------|------|--------------|---------|
| **MX** | `@` | `mx1` / `mx2.privateemail.com` | Inbox for `rus@…` |
| **TXT** (SPF) | `@` | `v=spf1 include:spf.privateemail.com ~all` | Authorised senders for mailbox SMTP |
| **CNAME** | `mail` | `privateemail.com` | PrivateEmail host alias |

Stripe email-domain setup uses **its own CNAME set** for mail-from/DKIM — do
**not** delete PrivateEmail SPF just to “make Stripe happy.” Only merge root SPF
if Dashboard explicitly shows a second SPF include (rare; prefer Stripe CNAMEs).

### Verify (shipped)

```bash
# DMARC + SPF + optional Dashboard rows + pay Checkout DNS
python scripts/verify_stripe_email_domain_dns.py
python scripts/verify_stripe_email_domain_dns.py --out stripe_email_dns_report.json

# Optional: after you paste Dashboard rows into a local JSON (do not commit):
# [{"category":"ownership","type":"TXT","host":"…","value":"…"}, …]
python scripts/verify_stripe_email_domain_dns.py --records stripe_email_domain_dns.local.json

# Checkout custom domain only (+ optional live Session host)
python scripts/verify_stripe_custom_domain.py
# STRIPE_SECRET_KEY=sk_live_... python scripts/verify_stripe_custom_domain.py --create-session
```

Helpers: `payments.dmarc_policy_expected()`, `parse_dmarc_policy()`,
`stripe_email_domain_dns_expected()`, `verify_dmarc_dns()`,
`verify_stripe_email_domain_dns()`, `verify_stripe_custom_domain_dns()`.

**Automation limits:** no public Stripe API for Customer emails DNS tokens or
Custom domains ACME TXT; Namecheap write needs operator login (no monorepo API
token). Repo work ships structure + public verify + Namecheap paste steps —
Dashboard **Verified** appears only after Stripe accepts your live DNS.

---

## 1. What Custom domains is

**Location:** Stripe Dashboard → **Settings** → **Custom domains**  
(URL shape: `…/settings/custom-domains`)

**What it does**

- Lets **Stripe-hosted** surfaces (Checkout, Payment Links, Customer Portal)
  appear on a **subdomain of your own domain**, e.g.  
  `https://pay.restoreprivacy.online/…`  
  instead of only `https://checkout.stripe.com/…` or `https://buy.stripe.com/…`.
- You prove domain ownership with **DNS** records Stripe shows you
  (typically **CNAME** for the subdomain + often **TXT** for verification).
- After verification, new Checkout Sessions / Payment Links can use that host.

**What it is not**

Custom domains does not inject the website’s full CSS. Summary:

| Myth | Reality |
|------|---------|
| “Payment runs on my site origin like `/pay` HTML.” | No. Hosting is still **Stripe’s servers**; only the **hostname** is yours. |
| “I inject the website’s full CSS into Checkout.” | No. Custom domains does not load `public_chrome` CSS, Tailwind, or any site stylesheet. |
| “Free for all accounts.” | Custom domains is a **paid Checkout feature** (see Stripe pricing / feature availability for your country and product). |
| “Path under the status host is enough” (e.g. `restoreprivacy.online/checkout`). | **Not supported.** You need a **subdomain** (e.g. `pay.`) pointed at Stripe via DNS, not a path on the Render status app alone. |

**Seamless for the customer?**

| Aspect | With Custom domains | Without |
|--------|---------------------|---------|
| URL trust / brand | Higher — address bar shows *your* domain | `checkout.stripe.com` / `buy.stripe.com` |
| Visual look | Still Stripe Checkout chrome | Same |
| Full site CSS / layout | **No** | **No** |
| Card data handling | Still Stripe PCI scope | Same |

**Recommendation for Restore Privacy**

1. Keep the homepage **Download client** box (device + plan + **Buy now**) —
   that form already uses full main-site CSS.
2. Optionally enable **Custom domains** for `pay.restoreprivacy.online` so the
   redirect after Buy now feels on-brand in the address bar.
3. Always set **Branding** (logo + colours) so Checkout is as close as Stripe
   allows to the site palette (see §2).

**Operator DNS — Namecheap zone `restoreprivacy.online` (live NS)**

NS today: `dns1.registrar-servers.com` / `dns2.registrar-servers.com` (Namecheap).

| Type | Host (Namecheap) | Value | Purpose |
|------|------------------|-------|---------|
| **CNAME** | `pay` | `hosted-checkout.stripecdn.com` | Maps `pay.restoreprivacy.online` → Stripe Checkout CDN |
| **TXT** | `_acme-challenge.pay` | *(copy from Dashboard → View instructions)* | ACME / TLS ownership proof |

1. Open [Custom domains](https://dashboard.stripe.com/settings/custom-domains) →
   **Add your domain** → `pay.restoreprivacy.online` (paid Checkout feature,
   ~USD 10/month). Leave **Switch to this domain once added** on if you want
   auto-enable.
2. **View instructions** → copy the exact **TXT** value (not inventable offline).
3. Namecheap → Domain List → **manage** → **Advanced DNS** for
   `restoreprivacy.online` → add the CNAME + TXT rows above (TTL 5 min / Automatic).
4. Wait until Stripe shows **Ready** / **Active**. After DNS is correct,
   the Dashboard may say it is **making sure DNS records are stable**
   (often **at least 3 hours**) and will email when done — leave records
   alone unless Stripe reports a failure. TLS on
   `https://pay.restoreprivacy.online` can succeed (valid cert) while
   Sessions still use `checkout.stripe.com` until the domain is fully
   enabled / switched.
5. If DNS + TLS are fine but Checkout Session URLs still use
   `checkout.stripe.com`, stay on the Custom domains page and **switch /
   activate** the domain — there is no public API for that step.
6. Verify:

```bash
dig @8.8.8.8 +short CNAME pay.restoreprivacy.online
# → hosted-checkout.stripecdn.com.
dig @8.8.8.8 +short TXT _acme-challenge.pay.restoreprivacy.online
# → non-empty ACME token from Stripe
python scripts/verify_stripe_custom_domain.py --create-session
# session url_host should be pay.restoreprivacy.online
# brand_trust_ready should be true
```

Shipped helpers: `payments.stripe_custom_domain_dns_expected()`,
`verify_stripe_custom_domain_dns()`, `checkout_session_uses_custom_domain()`.

Homepage **Buy now** already uses **server-side** Session create + redirect to
`session.url` (required for custom domains).

**Automation limits:** there is **no** public Stripe API to register Checkout
custom domains or read the ACME TXT; Namecheap DNS write needs operator
login/API credentials (not stored in this monorepo).

---

## 2. Branding Checkout to match the site (logo + colours)

Full site-CSS parity on Stripe-hosted Checkout is **not available**. Closest path:

### Dashboard locations

1. **Settings → Branding** (account logo, icon, primary/secondary colours)  
   https://dashboard.stripe.com/settings/branding  
2. **Settings → Checkout** / Checkout appearance (where present for your account)  
3. **Settings → Custom domains** (optional URL seamlessness — §1)

Logo upload and account branding for **your own** Stripe account are done in the
**Dashboard** (the platform Account API refuses self-updates with “connected
accounts only”).

### Logo / icon assets (Stripe Branding constraints)

Stripe accepts **JPG or PNG**, each **≥ 128×128 px**, file size **&lt; 512 KB**.
**Icon** must be **square**. **Logo** may be wider.

This repo ships **transparent-background PNG (RGBA)** only for Stripe icon/logo:
corner pixels have **alpha 0** (not a solid navy fill). Do **not** upload the
opaque site `status_page/static/logo.png` for Stripe Branding.

| Role | Path (shipped) | Notes |
|------|----------------|-------|
| **Icon** (square) | `assets/brand/stripe/stripe_brand_icon.png` | 512×512 **transparent** PNG from `primary_transparent_1024.png` |
| **Logo** (wide) | `assets/brand/stripe/stripe_brand_logo.png` | 1280×512 PNG, mark centered on **transparent** canvas |
| Public copies | `status_page/static/stripe_brand_{icon,logo}.png` | Same bytes; served as `/stripe_brand_icon.png` etc. |
| Source master | `assets/brand/primary_transparent_1024.png` | Transparent master — do not invent alternate art |

Also keep site favicon/logo for the status host itself:
`status_page/static/logo.png`, `favicon.png`.

**Automated upload (Files API)**

```bash
export STRIPE_SECRET_KEY=sk_live_...   # never commit
python scripts/upload_stripe_branding_assets.py --out stripe_brand_upload.json
```

- Uploads with purpose `business_icon` / `business_logo`.
- **Attach** via `POST /v1/account` often returns **403** on the platform account
  (“connected accounts only”). File ids still appear in Stripe Files.
- **Finish in Dashboard → Branding:** set Logo + Icon (use the shipped PNGs or
  the uploaded files) and colours primary **`#2694e8`**, secondary **`#0a1628`**.

Last uploaded file ids (refresh by re-running the script) are stored in
`payments.py` as `STRIPE_BRAND_*_FILE_ID`.

### Colour map (from public site theme)

Source: `status_page/public_chrome.py` dark theme CSS variables.

| Dashboard field | Hex | Site token / meaning |
|-----------------|-----|----------------------|
| **Primary colour** (buttons / accents) | `#2694e8` | `--rb-btn` / neon blue |
| **Secondary colour** (backgrounds / contrast) | `#0a1628` | `--rb-navy` |
| Optional accent reference | `#00e5ff` | `--rb-neon-cyan` (not always a Dashboard field) |
| Button text (site) | `#ffffff` | `--rb-btn-text` |

Use **dark navy + blue buttons** so Checkout feels continuous with the VPN APP Shop.

Shipped single source of truth:

```text
python -c "import sys; sys.path.insert(0,'status_page'); from payments import stripe_checkout_branding_guide; import json; print(json.dumps(stripe_checkout_branding_guide(), indent=2))"
```

### What Buy now still does

Homepage form → `POST /pay/checkout` → Stripe **subscription** Checkout Session
(Monthly / Yearly VPN plan, subscription starts when you pay). Branding and custom domains do
**not** change fulfilment webhooks or amounts.

---

## 3. “Can we utilise Custom domains for a seamless flow?”

**Yes, for URL seamlessness — not for full UI merge.**

| Goal | Achievable with Custom domains + Branding? |
|------|--------------------------------------------|
| Customer sees `pay.restoreprivacy.online` | Yes (after DNS + paid feature) |
| Same navy/blue look + logo on Checkout | Yes (Dashboard Branding) |
| Payment form looks identical to `#downloads` box HTML/CSS | **No** |
| Card fields embedded with full site CSS (no Stripe page) | Only via **Stripe Elements / embedded Checkout** rebuild — **out of scope** here |

---

## 4. Related code map

| Piece | Path |
|-------|------|
| Homepage Buy now form | `status_page/downloads.py` (`render_homepage_buy_form_html`) |
| Checkout Session create | `status_page/payments.py` (`create_subscription_checkout_session`) |
| Branding guide helper | `status_page/payments.py` (`stripe_checkout_branding_guide`) |
| Customer-facing honesty line | `STRIPE_CHECKOUT_BRANDING_NOTE` in `downloads.py` |
| Public CSS tokens | `status_page/public_chrome.py` |
| Logo file | `status_page/static/logo.png` |
