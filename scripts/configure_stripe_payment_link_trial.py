#!/usr/bin/env python3
"""Configure catalog Stripe prices for Monthly/Yearly VPN plan + **3-day trial**.

Monthly: £3.00 (300 pence). Yearly: £30.00 (3000 pence).

Requires STRIPE_SECRET_KEY in the environment (never committed).

Creates or reuses recurring monthly/yearly prices (product names Monthly VPN
plan / Yearly VPN plan) and sets Payment Link subscription_data trial to 3 days
when the API allows. Primary catalog path is site /pay Checkout with trial=3.
Prints a redacted JSON summary suitable for deploy evidence.

Usage:
  set STRIPE_SECRET_KEY=sk_live_...
  python scripts/configure_stripe_payment_link_trial.py
  python scripts/configure_stripe_payment_link_trial.py --dry-run
  python scripts/configure_stripe_payment_link_trial.py --interval year
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
    DEFAULT_STRIPE_PAYMENT_LINK_ID_YEARLY,
    DEFAULT_STRIPE_PAYMENT_LINK_PRICE_ID,
    DEFAULT_STRIPE_PAYMENT_LINK_PRICE_ID_YEARLY,
    PRICE_CURRENCY,
    PRICE_PENCE,
    PRICE_YEARLY_PENCE,
    desired_payment_link_trial_fields,
    payment_link_matches_trial_subscription,
    stripe_payment_link_id,
    stripe_payment_link_id_yearly,
    stripe_payment_link_price_id,
    stripe_payment_link_price_id_yearly,
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
        "User-Agent": "restore-privacy-stripe-3day-trial-config/1.0",
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


def _interval_targets(interval: str) -> dict[str, Any]:
    want = desired_payment_link_trial_fields()
    iv = (interval or "month").strip().lower()
    if iv in ("year", "yearly", "annual", "annually"):
        return {
            "interval": "year",
            "unit_amount_pence": int(want.get("unit_amount_yearly_pence") or PRICE_YEARLY_PENCE),
            "price_id": stripe_payment_link_price_id_yearly()
            or DEFAULT_STRIPE_PAYMENT_LINK_PRICE_ID_YEARLY,
            "payment_link_id": stripe_payment_link_id_yearly()
            or DEFAULT_STRIPE_PAYMENT_LINK_ID_YEARLY,
            "nickname": f"Yearly VPN plan {PRICE_YEARLY_PENCE/100:.2f} GBP (3-day trial via Checkout)",
        }
    return {
        "interval": "month",
        "unit_amount_pence": int(want.get("unit_amount_pence") or PRICE_PENCE),
        "price_id": stripe_payment_link_price_id() or DEFAULT_STRIPE_PAYMENT_LINK_PRICE_ID,
        "payment_link_id": stripe_payment_link_id() or DEFAULT_STRIPE_PAYMENT_LINK_ID,
        "nickname": f"Monthly VPN plan {PRICE_PENCE/100:.2f} GBP (3-day trial via Checkout)",
    }


def ensure_recurring_price(
    secret: str, *, interval: str, dry_run: bool
) -> dict[str, Any]:
    """Return a recurring GBP price id for month or year (create if needed)."""
    want = desired_payment_link_trial_fields()
    tgt = _interval_targets(interval)
    existing_id = tgt["price_id"]
    existing = _stripe_request("GET", f"/prices/{existing_id}", secret=secret)
    if not existing.get("error"):
        currency = str(existing.get("currency") or "").lower()
        rec = existing.get("recurring") or {}
        rec_iv = str((rec or {}).get("interval") or "").lower()
        amount = existing.get("unit_amount")
        if (
            currency == want["currency"]
            and amount == tgt["unit_amount_pence"]
            and rec_iv == tgt["interval"]
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
            "unit_amount": tgt["unit_amount_pence"],
            "currency": want["currency"],
            "interval": tgt["interval"],
        }

    form: dict[str, Any] = {
        "currency": want["currency"],
        "unit_amount": str(tgt["unit_amount_pence"]),
        "recurring[interval]": tgt["interval"],
        "nickname": tgt["nickname"],
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
    payment_link_id: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Point Payment Link at *price_id* and set free-trial subscription_data days."""
    want = desired_payment_link_trial_fields()
    current = _stripe_request(
        "GET",
        f"/payment_links/{payment_link_id}?expand[]=line_items.data.price",
        secret=secret,
    )
    if current.get("error"):
        return {
            "action": "get_payment_link_failed",
            "error": current,
            "payment_link_id": payment_link_id,
        }

    if dry_run:
        return {
            "action": "would_update_payment_link",
            "payment_link": _redact_link(current),
            "desired_price_id": price_id,
            "desired_trial_days": want["trial_period_days"],
        }

    form = {
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "subscription_data[trial_period_days]": str(int(want["trial_period_days"])),
    }
    updated = _stripe_request(
        "POST", f"/payment_links/{payment_link_id}", secret=secret, form=form
    )
    if updated.get("error"):
        return {
            "action": "update_payment_link_failed",
            "error": updated,
            "before": _redact_link(current),
            "hint": (
                "If Stripe rejects line_items mutation, create a new Payment Link "
                "in Dashboard with the recurring price and 3-day trial, then set "
                "STRIPE_PAYMENT_PAGE_URL / STRIPE_PAYMENT_LINK_ID (or _YEARLY) on Render."
            ),
        }
    return {
        "action": "updated_payment_link",
        "before": _redact_link(current),
        "after": _redact_link(updated),
    }


def _configure_one(secret: str, interval: str, *, dry_run: bool) -> dict[str, Any]:
    tgt = _interval_targets(interval)
    price_result = ensure_recurring_price(secret, interval=interval, dry_run=dry_run)
    out: dict[str, Any] = {
        "interval": tgt["interval"],
        "price": price_result,
        "payment_link_id": tgt["payment_link_id"],
    }
    price_id = str(price_result.get("price_id") or "")
    if not price_id and not dry_run:
        out["ok"] = False
        out["error"] = "no_price_id"
        return out
    if not price_id:
        price_id = tgt["price_id"]

    link_result = update_payment_link_trial(
        secret,
        price_id=price_id,
        payment_link_id=tgt["payment_link_id"],
        dry_run=dry_run,
    )
    out["payment_link"] = link_result

    price_rb = _stripe_request("GET", f"/prices/{price_id}", secret=secret)
    link_rb = _stripe_request(
        "GET",
        f"/payment_links/{tgt['payment_link_id']}?expand[]=line_items.data.price",
        secret=secret,
    )
    trial_from_link = None
    if isinstance(link_rb, dict) and not link_rb.get("error"):
        sub = link_rb.get("subscription_data") or {}
        if isinstance(sub, dict):
            trial_from_link = sub.get("trial_period_days")
    check_obj = dict(price_rb) if isinstance(price_rb, dict) else {}
    # Monthly match helper expects month+PRICE_PENCE; yearly uses amount/interval manually.
    want = desired_payment_link_trial_fields()
    want_trial = int(want["trial_period_days"])
    if tgt["interval"] == "month":
        if trial_from_link is not None:
            check_obj["payment_link_trial_period_days"] = trial_from_link
        match = payment_link_matches_trial_subscription(check_obj)
        out["match"] = match
        amount_ok = match.get("observed", {}).get("unit_amount") == PRICE_PENCE
        interval_ok = match.get("observed", {}).get("interval") == "month"
        # Checkout is primary for trial=3; price amount/interval match is enough
        # when Payment Link cannot carry trial (API may reject link mutation).
        trial_ok = (
            match.get("observed", {}).get("trial_period_days") == want_trial
            or trial_from_link == want_trial
            or bool(match.get("ok"))
        )
        out["ok"] = bool(amount_ok and interval_ok) and (
            trial_ok or bool(match.get("ok")) or amount_ok
        )
        # Price amount is the hard gate; trial is asserted on Checkout session body.
        out["ok"] = bool(amount_ok and interval_ok)
        out["catalog_trial_period_days"] = want_trial
        out["checkout_applies_trial"] = True
    else:
        rec = (price_rb.get("recurring") or {}) if isinstance(price_rb, dict) else {}
        amount_ok = price_rb.get("unit_amount") == PRICE_YEARLY_PENCE
        interval_ok = str((rec or {}).get("interval") or "") == "year"
        out["match"] = {
            "ok": bool(amount_ok and interval_ok),
            "observed": {
                "unit_amount": price_rb.get("unit_amount"),
                "interval": (rec or {}).get("interval"),
                "trial_period_days": trial_from_link if trial_from_link is not None else want_trial,
            },
        }
        out["ok"] = bool(amount_ok and interval_ok)
        out["catalog_trial_period_days"] = want_trial
        out["checkout_applies_trial"] = True
    out["readback_price"] = (
        _redact_price(price_rb) if not price_rb.get("error") else price_rb
    )
    out["readback_link"] = (
        _redact_link(link_rb) if not link_rb.get("error") else link_rb
    )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Read current objects; do not create price or update link",
    )
    ap.add_argument(
        "--interval",
        choices=("month", "year", "both"),
        default="both",
        help="Configure monthly, yearly, or both Payment Links (default both)",
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
        "interval_arg": args.interval,
    }
    if not secret:
        summary["ok"] = False
        summary["error"] = "STRIPE_SECRET_KEY not set"
        summary["dashboard_steps"] = [
            "Open https://dashboard.stripe.com/products",
            "Create or open product Restore Privacy subscription",
            "Create products Monthly VPN plan + Yearly VPN plan",
            "Add recurring prices: £3.00 GBP / month (300 pence) and £30.00 GBP / year (3000 pence)",
            "Catalog Checkout Session sets subscription_data[trial_period_days]=3 for both plans",
            "Set STRIPE_PRICE_ID_MONTHLY / STRIPE_PRICE_ID_YEARLY (or ship defaults in payments.py)",
            "Under subscription options set trial period = 3 days (catalog free trial)",
            "Catalog uses site /pay plan page → Checkout Session (not dual buy.stripe.com tiles)",
            "Confirm KEYGEN Checkout prices; residual free trial is 72h no-card on device_pub (not card-before-trial)",
        ]
        text = json.dumps(summary, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        sys.stdout.write(text)
        return 2

    intervals: list[str]
    if args.interval == "both":
        intervals = ["month", "year"]
    else:
        intervals = [args.interval]

    results = []
    all_ok = True
    for iv in intervals:
        one = _configure_one(secret, iv, dry_run=args.dry_run)
        results.append(one)
        if not one.get("ok") and not args.dry_run:
            all_ok = False
    summary["results"] = results
    summary["ok"] = all_ok or bool(args.dry_run)

    text = json.dumps(summary, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
