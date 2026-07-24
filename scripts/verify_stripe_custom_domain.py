#!/usr/bin/env python3
"""Verify DNS + optional live Checkout Session host for pay.restoreprivacy.online.

Steps this script cannot do alone (no public Stripe API for Custom domains;
Namecheap credentials not in-repo):
  1. Dashboard → Custom domains → Add pay.restoreprivacy.online (paid feature)
  2. Copy ACME TXT value; publish CNAME pay → hosted-checkout.stripecdn.com
     and TXT _acme-challenge.pay at Namecheap DNS

Usage:
  python scripts/verify_stripe_custom_domain.py
  python scripts/verify_stripe_custom_domain.py --create-session
  STRIPE_SECRET_KEY=sk_live_... python scripts/verify_stripe_custom_domain.py --create-session --out report.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from payments import (  # noqa: E402
    STRIPE_CUSTOM_DOMAIN,
    STRIPE_CUSTOM_DOMAIN_CNAME_TARGET,
    STRIPE_CUSTOM_DOMAINS_DASHBOARD_URL,
    checkout_session_url_host,
    checkout_session_uses_custom_domain,
    create_subscription_checkout_session,
    stripe_custom_domain_dns_expected,
    stripe_secret_key,
    verify_stripe_custom_domain_dns,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--create-session",
        action="store_true",
        help="Create a live subscription Checkout Session and report URL host",
    )
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    expected = stripe_custom_domain_dns_expected()
    dns = verify_stripe_custom_domain_dns()
    report: dict[str, Any] = {
        "domain": STRIPE_CUSTOM_DOMAIN,
        "cname_target": STRIPE_CUSTOM_DOMAIN_CNAME_TARGET,
        "dashboard_url": STRIPE_CUSTOM_DOMAINS_DASHBOARD_URL,
        "expected_dns": expected,
        "dns": dns,
        "session": None,
        "operator_steps_if_not_ok": [],
    }

    if args.create_session:
        secret = stripe_secret_key() or os.environ.get("STRIPE_SECRET_KEY", "").strip()
        if not secret:
            report["session"] = {"ok": False, "error": "STRIPE_SECRET_KEY not set"}
        else:
            try:
                sess = create_subscription_checkout_session(
                    "windows",
                    interval="month",
                    base_url="https://restoreprivacy.online",
                )
                url = str(sess.get("url") or "")
                host = checkout_session_url_host(url)
                report["session"] = {
                    "ok": True,
                    "id": sess.get("id"),
                    "url_host": host,
                    "uses_custom_domain": checkout_session_uses_custom_domain(url),
                    "url_prefix": url[:72] + ("…" if len(url) > 72 else ""),
                    "billing_interval": sess.get("billing_interval"),
                    "mode": sess.get("mode"),
                }
            except Exception as exc:  # noqa: BLE001
                report["session"] = {"ok": False, "error": str(exc)}

    dns_ok = bool(dns.get("ok"))
    sess = report.get("session") or {}
    session_ok = (
        not args.create_session
        or (
            bool(sess.get("ok"))
            and bool(sess.get("uses_custom_domain"))
        )
    )
    report["ok"] = dns_ok and session_ok
    report["brand_trust_ready"] = bool(
        dns_ok and (sess.get("uses_custom_domain") if args.create_session else dns_ok)
    )

    # Tailored residual steps (DNS may already be complete while Stripe TLS lags).
    if report["ok"]:
        report["operator_steps_if_not_ok"] = []
    elif dns_ok and args.create_session and not sess.get("uses_custom_domain"):
        report["operator_steps_if_not_ok"] = [
            f"DNS for {STRIPE_CUSTOM_DOMAIN} is already correct (CNAME+TXT).",
            f"Open {STRIPE_CUSTOM_DOMAINS_DASHBOARD_URL}",
            "If Dashboard says DNS records are being checked for stability "
            "(often ≥3 hours), wait for Stripe email / status Ready — do not "
            "re-edit DNS unless Stripe reports a failure.",
            f"Confirm {STRIPE_CUSTOM_DOMAIN} status is Ready/Active (not Pending/Adding).",
            "Enable «Switch to this domain» / set domain active if not already.",
            "TLS may already work (HTTP 204 on https://pay.restoreprivacy.online) "
            "while Sessions still use checkout.stripe.com until Switch/Active.",
            "Re-run: python3 scripts/verify_stripe_custom_domain.py --create-session",
            f"Expect session url_host={STRIPE_CUSTOM_DOMAIN}",
        ]
    else:
        report["operator_steps_if_not_ok"] = [
            f"Open {STRIPE_CUSTOM_DOMAINS_DASHBOARD_URL}",
            f"Add domain {STRIPE_CUSTOM_DOMAIN} (paid Checkout feature; enable billing if prompted)",
            "Keep «Switch to this domain once added» checked if you want auto-enable",
            "View instructions → copy ACME TXT value",
            "Namecheap → Domain List → manage → Advanced DNS for restoreprivacy.online",
            f"Add CNAME Host={expected['cname']['host']} Value={expected['cname']['value']} TTL=Automatic/5 min",
            f"Add TXT Host={expected['txt']['host']} Value=<from Stripe> TTL=Automatic/5 min",
            "Wait for Stripe status Ready/Active; re-run this script with --create-session",
        ]

    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
