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
   `https://buy.stripe.com/cNi7sM4uOeWQ9TBe0q7kc00?client_reference_id=<platform>`
2. Payment Link must **require email** (subscription does; or set
   `customer_creation=always` on the link — see PAID_DOWNLOADS_HOWTO §1.3b).
3. Stripe **After payment → Redirect to**  
   `https://restoreprivacy.online/download/success?session_id={CHECKOUT_SESSION_ID}`  
   (required — **no** `&platform=` empty suffix; platform comes from BUY tile
   `client_reference_id` and is filled on the success page)
4. Webhook `POST https://restoreprivacy.online/webhook/stripe`  
   event **`checkout.session.completed`** → mints 1-hour reusable token for that platform  
   (requires `payment_status` paid + **300** pence GBP (monthly) or **3000** (yearly) + platform from `client_reference_id` / metadata)
5. Success page shows **Download \<platform\> package** → `/download?token=…`  
   streams installer via **proxy** (local staged file or GitHub API token)

## Make / keep GitHub private

```text
GitHub → rgsneddon/restore-privacy → Settings → General → Danger zone
  → Change visibility → Private
```

Unauthenticated API/HTML already 404 as of operator verification — keep it **Private**.  
Collaborators and Render still need a token (or staged files) for fulfilment.

This environment cannot flip visibility without `gh auth` / `GH_TOKEN`.

## Fulfilment when the repo is private (preferred: Helsinki store)

Paid installers for **each device** (windows / android / macos / ios / linux) are hosted on a **dedicated Helsinki** store host and streamed by the status host after Stripe pays. The Iceland residual monopin (`82.221.101.241`) is **node-only** — not an installer CDN.

### Every commit: assure current per-device packages

Install once per clone so **each commit** fails if catalog pin / `client/VERSION` /
five device filenames drift (buyers always get the **current** package identity):

```bash
python scripts/install_commit_package_task.py
# or: python scripts/install_commit_package_task.py --force

# Manual check / list
python scripts/assure_current_packages.py --check
python scripts/assure_current_packages.py --list
```

After a real release version bump, re-stage and upload to **Helsinki**
(`host_paid_assets_vps.py`) so fulfilment binaries match the new pin.

### Operator: collect + host on Helsinki (`135.181.152.10`)

```bash
# List one package per platform
python scripts/host_paid_assets_vps.py --list

# Stage from releases/{VERSION} → status_page/assets/{VERSION}
python scripts/host_paid_assets_vps.py --stage

# Upload each device package to /opt/restore-privacy/paid_assets/{VERSION}/
# and install token-gated HTTP serve on the store host
export RPT_SSH_HOST=135.181.152.10 RPT_SSH_USER=root
export RPT_SSH_KEY=~/.ssh/id_ed25519_20260725
export RPT_ASSET_FETCH_TOKEN='long-random-secret'   # same value on Render
python scripts/host_paid_assets_vps.py --stage --upload --install-serve

# If packages already uploaded: only (re)start the serve unit
python scripts/host_paid_assets_vps.py --install-serve-only

# One-time: remove paid installer tree from Iceland residual node
export RPT_SSH_HOST=82.221.101.241 RPT_SSH_USER=raskul RPT_SSH_SUDO=1
export RPT_SSH_KEY=~/.ssh/id_ed25519_restore_privacy_vps
python scripts/host_paid_assets_vps.py --remove-iceland-paid-assets
```

Layout on store: `/opt/restore-privacy/paid_assets/{version}/{filename}`  
HTTP (token only): `https://135.181.152.10.sslip.io/paid-assets/{version}/{filename}`  
(or `http://135.181.152.10:8081/paid-assets/...`)  
Header: `X-RPT-Asset-Token: <RPT_ASSET_FETCH_TOKEN>` — **401 without token** (not free).

### Render env (status host)

| Variable | Purpose |
|----------|---------|
| `RPT_VPS_ASSET_BASE` | `https://135.181.152.10.sslip.io/paid-assets` |
| `RPT_ASSET_FETCH_TOKEN` | Same secret as store `rpt-paid-assets.service` |
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

Webhook grants when paid amount matches catalog (**300** pence monthly or **3000** yearly GBP) and currency is **gbp**.

- Prefer **subscription** Checkout: **monthly £3.00/month GBP** or **yearly £30.00/year** via site `/pay` (not a free-amount tip or one-time donate).
- Variable / tip-only amounts that are not catalog 300/3000 pence will **not** mint installers — the buyer pays but the success page stays on “Confirming with Stripe…”.

## Client in-app update

`client/ui_theme.upgrade_download_url()` opens the **paid** Windows path (Payment Link), never a free GitHub release URL.

## Verify

```text
# Free grab blocked
curl -sI "https://github.com/rgsneddon/restore-privacy/releases/download/0.3.0/..."  → 404

# Status paywall
curl -s https://restoreprivacy.online/ | findstr /i "buy.stripe client_reference_id releases/download"
  → buy.stripe + client_reference_id present; releases/download absent

# Fulfilment ready for paid proxy
curl -s https://restoreprivacy.online/health/fulfilment
  → {"ok": true, "source": "local"|"github_api"|...}

# After a £3.00 test payment for one platform:
# success page → Download <platform> package → installer streams once
```
