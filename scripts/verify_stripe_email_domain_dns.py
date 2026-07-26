#!/usr/bin/env python3
"""Verify public DNS for Stripe custom email domain + DMARC (+ Checkout pay).

Stripe Customer emails (Dashboard → Settings → Customer emails) requires:
  - Ownership TXT, Mail-From CNAME(s), DKIM CNAME(s) — values from Dashboard only
  - DMARC TXT at _dmarc (shipped policy in payments.DMARC_POLICY_VALUE)
  - Do not use aspf=s; leave PrivateEmail SPF/MX intact

Optional Checkout custom domain (pay.) is also reported via existing helpers.

Usage:
  python scripts/verify_stripe_email_domain_dns.py
  python scripts/verify_stripe_email_domain_dns.py --out report.json
  # After pasting Dashboard rows into a local JSON file (never commit secrets):
  python scripts/verify_stripe_email_domain_dns.py --records stripe_email_domain_dns.local.json

Records JSON shape:
  [{"category":"ownership","type":"TXT","host":"...","value":"..."}, ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from payments import (  # noqa: E402
    DMARC_POLICY_VALUE,
    STRIPE_EMAIL_DOMAIN_DASHBOARD_URL,
    STRIPE_EMAIL_DOMAIN_ZONE,
    dmarc_policy_expected,
    stripe_custom_domain_dns_expected,
    stripe_email_domain_dns_expected,
    verify_stripe_custom_domain_dns,
    verify_stripe_email_domain_dns,
)


def _load_records(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    if not path.is_file():
        raise SystemExit(f"records file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "records" in data:
        data = data["records"]
    if not isinstance(data, list):
        raise SystemExit("records file must be a JSON list of {type,host,value}")
    return list(data)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument(
        "--records",
        type=Path,
        default=None,
        help="Optional Dashboard-issued DNS rows JSON (host/type/value)",
    )
    ap.add_argument(
        "--skip-checkout",
        action="store_true",
        help="Skip pay. Checkout custom-domain DNS check",
    )
    args = ap.parse_args(argv)

    records = _load_records(args.records)
    email = verify_stripe_email_domain_dns(dashboard_records=records or None)
    checkout = None if args.skip_checkout else verify_stripe_custom_domain_dns()

    report: dict[str, Any] = {
        "zone": STRIPE_EMAIL_DOMAIN_ZONE,
        "dashboard_url": STRIPE_EMAIL_DOMAIN_DASHBOARD_URL,
        "dmarc_expected": dmarc_policy_expected(),
        "dmarc_policy_value": DMARC_POLICY_VALUE,
        "email_domain": email,
        "checkout_custom_domain": checkout,
        "structure": stripe_email_domain_dns_expected(dashboard_records=records or None),
        "checkout_structure": stripe_custom_domain_dns_expected(),
        "stripe_dashboard_verified": False,
        "ok": bool(email.get("ok"))
        and (True if args.skip_checkout else bool((checkout or {}).get("ok"))),
    }

    # Honest: never claim Stripe Verified without Dashboard evidence.
    if not email.get("dmarc", {}).get("ok"):
        report["ok"] = False

    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)

    # Exit 0 only when DMARC + SPF (+ checkout unless skipped) look good.
    # Missing Dashboard email rows alone do not fail if not provided.
    dmarc_ok = bool(email.get("dmarc", {}).get("ok"))
    spf_ok = bool(email.get("spf", {}).get("ok"))
    checkout_ok = True if args.skip_checkout else bool((checkout or {}).get("ok"))
    return 0 if (dmarc_ok and spf_ok and checkout_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
