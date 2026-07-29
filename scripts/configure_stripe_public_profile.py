#!/usr/bin/env python3
"""Set Stripe public business name to RASKUL and support email to rus@….

Uses status_page/payments.update_stripe_account_public_profile.
Platform accounts may return 403 for some fields — then finish in Dashboard:

  Settings → Public details → public business name = RASKUL
  Settings → Customer emails / Public details → support = rus@restoreprivacy.online

Stripe receipt PDFs never include the paid /download?token= link; that is only
in the status-host fulfilment SMTP email after checkout.session.completed.

Usage:
  export STRIPE_SECRET_KEY=sk_live_…   # never commit
  python scripts/configure_stripe_public_profile.py
  python scripts/configure_stripe_public_profile.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print guide only; do not call Stripe",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON file for API result summary (no secrets)",
    )
    args = ap.parse_args()

    from payments import (  # noqa: E402
        PUBLIC_BUSINESS_NAME,
        SUPPORT_EMAIL,
        stripe_public_business_guide,
        update_stripe_account_public_profile,
    )

    guide = stripe_public_business_guide()
    print("Wanted public name:", PUBLIC_BUSINESS_NAME)
    print("Wanted support email:", SUPPORT_EMAIL)
    print("Dashboard steps:")
    for s in guide["dashboard"]["steps"]:
        print(" -", s)

    if args.dry_run:
        print("dry-run: no API call")
        if args.out:
            args.out.write_text(
                json.dumps({"dry_run": True, "guide": guide}, indent=2) + "\n",
                encoding="utf-8",
            )
        return 0

    result = update_stripe_account_public_profile()
    print(json.dumps({k: v for k, v in result.items() if k != "guide"}, indent=2))
    if args.out:
        safe = {k: v for k, v in result.items() if k != "guide"}
        safe["guide_urls"] = guide["dashboard"]
        args.out.write_text(json.dumps(safe, indent=2) + "\n", encoding="utf-8")
    if not result.get("ok"):
        print(
            "API did not apply all fields — complete Public details in Dashboard.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
