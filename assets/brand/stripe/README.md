# Stripe Branding assets

Exported from `../primary_transparent_1024.png` for
[Dashboard → Branding](https://dashboard.stripe.com/settings/branding).

**Transparent-background PNGs (required):** RGBA with clear corners (alpha 0),
not a solid navy/opaque plate. The site’s `status_page/static/logo.png` is
**not** used for Stripe (it is fully opaque).

| File | Use | Size |
|------|-----|------|
| `stripe_brand_icon.png` | Stripe **Icon** (square) | 512×512 PNG **transparent** |
| `stripe_brand_logo.png` | Stripe **Logo** (wide) | 1280×512 PNG **transparent canvas** |

Constraints (Stripe + this repo): PNG RGBA, ≥128×128, &lt;512 KB; icon square;
meaningful transparent canvas + visible mark.

Upload:

```bash
export STRIPE_SECRET_KEY=sk_live_...
python scripts/upload_stripe_branding_assets.py
```

Platform account branding **attach** via API is often 403 — set logo/icon and
colours `#2694e8` / `#0a1628` in the Dashboard if so.
