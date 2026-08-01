# Compulsory pay copy snippets

## SUITE_KEYGEN_HINT
Brand installers require a KEYGEN licence first: start the 3-day free trial (£3.00/month or yearly) — no money is taken until after the trial ends. Enter the KEYGEN from your fulfilment email to unlock residual Connect and downloads.
---
VPN, Perccent wallet (%), and Evolve in one app — start the KEYGEN free trial to download
---
Full business package? (£3000 deposit required)

## suite-pay-hint excerpt
<strong>Start the 3-day free trial first</strong> (Get KEYGEN above) — installers
      refuse anonymous download. After checkout, use your fulfilment KEYGEN and the
      download links (session_id / token from thank-you). Yearly plans are in the
      client box below. Business-Class requires a separate <strong>£3000 deposit</strong>
      on Service.
data-keygen-gated True

## service page deposit
True True True True

## docs
# Suite download (KEYGEN free trial required)

Restore Privacy Suite **v1.0.2** installers are **not** anonymous freebies.
You must start the catalog **KEYGEN** path first — monthly **£3.00** or yearly
**£30.00** with the **3-day free trial** (no money taken until after the trial
ends). Residual Connect also needs that KEYGEN after install.

Download links sit on the public homepage (and on the open `public_site/` Pages
export). Unauthenticated `/suite/download` and `/assets/…` requests **redirect
to `/pay`**. After checkout, use `session_id` / download token / KEYGEN, paste
the KEYGEN from your fulfilment email, then Connect.

Live gated route on the status host: `/suite/download?platform=…`  
(requires `session_id`, `keygen`, or `token` query proof)

**Business-Class / full business package** requires a separate compulsory
**£3000 deposit** via `/pay/commercial-suite` (Service page) — not the KEYGEN
subscription.

**Catalog monopin:** `1.0.2` (`status_page/downloads.py` `RELEASE_VERSION`,
`client/VERSION`).

Open public website (no admin):

- https://rgsneddon.github.io/restore-privacy-suite/
