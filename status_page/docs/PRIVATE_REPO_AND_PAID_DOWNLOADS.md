# Private repo + paid downloads (operator checklist)

## Goal

- Source repo **private** → browsers cannot grab free `github.com/.../releases/download/...` installers.
- Buyers still get the package they paid for via the **status host** after Stripe.

## Verified (live)

| Check | Result |
|-------|--------|
| `github.com/rgsneddon/restore-privacy` (unauthenticated) | **404** — not publicly cloneable / browsable |
| Free release asset URL (unauthenticated) | **404** — no free installer grab |
| Status home download buttons | Stripe Payment Link + `client_reference_id=<platform>` only |
| Free `releases/download` hrefs on status HTML | **None** |
| `GET /health/fulfilment` | Must be **200** with `"ok": true` (local staged assets or `RPT_GITHUB_TOKEN`) |

If fulfilment returns **503**, paying customers cannot download until you stage assets or set a GitHub token (below).

## Buyer path (seamless)

1. Status downloads → Stripe Payment Link  
   `https://donate.stripe.com/cNi7sM4uOeWQ9TBe0q7kc00?client_reference_id=<platform>`
2. Stripe **After payment → Redirect to**  
   `https://restoreprivacy.online/download/success?session_id={CHECKOUT_SESSION_ID}`  
   (required — already configured for seamless thank-you)
3. Webhook `POST https://restoreprivacy.online/webhook/stripe`  
   event **`checkout.session.completed`** → mints one-time token for that platform  
   (requires `payment_status` paid + **245** pence GBP + platform from `client_reference_id` / metadata)
4. Success page shows **Download \<platform\> package** → `/download?token=…`  
   streams installer via **proxy** (local staged file or GitHub API token)

## Make / keep GitHub private

```text
GitHub → rgsneddon/restore-privacy → Settings → General → Danger zone
  → Change visibility → Private
```

Unauthenticated API/HTML already 404 as of operator verification — keep it **Private**.  
Collaborators and Render still need a token (or staged files) for fulfilment.

This environment cannot flip visibility without `gh auth` / `GH_TOKEN`.

## Fulfilment when the repo is private (preferred: Iceland VPS)

Paid installers for **each device** (windows / android / macos / ios / linux) are hosted on the product VPS and streamed by the status host after Stripe pays.

### Operator: collect + host on Iceland (`82.221.101.241`)

```bash
# List one package per platform
python scripts/host_paid_assets_vps.py --list

# Stage from releases/0.3.0 → status_page/assets/0.3.0
python scripts/host_paid_assets_vps.py --stage

# Upload each device package to /opt/restore-privacy/paid_assets/0.3.0/
# and install token-gated HTTP serve on :8081
export RPT_SSH_USER=raskul RPT_SSH_SUDO=1
export RPT_SSH_KEY=~/.ssh/id_ed25519_restore_privacy_vps
export RPT_ASSET_FETCH_TOKEN='long-random-secret'   # same value on Render
python scripts/host_paid_assets_vps.py --stage --upload --install-serve

# If packages already uploaded: only (re)start the serve unit
python scripts/host_paid_assets_vps.py --install-serve-only
```

Layout on VPS: `/opt/restore-privacy/paid_assets/{version}/{filename}`  
HTTP (token only): `http://82.221.101.241:8081/paid-assets/{version}/{filename}`  
Header: `X-RPT-Asset-Token: <RPT_ASSET_FETCH_TOKEN>` — **401 without token** (not free).

### Render env (status host)

| Variable | Purpose |
|----------|---------|
| `RPT_VPS_ASSET_BASE` | `http://82.221.101.241:8081/paid-assets` |
| `RPT_ASSET_FETCH_TOKEN` | Same secret as VPS `rpt-paid-assets.service` |
| `STRIPE_SECRET_KEY` | Optional server Checkout; webhook verification uses signing secret |
| `STRIPE_WEBHOOK_SECRET` | Required for grants (`whsec_…`) |

Fallbacks (optional): local `status_page/assets/{version}/`, or `RPT_GITHUB_TOKEN` for private GitHub release API.

## Stripe env (Render) — also see table above

| Variable | Purpose |
|----------|---------|
| `STRIPE_SECRET_KEY` | Optional server Checkout; webhook verification uses signing secret |
| `STRIPE_WEBHOOK_SECRET` | Required for grants (`whsec_…`) |
| `RPT_PUBLIC_BASE_URL` | `https://restoreprivacy.online` |
| `RPT_GITHUB_TOKEN` | Private release asset fetch if not staging files |

## Payment Link amount (critical for seamless grants)

Webhook grants only when paid amount is **245 pence (GBP)** and currency is **gbp**.

- Prefer a **fixed £2.45 one-time** Payment Link (not a free-amount tip).
- Variable / donate-only amounts that are not exactly 245p will **not** mint installers — the buyer pays but the success page stays on “Confirming with Stripe…”.

## Client in-app update

`client/ui_theme.upgrade_download_url()` opens the **paid** Windows path (Payment Link), never a free GitHub release URL.

## Verify

```text
# Free grab blocked
curl -sI "https://github.com/rgsneddon/restore-privacy/releases/download/0.3.0/..."  → 404

# Status paywall
curl -s https://restoreprivacy.online/ | findstr /i "donate.stripe releases/download"
  → donate.stripe present; releases/download absent

# Fulfilment ready for paid proxy
curl -s https://restoreprivacy.online/health/fulfilment
  → {"ok": true, "source": "local"|"github_api"|...}

# After a £2.45 test payment for one platform:
# success page → Download <platform> package → installer streams once
```
