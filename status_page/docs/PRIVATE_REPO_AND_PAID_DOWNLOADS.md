# Private repo + paid downloads (operator checklist)

## Goal

- Source repo **private** → browsers cannot grab free `github.com/.../releases/download/...` installers.
- Buyers still get the package they paid for via the **status host** after Stripe.

## Buyer path (seamless)

1. Status downloads → Stripe Payment Link  
   `https://donate.stripe.com/cNi7sM4uOeWQ9TBe0q7kc00?client_reference_id=<platform>`
2. Stripe **After payment → Redirect to**  
   `https://restore-privacy-status.onrender.com/download/success?session_id={CHECKOUT_SESSION_ID}`  
   (you already set this)
3. Webhook `POST https://restore-privacy-status.onrender.com/webhook/stripe`  
   event **`checkout.session.completed`** → mints one-time token for that platform  
   (requires paid status + **245** pence GBP + `client_reference_id` / metadata)
4. Success page shows **Download \<platform\> package** → `/download?token=…`  
   streams installer via **proxy** (local staged file or GitHub API token)

## Make GitHub private

```text
GitHub → rgsneddon/restore-privacy → Settings → General → Danger zone → Change visibility → Private
```

This environment cannot flip visibility without `gh auth` / `GH_TOKEN`.

## Fulfilment when the repo is private (pick one)

| Method | Render env / disk |
|--------|-------------------|
| **A. GitHub token** | `RPT_GITHUB_TOKEN` or `GITHUB_TOKEN` with `contents:read` on the private repo |
| **B. Staged files** | Copy catalog packages to `status_page/assets/0.3.0/` on the host (see `scripts/stage_paid_assets.py`) |

Local monorepo also searches `releases/0.3.0/` (gitignored).

## Stripe env (Render)

| Variable | Purpose |
|----------|---------|
| `STRIPE_SECRET_KEY` | Optional server Checkout; webhook verification uses signing secret |
| `STRIPE_WEBHOOK_SECRET` | Required for grants (`whsec_…`) |
| `RPT_PUBLIC_BASE_URL` | `https://restore-privacy-status.onrender.com` |
| `RPT_GITHUB_TOKEN` | Private release asset fetch if not staging files |

## Payment Link amount

Webhook grants only when paid amount is **245 pence (GBP)**.  
If the Payment Link price is not £2.45 one-time, create a matching one-time price or adjust product pricing code — underpay / donate-only amounts will not mint installers.

## Verify

- `GET /health/fulfilment` → `{"ok":true,"source":"local"|"github_api"|…}` when assets/token work  
- Public HTML has **no** free `releases/download` installer buttons  
- After a test payment: success page → download starts for the chosen platform only  
