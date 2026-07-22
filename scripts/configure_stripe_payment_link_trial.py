#!/usr/bin/env python3
"""Configure catalog Payment Link for £2.45/month GBP + 7-day trial.

Requires STRIPE_SECRET_KEY in the environment (never committed).

Creates a recurring monthly price (if the current Payment Link price is not
already monthly £2.45) and updates the Payment Link line items + subscription
trial. Prints a redacted JSON summary suitable for deploy evidence.

Usage:
  set STRIPE_SECRET_KEY=sk_live_...
  python scripts/configure_stripe_payment_link_trial.py
  python scripts/configure_stripe_payment_link_trial.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from payments import (  # noqa: E402
    DEFAULT_STRIPE_PAYMENT_LINK_ID,
    DEFAULT_STRIPE_PAYMENT_LINK_PRICE_ID,
    PRICE_CURRENCY,
    PRICE_PENCE,
    desired_payment_link_trial_fields,
    payment_link_matches_trial_subscription,
    stripe_payment_link_id,
    stripe_payment_link_price_id,
    stripe_secret_key,
)


def _stripe_request(
    method: str,
    path: str,
    *,
    secret: str,
    form: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"https://api.stripe.com/v1{path}"
    data = None
    headers = {
        "Authorization": f"Bearer {secret}",
        "User-Agent": "restore-privacy-stripe-trial-config/1.0",
    }
    if form is not None:
        data = urllib.parse.urlencode(form, doseq=True).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
        out = json.loads(raw)
        if isinstance(out, dict):
            return out
        return {"error": "non_object", "raw_type": type(out).__name__}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(body)
        except json.JSONDecodeError:
            err = {"message": body[:500]}
        return {"error": True, "status": exc.code, "body": err}
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {"error": True, "message": str(exc)}


def _redact_price(p: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(p, dict):
        return {}
    rec = p.get("recurring") or {}
    if not isinstance(rec, dict):
        rec = {}
    return {
        "id": p.get("id"),
        "currency": p.get("currency"),
        "unit_amount": p.get("unit_amount"),
        "type": p.get("type"),
        "recurring": {
            "interval": rec.get("interval"),
            "interval_count": rec.get("interval_count"),
            "trial_period_days": rec.get("trial_period_days"),
        },
        "active": p.get("active"),
        "product": p.get("product"),
    }


def _redact_link(pl: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(pl, dict):
        return {}
    items = ((pl.get("line_items") or {}).get("data")) or []
    price_ids = []
    for it in items:
        if isinstance(it, dict):
            pr = it.get("price")
            if isinstance(pr, dict):
                price_ids.append(pr.get("id"))
            elif pr:
                price_ids.append(pr)
    sub_data = pl.get("subscription_data") or {}
    if not isinstance(sub_data, dict):
        sub_data = {}
    return {
        "id": pl.get("id"),
        "url": pl.get("url"),
        "active": pl.get("active"),
        "line_item_price_ids": price_ids,
        "subscription_data_trial_period_days": sub_data.get("trial_period_days"),
        "after_completion": (pl.get("after_completion") or {}).get("type")
        if isinstance(pl.get("after_completion"), dict)
        else None,
    }


def ensure_monthly_price(secret: str, *, dry_run: bool) -> dict[str, Any]:
    """Return a recurring £2.45/month price id (create if needed)."""
    want = desired_payment_link_trial_fields()
    existing_id = stripe_payment_link_price_id() or DEFAULT_STRIPE_PAYMENT_LINK_PRICE_ID
    existing = _stripe_request("GET", f"/prices/{existing_id}", secret=secret)
    if not existing.get("error"):
        # Accept existing if amount/currency/interval match (trial may be on link)
        currency = str(existing.get("currency") or "").lower()
        rec = existing.get("recurring") or {}
        interval = str((rec or {}).get("interval") or "").lower()
        amount = existing.get("unit_amount")
        if (
            currency == want["currency"]
            and amount == want["unit_amount_pence"]
            and interval == want["recurring_interval"]
        ):
            return {
                "action": "reuse_existing_price",
                "price": _redact_price(existing),
                "price_id": existing.get("id"),
            }
        product = existing.get("product")
    else:
        product = None

    if dry_run:
        return {
            "action": "would_create_price",
            "product": product,
            "unit_amount": want["unit_amount_pence"],
            "currency": want["currency"],
            "interval": want["recurring_interval"],
        }

    form: dict[str, Any] = {
        "currency": want["currency"],
        "unit_amount": str(want["unit_amount_pence"]),
        "recurring[interval]": want["recurring_interval"],
        "nickname": "Restore Privacy monthly £2.45 (7-day trial on Payment Link)",
    }
    if product:
        form["product"] = str(product)
    else:
        form["product_data[name]"] = "Restore Privacy subscription"
    created = _stripe_request("POST", "/prices", secret=secret, form=form)
    if created.get("error"):
        return {"action": "create_price_failed", "error": created}
    return {
        "action": "created_price",
        "price": _redact_price(created),
        "price_id": created.get("id"),
    }


def update_payment_link_trial(
    secret: str,
    *,
    price_id: str,
    dry_run: bool,
) -> dict[str, Any]:
    plink = stripe_payment_link_id() or DEFAULT_STRIPE_PAYMENT_LINK_ID
    want = desired_payment_link_trial_fields()
    current = _stripe_request(
        "GET",
        f"/payment_links/{plink}?expand[]=line_items.data.price",
        secret=secret,
    )
    if current.get("error"):
        return {"action": "get_payment_link_failed", "error": current, "payment_link_id": plink}

    if dry_run:
        return {
            "action": "would_update_payment_link",
            "payment_link": _redact_link(current),
            "desired_price_id": price_id,
            "desired_trial_days": want["trial_period_days"],
        }

    # Stripe API: updating line items on Payment Links uses line_items[0][price]
    # and subscription_data[trial_period_days]. Some accounts require inactive
    # then re-create; try update first.
    form = {
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "subscription_data[trial_period_days]": str(want["trial_period_days"]),
    }
    updated = _stripe_request(
        "POST", f"/payment_links/{plink}", secret=secret, form=form
    )
    if updated.get("error"):
        return {
            "action": "update_payment_link_failed",
            "error": updated,
            "before": _redact_link(current),
            "hint": (
                "If Stripe rejects line_items mutation, create a new Payment Link "
                "in Dashboard with monthly price + 7-day trial and set "
                "STRIPE_PAYMENT_PAGE_URL / STRIPE_PAYMENT_LINK_ID on Render."
            ),
        }
    return {
        "action": "updated_payment_link",
        "before": _redact_link(current),
        "after": _redact_link(updated),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Read current objects; do not create price or update link",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write redacted JSON summary to this path",
    )
    args = ap.parse_args(argv)

    secret = stripe_secret_key() or os.environ.get("STRIPE_SECRET_KEY", "").strip()
    summary: dict[str, Any] = {
        "desired": desired_payment_link_trial_fields(),
        "dry_run": bool(args.dry_run),
        "secret_present": bool(secret),
    }
    if not secret:
        summary["ok"] = False
        summary["error"] = "STRIPE_SECRET_KEY not set"
        summary["dashboard_steps"] = [
            "Open https://dashboard.stripe.com/products",
            "Create or open product Restore Privacy subscription",
            "Add recurring price £2.45 GBP / month",
            f"Open Payment Link {DEFAULT_STRIPE_PAYMENT_LINK_ID} "
            f"({desired_payment_link_trial_fields()['payment_page_url']})",
            "Set line item to the monthly price",
            "Under subscription options set trial period = 7 days",
            "Save; confirm checkout shows trial then £2.45/month",
            "If URL changes, set STRIPE_PAYMENT_PAGE_URL + STRIPE_PAYMENT_LINK_ID on Render",
        ]
        text = json.dumps(summary, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        sys.stdout.write(text)
        return 2

    price_result = ensure_monthly_price(secret, dry_run=args.dry_run)
    summary["price"] = price_result
    price_id = str(price_result.get("price_id") or "")
    if not price_id and not args.dry_run:
        summary["ok"] = False
        summary["error"] = "no_price_id"
        text = json.dumps(summary, indent=2) + "\n"
        if args.out:
            args.out.write_text(text, encoding="utf-8")
        sys.stdout.write(text)
        return 1

    if not price_id:
        price_id = stripe_payment_link_price_id() or DEFAULT_STRIPE_PAYMENT_LINK_PRICE_ID

    link_result = update_payment_link_trial(
        secret, price_id=price_id, dry_run=args.dry_run
    )
    summary["payment_link"] = link_result

    # Readback verification
    price_rb = _stripe_request("GET", f"/prices/{price_id}", secret=secret)
    plink = stripe_payment_link_id() or DEFAULT_STRIPE_PAYMENT_LINK_ID
    link_rb = _stripe_request(
        "GET",
        f"/payment_links/{plink}?expand[]=line_items.data.price",
        secret=secret,
    )
    trial_from_link = None
    if isinstance(link_rb, dict) and not link_rb.get("error"):
        sub = link_rb.get("subscription_data") or {}
        if isinstance(sub, dict):
            trial_from_link = sub.get("trial_period_days")
    check_obj = dict(price_rb) if isinstance(price_rb, dict) else {}
    if trial_from_link is not None:
        check_obj["payment_link_trial_period_days"] = trial_from_link
    match = payment_link_matches_trial_subscription(check_obj)
    summary["readback_price"] = _redact_price(price_rb) if not price_rb.get("error") else price_rb
    summary["readback_link"] = _redact_link(link_rb) if not link_rb.get("error") else link_rb
    summary["match"] = match
    # ok if price amount/interval match AND trial is 7 (on price or link)
    summary["ok"] = bool(match.get("ok")) or (
        match.get("observed", {}).get("unit_amount") == PRICE_PENCE
        and match.get("observed", {}).get("interval") == "month"
        and (
            match.get("observed", {}).get("trial_period_days") == 7
            or trial_from_link == 7
        )
    )

    text = json.dumps(summary, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0 if summary.get("ok") or args.dry_run else 1


if __name__ == "__main__":
    raise SystemExit(main())
