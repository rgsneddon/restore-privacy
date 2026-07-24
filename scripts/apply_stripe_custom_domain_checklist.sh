#!/usr/bin/env bash
# One-shot checklist for pay.restoreprivacy.online Stripe Checkout custom domain.
# This cannot invent Stripe's ACME TXT or write Namecheap DNS without credentials.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DOMAIN="pay.restoreprivacy.online"
CNAME_TARGET="hosted-checkout.stripecdn.com"
TXT_HOST="_acme-challenge.pay"
DASH="https://dashboard.stripe.com/settings/custom-domains"
NC="https://ap.www.namecheap.com/Domains/DomainControlPanel/restoreprivacy.online/advancedns"

echo "=== Stripe Custom domain: $DOMAIN ==="
echo
echo "1) Stripe Dashboard (required — no public API for Checkout custom domains):"
echo "   $DASH"
echo "   → Add domain: $DOMAIN"
echo "   → Leave «Switch to this domain once added» ON"
echo "   → View instructions → COPY the TXT value"
echo
echo "2) Namecheap Advanced DNS for restoreprivacy.online:"
echo "   $NC"
echo "   CNAME  Host=pay Value=$CNAME_TARGET"
echo "   TXT    Host=$TXT_HOST        Value=<paste from Stripe>"
echo
echo "   (Host fields without the zone: CNAME host is 'pay', TXT host is '_acme-challenge.pay')"
echo
echo "3) After Stripe shows Ready/Active, run:"
echo "   python3 scripts/verify_stripe_custom_domain.py --create-session"
echo "   Expect url_host=$DOMAIN"
echo
echo "=== Current public DNS (system + 8.8.8.8) ==="
echo -n "CNAME $DOMAIN (system) → "
dig +short CNAME "$DOMAIN" || true
echo -n "CNAME $DOMAIN (@8.8.8.8) → "
dig @8.8.8.8 +short CNAME "$DOMAIN" || true
echo -n "TXT $TXT_HOST.restoreprivacy.online (@8.8.8.8) → "
dig @8.8.8.8 +short TXT "_acme-challenge.pay.restoreprivacy.online" || true
echo
echo "=== HTTPS readiness (TLS cert from Stripe; handshake-fail = not Ready yet) ==="
curl -4 -sS -o /dev/null -w "https://$DOMAIN → http_code=%{http_code} err_check_stderr\n" \
  --max-time 10 "https://$DOMAIN" 2>&1 || true
echo
echo "=== Live verification script ==="
export STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY:-}"
if [[ -z "${STRIPE_SECRET_KEY}" && -f secrets/stripe_secret_key ]]; then
  STRIPE_SECRET_KEY="$(tr -d '\n' < secrets/stripe_secret_key)"
  export STRIPE_SECRET_KEY
fi
python3 scripts/verify_stripe_custom_domain.py --create-session || true

# Optional: open dashboards on macOS when DISPLAY/GUI available
if command -v open >/dev/null 2>&1; then
  echo
  echo "Opening Dashboard pages in browser (if GUI available)…"
  open "$DASH" 2>/dev/null || true
  open "$NC" 2>/dev/null || true
fi
