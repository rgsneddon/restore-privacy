"""Paid download fulfilment: Stripe **subscription** (£2.45/month GBP) + tokens.

Catalog BUY buttons open the **site-hosted plan page** (``/pay``) where the
visitor selects Monthly or Annual (5% off yearly = £27.93). Checkout continues
to a Stripe **subscription** Checkout Session for the chosen plan only (products
**Monthly VPN plan** / **Yearly VPN plan**). Webhook/recovery mints a time-limited
download token and Connect entitlement. See docs/PAID_DOWNLOADS_HOWTO.md.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from downloads import RELEASE_ASSETS, available_downloads

# £2.45 monthly; annual = 5% off 12 × monthly → £27.93 (2793 pence)
PRICE_PENCE = 245
YEARLY_DISCOUNT_PERCENT = 5
PRICE_CURRENCY = "gbp"
PRICE_LABEL = "£2.45"
# Operator: enable Stripe Dashboard Adaptive Pricing when presentment allows;
# unsupported currencies → USD (see local_currency.stripe_presentment_or_usd).


def yearly_amount_pence(
    monthly_pence: int = PRICE_PENCE,
    *,
    discount_percent: int = YEARLY_DISCOUNT_PERCENT,
) -> int:
    """Annual unit amount in pence: 12 × monthly with *discount_percent* off."""
    m = int(monthly_pence)
    d = max(0, min(100, int(discount_percent)))
    return int(round(m * 12 * (100 - d) / 100.0))


PRICE_YEARLY_PENCE = yearly_amount_pence()  # 2793
PRICE_YEARLY_LABEL = f"£{PRICE_YEARLY_PENCE // 100}.{PRICE_YEARLY_PENCE % 100:02d}"
# Pre-discount 12× monthly (for “was / save 5%” display only)
PRICE_YEARLY_FULL_PENCE = PRICE_PENCE * 12  # 2940
PRICE_YEARLY_FULL_LABEL = (
    f"£{PRICE_YEARLY_FULL_PENCE // 100}.{PRICE_YEARLY_FULL_PENCE % 100:02d}"
)

DEFAULT_SUCCESS_PATH = "/download/success"
DEFAULT_CANCEL_PATH = "/download/cancel"
# Site-hosted plan selection (main-site style) before Stripe Checkout
SITE_PAY_PLAN_PATH = "/pay"
TOKEN_TTL_SEC = int(os.environ.get("RPT_DOWNLOAD_TOKEN_TTL_SEC", "3600"))
# Buyer-facing window for the paid fulfilment link (default 1 hour).
DOWNLOAD_LINK_TTL_HOURS = max(1, int(round(TOKEN_TTL_SEC / 3600.0)) or 1)
DOWNLOAD_LINK_VALIDITY_ADVICE = (
    f"Your download link is valid for {DOWNLOAD_LINK_TTL_HOURS} hour"
    f"{'s' if DOWNLOAD_LINK_TTL_HOURS != 1 else ''} from when it was created. "
    "You can download again if the connection drops — the same link works until "
    "it expires (not a one-time use)."
)
DOWNLOAD_DENIED_MSG = (
    "Invalid or expired download link. Links stay valid for "
    f"{DOWNLOAD_LINK_TTL_HOURS} hour"
    f"{'s' if DOWNLOAD_LINK_TTL_HOURS != 1 else ''} and can be retried until they expire."
)
# Customer-facing business / support identity (status-host email + Stripe Dashboard).
# Stripe receipt/invoice PDFs do **not** carry the paid download token — that lives
# only in the status-host fulfilment email and thank-you page.
PUBLIC_BUSINESS_NAME = "RASKUL"
SUPPORT_EMAIL = "rus@restoreprivacy.online"
FULFILMENT_SUPPORT_FOOTER = (
    f"Questions? Contact us at {SUPPORT_EMAIL}."
)
STRIPE_PUBLIC_DETAILS_DASHBOARD_URL = (
    "https://dashboard.stripe.com/settings/public"
)
STRIPE_CUSTOMER_EMAILS_DASHBOARD_URL = (
    "https://dashboard.stripe.com/settings/emails"
)
STRIPE_ACCOUNT_SETTINGS_DASHBOARD_URL = (
    "https://dashboard.stripe.com/settings/account"
)

# --- Stripe Dashboard Branding (logo + colours) — not full site CSS ---
# Map from status_page/public_chrome.py dark theme. Upload logo in Dashboard →
# Settings → Branding (Account API cannot self-update branding on own account).
# Custom domains (pay.example.com) are separate: Settings → Custom domains.
STRIPE_BRAND_PRIMARY_COLOR = "#2694e8"  # --rb-btn
STRIPE_BRAND_SECONDARY_COLOR = "#0a1628"  # --rb-navy
STRIPE_BRAND_ACCENT_CYAN = "#00e5ff"  # --rb-neon-cyan (reference only)
# Stripe Branding constraints: PNG/JPG, each ≥128×128, file <512KB; icon square.
# Exported from assets/brand/primary_transparent_1024.png (see assets/brand/stripe/).
STRIPE_BRAND_LOGO_RELPATH = "assets/brand/stripe/stripe_brand_logo.png"
STRIPE_BRAND_ICON_RELPATH = "assets/brand/stripe/stripe_brand_icon.png"
# Public copies under status host static/ (same bytes as assets/brand/stripe/).
STRIPE_BRAND_LOGO_STATIC_RELPATH = "status_page/static/stripe_brand_logo.png"
STRIPE_BRAND_ICON_STATIC_RELPATH = "status_page/static/stripe_brand_icon.png"
# Last successful Files API upload ids (account-local; re-run upload script to refresh).
STRIPE_BRAND_ICON_FILE_ID = "file_1TwkaXJDavQ2TJW6qwpCbucI"
STRIPE_BRAND_LOGO_FILE_ID = "file_1TwkaZJDavQ2TJW6D0Uw27Fw"
STRIPE_CUSTOM_DOMAIN_RECOMMENDED = "pay.restoreprivacy.online"
# Active custom domain host for Checkout once DNS verifies (same as recommended).
STRIPE_CUSTOM_DOMAIN = STRIPE_CUSTOM_DOMAIN_RECOMMENDED
STRIPE_CUSTOM_DOMAIN_CNAME_TARGET = "hosted-checkout.stripecdn.com"
STRIPE_CUSTOM_DOMAIN_CNAME_NAME = "pay"  # Namecheap Host field for pay.restoreprivacy.online
STRIPE_CUSTOM_DOMAIN_TXT_NAME = "_acme-challenge.pay"
STRIPE_CUSTOM_DOMAIN_TXT_FQDN = "_acme-challenge.pay.restoreprivacy.online"
STRIPE_CUSTOM_DOMAIN_PAID_FEATURE = True
STRIPE_CUSTOM_DOMAIN_MONTHLY_USD = 10  # Stripe Checkout custom domains FAQ (~USD)
STRIPE_BRANDING_DASHBOARD_URL = "https://dashboard.stripe.com/settings/branding"
STRIPE_CUSTOM_DOMAINS_DASHBOARD_URL = (
    "https://dashboard.stripe.com/settings/custom-domains"
)
# --- Custom email domain (Customer emails) + DMARC ---
# Dashboard: https://dashboard.stripe.com/settings/emails — values are account-specific.
STRIPE_EMAIL_DOMAIN_ZONE = "restoreprivacy.online"
STRIPE_EMAIL_DOMAIN_DASHBOARD_URL = "https://dashboard.stripe.com/settings/emails"
STRIPE_EMAIL_DOMAIN_DOCS_URL = (
    "https://docs.stripe.com/get-started/account/email-domain"
)
# Existing mailbox provider (do not replace root SPF with Stripe-only).
STRIPE_EMAIL_EXISTING_SPF = "v=spf1 include:spf.privateemail.com ~all"
STRIPE_EMAIL_EXISTING_MX = ("mx1.privateemail.com", "mx2.privateemail.com")
# Namecheap zone uses registrar-servers.com nameservers.
STRIPE_DNS_NAMECHEAP_NS = (
    "dns1.registrar-servers.com",
    "dns2.registrar-servers.com",
)
# Shipped DMARC for Stripe custom email domain (must start with v=DMARC1, include p=,
# must NOT include aspf=s — Stripe does not support strict SPF alignment).
DMARC_HOST = "_dmarc"
DMARC_FQDN = f"_dmarc.{STRIPE_EMAIL_DOMAIN_ZONE}"
DMARC_POLICY_P = "none"  # monitoring first; later quarantine/reject when ready
DMARC_RUA = "mailto:rus@restoreprivacy.online"
DMARC_POLICY_VALUE = (
    f"v=DMARC1; p={DMARC_POLICY_P}; rua={DMARC_RUA}; pct=100"
)
STRIPE_BRAND_MIN_PX = 128
STRIPE_BRAND_MAX_BYTES = 512 * 1024
# Transparent-background Stripe assets: corners must be clear; canvas mostly clear.
STRIPE_BRAND_CORNER_ALPHA_MAX = 16  # treat as transparent
STRIPE_BRAND_MIN_TRANSPARENT_FRACTION = 0.35  # icon/logo canvas, not solid plate
STRIPE_BRAND_MIN_OPAQUE_PIXELS = 50  # mark must still be visible


def stripe_custom_domain_dns_expected() -> dict[str, Any]:
    """Expected Namecheap / public DNS records for Checkout custom domain.

    Pure helper (no network). TXT **value** is issued only after Dashboard
    → Custom domains → Add ``pay.restoreprivacy.online`` → View instructions.
    """
    return {
        "domain": STRIPE_CUSTOM_DOMAIN,
        "zone": STRIPE_EMAIL_DOMAIN_ZONE,
        "dns_provider": "Namecheap (NS dns1/dns2.registrar-servers.com)",
        "paid_feature": STRIPE_CUSTOM_DOMAIN_PAID_FEATURE,
        "approx_monthly_usd": STRIPE_CUSTOM_DOMAIN_MONTHLY_USD,
        "dashboard_url": STRIPE_CUSTOM_DOMAINS_DASHBOARD_URL,
        "cname": {
            "type": "CNAME",
            "host": STRIPE_CUSTOM_DOMAIN_CNAME_NAME,
            "fqdn": STRIPE_CUSTOM_DOMAIN,
            "value": STRIPE_CUSTOM_DOMAIN_CNAME_TARGET,
            "value_with_trailing_dot": STRIPE_CUSTOM_DOMAIN_CNAME_TARGET + ".",
            "ttl_sec": 300,
        },
        "txt": {
            "type": "TXT",
            "host": STRIPE_CUSTOM_DOMAIN_TXT_NAME,
            "fqdn": STRIPE_CUSTOM_DOMAIN_TXT_FQDN,
            "value": None,  # from Dashboard only
            "value_source": (
                "Stripe Dashboard → Settings → Custom domains → "
                "View instructions for pay.restoreprivacy.online"
            ),
            "ttl_sec": 300,
        },
        "notes": [
            "Path under restoreprivacy.online/checkout is not supported; use pay. subdomain.",
            "Do not proxy the CNAME through Cloudflare orange-cloud if NS ever moves to CF.",
            "Custom domains is a paid Checkout feature (~USD 10/month per Stripe FAQ).",
            "Full website CSS is not injected; URL brand trust only.",
            "Server-side Session create + redirect to session.url is required "
            "(homepage Buy now already does this).",
            "Namecheap Host field: enter only the left label (pay, _acme-challenge.pay) "
            "— do not append .restoreprivacy.online (provider adds the zone).",
        ],
    }


def dmarc_policy_expected() -> dict[str, Any]:
    """Shipped DMARC TXT for Stripe custom email domain (pure, no network).

    Stripe requires a DMARC policy and rejects ``aspf=s`` (strict SPF alignment).
    """
    return {
        "type": "TXT",
        "host": DMARC_HOST,  # Namecheap Host field
        "fqdn": DMARC_FQDN,
        "value": DMARC_POLICY_VALUE,
        "policy": DMARC_POLICY_P,
        "rua": DMARC_RUA,
        "forbids_aspf_strict": True,
        "notes": [
            "Stripe: do not set aspf=s on DMARC.",
            "Start with p=none; raise to quarantine/reject after monitoring.",
            "Coexists with PrivateEmail SPF/MX — do not delete root SPF or MX.",
        ],
    }


def parse_dmarc_policy(txt: str) -> dict[str, Any]:
    """Parse a DMARC TXT value into tags; validate Stripe-safe shape."""
    raw = (txt or "").strip().strip('"').strip()
    tags: dict[str, str] = {}
    for part in re.split(r"\s*;\s*", raw):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, _, v = part.partition("=")
        tags[k.strip().lower()] = v.strip()
    v_ok = tags.get("v", "").upper() == "DMARC1"
    p = tags.get("p", "").lower()
    p_ok = p in ("none", "quarantine", "reject")
    aspf = tags.get("aspf", "").lower()
    aspf_strict = aspf == "s"
    ok = bool(raw) and v_ok and p_ok and not aspf_strict
    return {
        "raw": raw,
        "tags": tags,
        "ok": ok,
        "v_ok": v_ok,
        "p_ok": p_ok,
        "p": p,
        "aspf_strict": aspf_strict,
        "starts_with_v_dmarc1": raw.upper().startswith("V=DMARC1"),
    }


def stripe_email_domain_dns_expected(
    *,
    dashboard_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Expected structure for Stripe Customer emails custom domain DNS.

    Pure helper. Stripe issues ownership TXT, mail-from CNAME(s), and DKIM
    CNAME(s) only in Dashboard → Customer emails → View instructions. Pass
    *dashboard_records* (list of {category,type,host,value}) when the operator
    has pasted those values; otherwise placeholders describe categories only.
    """
    categories = [
        {
            "category": "ownership",
            "type": "TXT",
            "purpose": "Stripe proof-of-ownership before sending from the domain",
            "host": None,  # Dashboard-issued
            "value": None,
            "value_source": (
                "Stripe Dashboard → Settings → Customer emails → "
                f"Add {STRIPE_EMAIL_DOMAIN_ZONE} → View instructions"
            ),
        },
        {
            "category": "mail_from",
            "type": "CNAME",
            "purpose": "Mail-From domain (SPF path for Stripe-sent mail)",
            "host": None,
            "value": None,
            "value_source": "Dashboard View instructions (often a bounce.* host)",
        },
        {
            "category": "dkim",
            "type": "CNAME",
            "purpose": "DKIM public key CNAMEs (usually multiple)",
            "host": None,
            "value": None,
            "value_source": "Dashboard View instructions (*._domainkey…)",
        },
    ]
    dmarc = dmarc_policy_expected()
    return {
        "zone": STRIPE_EMAIL_DOMAIN_ZONE,
        "dns_provider": "Namecheap (NS dns1/dns2.registrar-servers.com)",
        "namecheap_ns": list(STRIPE_DNS_NAMECHEAP_NS),
        "dashboard_url": STRIPE_EMAIL_DOMAIN_DASHBOARD_URL,
        "docs_url": STRIPE_EMAIL_DOMAIN_DOCS_URL,
        "categories": categories,
        "dashboard_records": list(dashboard_records or []),
        "dmarc": dmarc,
        "existing_mail": {
            "spf": STRIPE_EMAIL_EXISTING_SPF,
            "mx": list(STRIPE_EMAIL_EXISTING_MX),
            "note": (
                "Keep PrivateEmail SPF/MX for rus@ mailbox + status-host SMTP. "
                "Stripe email domain uses its own CNAME set (not a second root SPF "
                "unless Dashboard explicitly asks for a TXT SPF change)."
            ),
        },
        "checkout_custom_domain": stripe_custom_domain_dns_expected(),
        "namecheap_rules": [
            "Host field: only the label Stripe shows (e.g. bounce, _dmarc, "
            "xxx._domainkey) — Namecheap appends .restoreprivacy.online.",
            "Never create CNAME name that already has A/AAAA/MX/TXT at the same host.",
            "Do not Cloudflare-proxy (orange cloud) Stripe CNAMEs if NS ever moves to CF.",
            "TTL Automatic or 5 min while verifying.",
            "DMARC Host=_dmarc Value=" + DMARC_POLICY_VALUE,
        ],
        "secrets_not_in_repo": True,
    }


def checkout_session_url_host(url: str) -> str:
    """Return hostname of a Checkout Session ``url`` (empty if unparseable)."""
    u = (url or "").strip()
    if not u:
        return ""
    try:
        return (urllib.parse.urlparse(u).hostname or "").lower()
    except Exception:
        return ""


def checkout_session_uses_custom_domain(url: str) -> bool:
    """True when Session URL is on the shipped custom domain host."""
    host = checkout_session_url_host(url)
    want = STRIPE_CUSTOM_DOMAIN.lower().rstrip(".")
    return host == want or host.endswith("." + want)


def verify_stripe_custom_domain_dns(
    *,
    dig_runner: Callable[[list[str]], str] | None = None,
) -> dict[str, Any]:
    """Live DNS check for pay.restoreprivacy.online CNAME + ACME TXT.

    Uses ``dig +short`` when available; on Windows without dig falls back to
    ``nslookup``. Injected *dig_runner* is used for unit tests. Returns
    ``{ok, cname_ok, txt_ok, observed, expected, mismatches}``.
    """
    import subprocess

    expected = stripe_custom_domain_dns_expected()
    mismatches: list[str] = []
    observed: dict[str, Any] = {
        "cname_answers": [],
        "txt_answers": [],
        "resolvers_tried": [],
    }

    dig_bin = ""
    if dig_runner is None:
        for candidate in ("/usr/bin/dig", "dig"):
            try:
                subprocess.run(
                    [candidate, "-v"],
                    check=False,
                    capture_output=True,
                    timeout=5,
                )
                dig_bin = candidate
                break
            except (OSError, subprocess.TimeoutExpired):
                continue

    def _dig_once(server: str | None, args: list[str]) -> str:
        if dig_runner is not None:
            if server is not None:
                return ""
            return dig_runner(args)
        if not dig_bin:
            return ""
        cmd = [dig_bin, "+short", "+time=5", "+tries=1"]
        if server:
            cmd.append(f"@{server}")
        cmd.extend(args)
        try:
            out = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
            return (out.stdout or "").strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"__error__:{exc}"

    def _dig_any(args: list[str]) -> str:
        """Return first non-empty dig answer across resolvers."""
        servers: list[str | None] = [
            None,
            "8.8.8.8",
            "1.1.1.1",
            "dns1.registrar-servers.com",
        ]
        chunks: list[str] = []
        for server in servers:
            label = server or "system"
            if label not in observed["resolvers_tried"]:
                observed["resolvers_tried"].append(label)
            raw = _dig_once(server, args)
            if raw and not raw.startswith("__error__"):
                return raw
            if raw:
                chunks.append(f"{label}:{raw}")
        return chunks[0] if chunks else ""

    def _nslookup_cname(fqdn: str) -> list[str]:
        try:
            proc = subprocess.run(
                ["nslookup", "-type=CNAME", fqdn],
                check=False,
                capture_output=True,
                text=True,
                timeout=25,
            )
            blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
        except (OSError, subprocess.TimeoutExpired):
            return []
        found: list[str] = []
        for m in re.finditer(
            r"canonical name\s*=\s*(\S+)",
            blob,
            flags=re.IGNORECASE,
        ):
            found.append(m.group(1).strip().rstrip(".").lower())
        return found

    cname_raw = _dig_any(["CNAME", STRIPE_CUSTOM_DOMAIN])
    if not cname_raw:
        cname_raw = _dig_any([STRIPE_CUSTOM_DOMAIN])
    cname_lines = [
        ln.strip().rstrip(".").lower()
        for ln in cname_raw.splitlines()
        if ln.strip() and not ln.startswith("__error__") and "__error__" not in ln
    ]
    if not cname_lines and dig_runner is None:
        observed["resolvers_tried"].append("nslookup")
        cname_lines = _nslookup_cname(STRIPE_CUSTOM_DOMAIN)
    observed["cname_answers"] = cname_lines
    target = STRIPE_CUSTOM_DOMAIN_CNAME_TARGET.lower()
    cname_ok = any(
        target in ln or ln.endswith(target) or ln == target for ln in cname_lines
    )
    if not cname_ok:
        mismatches.append(
            f"cname_missing_or_wrong: want {target!r} got {cname_lines!r}"
        )

    txt_lines: list[str] = []
    if dig_runner is not None or dig_bin:
        txt_raw = _dig_any(["TXT", STRIPE_CUSTOM_DOMAIN_TXT_FQDN])
        for ln in txt_raw.splitlines():
            s = ln.strip().strip('"')
            if s and not s.startswith("__error__") and "__error__" not in s:
                txt_lines.append(s)
    if not txt_lines and dig_runner is None:
        if "nslookup" not in observed["resolvers_tried"]:
            observed["resolvers_tried"].append("nslookup")
        txt_lines = _dns_txt_answers(STRIPE_CUSTOM_DOMAIN_TXT_FQDN)
    observed["txt_answers"] = txt_lines
    txt_ok = any(len(s) >= 16 for s in txt_lines)  # ACME token non-empty
    if not txt_ok:
        mismatches.append(
            f"txt_missing_or_empty: {STRIPE_CUSTOM_DOMAIN_TXT_FQDN} answers={txt_lines!r}"
        )

    return {
        "ok": cname_ok and txt_ok,
        "cname_ok": cname_ok,
        "txt_ok": txt_ok,
        "observed": observed,
        "expected": {
            "cname_fqdn": STRIPE_CUSTOM_DOMAIN,
            "cname_target": STRIPE_CUSTOM_DOMAIN_CNAME_TARGET,
            "txt_fqdn": STRIPE_CUSTOM_DOMAIN_TXT_FQDN,
        },
        "mismatches": mismatches,
        "domain": STRIPE_CUSTOM_DOMAIN,
    }


def _dns_txt_answers(
    fqdn: str,
    *,
    dig_runner: Callable[[list[str]], str] | None = None,
) -> list[str]:
    """Public TXT answers for *fqdn* via dig or Windows nslookup fallback."""
    import subprocess

    if dig_runner is not None:
        raw = dig_runner(["TXT", fqdn])
        out: list[str] = []
        for ln in (raw or "").splitlines():
            s = ln.strip().strip('"')
            if s and not s.startswith("__error__"):
                out.append(s)
        return out

    dig_bin = "dig"
    for candidate in ("/usr/bin/dig", "dig"):
        try:
            subprocess.run(
                [candidate, "-v"],
                check=False,
                capture_output=True,
                timeout=5,
            )
            dig_bin = candidate
            break
        except (OSError, subprocess.TimeoutExpired):
            dig_bin = ""
            continue

    lines: list[str] = []
    if dig_bin:
        for server in (None, "8.8.8.8", "dns1.registrar-servers.com"):
            cmd = [dig_bin, "+short", "+time=5", "+tries=1"]
            if server:
                cmd.append(f"@{server}")
            cmd.extend(["TXT", fqdn])
            try:
                proc = subprocess.run(
                    cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                raw = (proc.stdout or "").strip()
            except (OSError, subprocess.TimeoutExpired):
                raw = ""
            for ln in raw.splitlines():
                s = ln.strip().strip('"')
                if s:
                    lines.append(s)
            if lines:
                return lines

    # Windows: nslookup -type=TXT
    try:
        proc = subprocess.run(
            ["nslookup", "-type=TXT", fqdn],
            check=False,
            capture_output=True,
            text=True,
            timeout=25,
        )
        blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
        # nslookup prints text = "..." possibly multi-line quoted
        for m in re.finditer(
            r'text\s*=\s*"([^"]*)"',
            blob,
            flags=re.IGNORECASE,
        ):
            s = m.group(1).strip()
            if s:
                lines.append(s)
        # Also unquoted: text = v=spf1 ...
        for m in re.finditer(
            r"text\s*=\s*(\S.+)$",
            blob,
            flags=re.IGNORECASE | re.MULTILINE,
        ):
            s = m.group(1).strip().strip('"')
            if s and s not in lines:
                lines.append(s)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return lines


def verify_dmarc_dns(
    *,
    dig_runner: Callable[[list[str]], str] | None = None,
) -> dict[str, Any]:
    """Live public DNS check for ``_dmarc.restoreprivacy.online`` TXT.

    Returns ``{ok, published, parsed, expected_value, observed, mismatches}``.
    Honest fail when missing (operator must publish Namecheap TXT).
    """
    expected = dmarc_policy_expected()
    answers = _dns_txt_answers(DMARC_FQDN, dig_runner=dig_runner)
    mismatches: list[str] = []
    parsed_any: dict[str, Any] | None = None
    ok = False
    for ans in answers:
        parsed = parse_dmarc_policy(ans)
        if parsed["ok"]:
            ok = True
            parsed_any = parsed
            break
        parsed_any = parsed
    if not answers:
        mismatches.append(f"dmarc_missing: no TXT at {DMARC_FQDN}")
    elif not ok:
        mismatches.append(
            f"dmarc_invalid: answers={answers!r} "
            f"(need v=DMARC1; p=none|quarantine|reject; no aspf=s)"
        )
    return {
        "ok": ok,
        "published": bool(answers),
        "fqdn": DMARC_FQDN,
        "host": DMARC_HOST,
        "expected_value": expected["value"],
        "observed": answers,
        "parsed": parsed_any,
        "mismatches": mismatches,
        "namecheap": {
            "type": "TXT",
            "host": DMARC_HOST,
            "value": expected["value"],
        },
    }


def verify_stripe_email_domain_dns(
    *,
    dig_runner: Callable[[list[str]], str] | None = None,
    dashboard_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Public DNS for DMARC + optional Dashboard-issued Stripe email records.

    Without *dashboard_records*, only DMARC (and structural guide) is checked —
    ownership/DKIM/mail-from values are never invented. When records are
    provided (host+type+optional value), each host is looked up.
    """
    expected = stripe_email_domain_dns_expected(
        dashboard_records=dashboard_records
    )
    dmarc = verify_dmarc_dns(dig_runner=dig_runner)
    record_results: list[dict[str, Any]] = []
    for rec in list(dashboard_records or []):
        host = str(rec.get("host") or "").strip().rstrip(".")
        rtype = str(rec.get("type") or "TXT").strip().upper()
        want = (rec.get("value") or "").strip().rstrip(".")
        if not host:
            continue
        fqdn = host if host.endswith("." + STRIPE_EMAIL_DOMAIN_ZONE) or host == STRIPE_EMAIL_DOMAIN_ZONE else f"{host}.{STRIPE_EMAIL_DOMAIN_ZONE}"
        if rtype == "TXT":
            answers = _dns_txt_answers(fqdn, dig_runner=dig_runner)
            published = bool(answers)
            match = (
                (not want and published)
                or any(want.lower() in a.lower() for a in answers)
            )
        else:
            # CNAME: dig CNAME or nslookup
            answers = []
            import subprocess

            if dig_runner is not None:
                raw = dig_runner(["CNAME", fqdn])
                answers = [
                    ln.strip().rstrip(".").lower()
                    for ln in (raw or "").splitlines()
                    if ln.strip()
                ]
            else:
                try:
                    proc = subprocess.run(
                        ["nslookup", "-type=CNAME", fqdn],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=25,
                    )
                    blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
                    for m in re.finditer(
                        r"canonical name\s*=\s*(\S+)",
                        blob,
                        flags=re.IGNORECASE,
                    ):
                        answers.append(m.group(1).strip().rstrip(".").lower())
                except (OSError, subprocess.TimeoutExpired):
                    pass
            published = bool(answers)
            match = (
                (not want and published)
                or any(want.lower().rstrip(".") in a for a in answers)
            )
        record_results.append(
            {
                "host": host,
                "fqdn": fqdn,
                "type": rtype,
                "want_value": want or None,
                "observed": answers,
                "published": published,
                "ok": match,
                "category": rec.get("category"),
            }
        )

    # Root SPF coexistence (must still be PrivateEmail when present)
    spf_answers = _dns_txt_answers(STRIPE_EMAIL_DOMAIN_ZONE, dig_runner=dig_runner)
    spf_ok = any(
        "v=spf1" in a.lower() and "privateemail" in a.lower() for a in spf_answers
    )
    spf_status = {
        "ok": spf_ok,
        "observed": spf_answers,
        "expected_include": "include:spf.privateemail.com",
        "mismatches": (
            []
            if spf_ok
            else ["spf_missing_or_not_privateemail: " + repr(spf_answers)]
        ),
    }

    dash_ok = all(r["ok"] for r in record_results) if record_results else True
    overall = bool(dmarc["ok"] and spf_ok and dash_ok)
    return {
        "ok": overall,
        "dmarc": dmarc,
        "spf": spf_status,
        "dashboard_record_checks": record_results,
        "expected": expected,
        "stripe_verified_claim": False,  # never claim Dashboard Verified without evidence
        "operator_if_not_ok": [
            f"Namecheap → Advanced DNS for {STRIPE_EMAIL_DOMAIN_ZONE}",
            f"Add TXT Host=_dmarc Value={DMARC_POLICY_VALUE}",
            f"Open {STRIPE_EMAIL_DOMAIN_DASHBOARD_URL} → Add domain → View instructions",
            "Paste ownership TXT + mail-from/DKIM CNAMEs (Host = left label only)",
            "Do not invent Stripe token values offline; do not double-append zone",
            "Keep existing SPF: " + STRIPE_EMAIL_EXISTING_SPF,
            "Re-run: python scripts/verify_stripe_email_domain_dns.py",
        ],
    }


def stripe_brand_asset_paths() -> dict[str, Path]:
    """Absolute paths to shipped Stripe-ready icon/logo PNGs."""
    root = Path(__file__).resolve().parents[1]
    return {
        "icon": root / STRIPE_BRAND_ICON_RELPATH,
        "logo": root / STRIPE_BRAND_LOGO_RELPATH,
        "icon_static": root / STRIPE_BRAND_ICON_STATIC_RELPATH,
        "logo_static": root / STRIPE_BRAND_LOGO_STATIC_RELPATH,
    }


def _png_ihdr(raw: bytes) -> tuple[int, int, int, int] | None:
    """Return (width, height, bit_depth, color_type) from PNG bytes or None."""
    import struct

    if len(raw) < 33 or raw[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    # IHDR length at 8, type at 12, data at 16
    if raw[12:16] != b"IHDR":
        return None
    w, h, bit, color = struct.unpack(">IIBB", raw[16:26])
    return int(w), int(h), int(bit), int(color)


def _png_rgba8_pixels(raw: bytes) -> tuple[int, int, bytes] | None:
    """Decode 8-bit RGBA PNG (color type 6) to raw RGBA bytes (stdlib zlib).

    Returns ``(width, height, rgba_bytes)`` or None if not supported.
    """
    import struct
    import zlib

    ihdr = _png_ihdr(raw)
    if not ihdr:
        return None
    w, h, bit, color = ihdr
    if bit != 8 or color != 6 or w < 1 or h < 1 or w * h > 8_000_000:
        return None
    # Collect IDAT
    idat = bytearray()
    pos = 8
    while pos + 8 <= len(raw):
        length = struct.unpack(">I", raw[pos : pos + 4])[0]
        ctype = raw[pos + 4 : pos + 8]
        data = raw[pos + 8 : pos + 8 + length]
        pos = pos + 12 + length  # length+type+data+crc
        if ctype == b"IEND":
            break
        if ctype == b"IDAT":
            idat.extend(data)
    if not idat:
        return None
    try:
        decompressed = zlib.decompress(bytes(idat))
    except zlib.error:
        return None
    stride = w * 4
    expected = h * (1 + stride)
    if len(decompressed) < expected:
        return None
    # Unfilter rows (filters 0-4)
    out = bytearray(h * stride)
    prev = bytearray(stride)

    def paeth(a: int, b: int, c: int) -> int:
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        if pa <= pb and pa <= pc:
            return a
        if pb <= pc:
            return b
        return c

    for y in range(h):
        row_start = y * (1 + stride)
        filt = decompressed[row_start]
        row = bytearray(decompressed[row_start + 1 : row_start + 1 + stride])
        if filt == 0:
            pass
        elif filt == 1:  # Sub
            for i in range(stride):
                left = row[i - 4] if i >= 4 else 0
                row[i] = (row[i] + left) & 0xFF
        elif filt == 2:  # Up
            for i in range(stride):
                row[i] = (row[i] + prev[i]) & 0xFF
        elif filt == 3:  # Average
            for i in range(stride):
                left = row[i - 4] if i >= 4 else 0
                up = prev[i]
                row[i] = (row[i] + ((left + up) // 2)) & 0xFF
        elif filt == 4:  # Paeth
            for i in range(stride):
                left = row[i - 4] if i >= 4 else 0
                up = prev[i]
                up_left = prev[i - 4] if i >= 4 else 0
                row[i] = (row[i] + paeth(left, up, up_left)) & 0xFF
        else:
            return None
        out[y * stride : (y + 1) * stride] = row
        prev = row
    return w, h, bytes(out)


def stripe_brand_asset_constraints_ok(
    path: Path,
    *,
    require_square: bool = False,
    require_transparent: bool = True,
) -> dict[str, Any]:
    """Check Stripe Branding image limits + optional transparent background.

    Size: PNG preferred, ≥128px, <512KB; icon square when *require_square*.
    Transparency (default on): PNG RGBA with **transparent corners** and a
    meaningful transparent canvas fraction (not an opaque plate). JPEG cannot
    satisfy transparency.

    Uses stdlib only. Returns ``{ok, mismatches, observed}``.
    """
    import struct

    p = Path(path)
    mismatches: list[str] = []
    observed: dict[str, Any] = {
        "path": str(p),
        "exists": p.is_file(),
        "size_bytes": None,
        "width": None,
        "height": None,
        "format": None,
        "square": None,
        "color_type": None,
        "has_alpha": None,
        "corner_alphas": None,
        "corners_transparent": None,
        "transparent_fraction": None,
        "opaque_pixel_count": None,
    }
    if not p.is_file():
        return {"ok": False, "mismatches": ["missing_file"], "observed": observed}
    size = p.stat().st_size
    observed["size_bytes"] = size
    if size >= STRIPE_BRAND_MAX_BYTES:
        mismatches.append(f"size_bytes:{size}>={STRIPE_BRAND_MAX_BYTES}")
    if size < 100:
        mismatches.append("size_bytes_too_small")
    raw = p.read_bytes()
    w = h = None
    fmt = None
    color_type = None
    if raw[:8] == b"\x89PNG\r\n\x1a\n" and len(raw) >= 24:
        ihdr = _png_ihdr(raw)
        if ihdr:
            w, h, _bit, color_type = ihdr
        else:
            w, h = struct.unpack(">II", raw[16:24])
        fmt = "png"
        observed["color_type"] = color_type
        # 4=gray+alpha, 6=RGBA, 3=palette may have tRNS
        observed["has_alpha"] = color_type in (4, 6) or (
            color_type == 3 and b"tRNS" in raw
        )
    elif raw[:2] == b"\xff\xd8":
        fmt = "jpg"
        observed["has_alpha"] = False
        i = 2
        while i + 9 < len(raw):
            if raw[i] != 0xFF:
                i += 1
                continue
            marker = raw[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", raw[i + 5 : i + 9])
                break
            if marker == 0xD9:
                break
            if marker in (0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0x01) or marker == 0x00:
                i += 2
                continue
            if i + 4 > len(raw):
                break
            seg_len = struct.unpack(">H", raw[i + 2 : i + 4])[0]
            i += 2 + seg_len
    else:
        mismatches.append("format_not_png_or_jpg")
    observed["width"] = w
    observed["height"] = h
    observed["format"] = fmt
    if w is not None and h is not None:
        observed["square"] = w == h
        if w < STRIPE_BRAND_MIN_PX or h < STRIPE_BRAND_MIN_PX:
            mismatches.append(f"dims:{w}x{h}<{STRIPE_BRAND_MIN_PX}")
        if require_square and w != h:
            mismatches.append(f"not_square:{w}x{h}")
    elif fmt == "jpg" and (w is None or h is None):
        mismatches.append("jpg_dims_unparsed")

    if require_transparent:
        if fmt != "png":
            mismatches.append("transparent_requires_png")
        elif color_type != 6:
            mismatches.append(f"transparent_requires_rgba_color_type_6_got:{color_type}")
        else:
            decoded = _png_rgba8_pixels(raw)
            if not decoded:
                mismatches.append("png_rgba_decode_failed")
            else:
                dw, dh, rgba = decoded
                stride = dw * 4

                def alpha_at(x: int, y: int) -> int:
                    return rgba[y * stride + x * 4 + 3]

                corners = [
                    alpha_at(0, 0),
                    alpha_at(dw - 1, 0),
                    alpha_at(0, dh - 1),
                    alpha_at(dw - 1, dh - 1),
                ]
                observed["corner_alphas"] = corners
                corners_ok = all(a < STRIPE_BRAND_CORNER_ALPHA_MAX for a in corners)
                observed["corners_transparent"] = corners_ok
                if not corners_ok:
                    mismatches.append(f"corners_not_transparent:{corners}")
                # Sample grid for transparent fraction + opaque mark presence
                step_x = max(1, dw // 64)
                step_y = max(1, dh // 64)
                transparent = opaque = samples = 0
                for y in range(0, dh, step_y):
                    for x in range(0, dw, step_x):
                        a = alpha_at(x, y)
                        samples += 1
                        if a < STRIPE_BRAND_CORNER_ALPHA_MAX:
                            transparent += 1
                        if a > 240:
                            opaque += 1
                frac = transparent / samples if samples else 0.0
                observed["transparent_fraction"] = round(frac, 4)
                observed["opaque_pixel_count"] = opaque
                if frac < STRIPE_BRAND_MIN_TRANSPARENT_FRACTION:
                    mismatches.append(
                        f"transparent_fraction:{frac:.3f}<{STRIPE_BRAND_MIN_TRANSPARENT_FRACTION}"
                    )
                if opaque < STRIPE_BRAND_MIN_OPAQUE_PIXELS:
                    mismatches.append(f"mark_too_transparent:opaque_samples={opaque}")

    return {"ok": len(mismatches) == 0, "mismatches": mismatches, "observed": observed}


def stripe_checkout_branding_guide() -> dict[str, Any]:
    """Operator guide: Custom domains + Dashboard branding (pure, no network).

    Custom domains put Checkout on a **subdomain** of your domain (DNS CNAME);
    they do **not** inject website CSS. Branding (logo + primary/secondary
    colours) is the achievable visual match to the public site.

    Stripe-ready assets: ``assets/brand/stripe/stripe_brand_{icon,logo}.png``
    (**transparent-background** PNG RGBA, ≥128px, <512KB; icon square). Files
    API upload ids may be present; attaching them as account branding on the
    **platform** account requires Dashboard (API 403).
    """
    root = Path(__file__).resolve().parents[1]
    paths = stripe_brand_asset_paths()
    logo = paths["logo"]
    icon = paths["icon"]
    icon_check = stripe_brand_asset_constraints_ok(
        icon, require_square=True, require_transparent=True
    )
    logo_check = stripe_brand_asset_constraints_ok(
        logo, require_square=False, require_transparent=True
    )
    return {
        "custom_domains": {
            "what_it_does": (
                "Maps Stripe-hosted Checkout / Payment Links / Customer Portal "
                "onto a subdomain of your domain (e.g. pay.restoreprivacy.online) "
                "via DNS CNAME/TXT verification."
            ),
            "what_it_does_not": (
                "Does not inject the website full CSS; does not serve Checkout as "
                "a path under the status host origin alone; paid Checkout feature."
            ),
            "seamless": {
                "url_brand_trust": True,
                "full_site_css_on_stripe_page": False,
            },
            "recommended_subdomain": STRIPE_CUSTOM_DOMAIN_RECOMMENDED,
            "domain": STRIPE_CUSTOM_DOMAIN,
            "cname_target": STRIPE_CUSTOM_DOMAIN_CNAME_TARGET,
            "txt_host": STRIPE_CUSTOM_DOMAIN_TXT_NAME,
            "txt_fqdn": STRIPE_CUSTOM_DOMAIN_TXT_FQDN,
            "paid_feature": STRIPE_CUSTOM_DOMAIN_PAID_FEATURE,
            "approx_monthly_usd": STRIPE_CUSTOM_DOMAIN_MONTHLY_USD,
            "dns_expected": stripe_custom_domain_dns_expected(),
            "dashboard_url": STRIPE_CUSTOM_DOMAINS_DASHBOARD_URL,
            "docs": "docs/STRIPE_CUSTOM_DOMAINS_AND_BRANDING.md",
            "server_side_redirect_required": True,
        },
        "branding": {
            "dashboard_url": STRIPE_BRANDING_DASHBOARD_URL,
            "primary_color": STRIPE_BRAND_PRIMARY_COLOR,
            "secondary_color": STRIPE_BRAND_SECONDARY_COLOR,
            "accent_reference": STRIPE_BRAND_ACCENT_CYAN,
            "logo_relpath": STRIPE_BRAND_LOGO_RELPATH,
            "icon_relpath": STRIPE_BRAND_ICON_RELPATH,
            "logo_static_relpath": STRIPE_BRAND_LOGO_STATIC_RELPATH,
            "icon_static_relpath": STRIPE_BRAND_ICON_STATIC_RELPATH,
            "logo_exists": logo.is_file(),
            "icon_exists": icon.is_file(),
            "logo_constraints_ok": bool(logo_check.get("ok")),
            "icon_constraints_ok": bool(icon_check.get("ok")),
            "logo_observed": logo_check.get("observed"),
            "icon_observed": icon_check.get("observed"),
            "requires_transparent_background": True,
            "transparent_background": bool(
                (icon_check.get("observed") or {}).get("corners_transparent")
                and (logo_check.get("observed") or {}).get("corners_transparent")
            ),
            "stripe_file_id_logo": STRIPE_BRAND_LOGO_FILE_ID,
            "stripe_file_id_icon": STRIPE_BRAND_ICON_FILE_ID,
            "public_logo_url": "https://restoreprivacy.online/stripe_brand_logo.png",
            "public_icon_url": "https://restoreprivacy.online/stripe_brand_icon.png",
            "source_master": "assets/brand/primary_transparent_1024.png",
            "public_business_name": PUBLIC_BUSINESS_NAME,
            "support_email": SUPPORT_EMAIL,
            "source_theme": "status_page/public_chrome.py (--rb-btn, --rb-navy)",
            "full_site_css_on_checkout": False,
            "account_api_self_update": False,
            "account_api_note": (
                "Files API upload succeeds (business_logo / business_icon). "
                "Attaching branding on the platform account via POST /v1/account "
                "returns 403 (connected accounts only). Finish attach in Dashboard "
                "→ Branding: upload the shipped PNGs or pick the uploaded files; "
                "set primary #2694e8 secondary #0a1628."
            ),
            "upload_script": "scripts/upload_stripe_branding_assets.py",
        },
        "checkout_flow_unchanged": (
            "Homepage Buy now → POST /pay/checkout → subscription Checkout "
            "Session; branding/domains do not change amounts or fulfilment."
        ),
        "customer_emails_vs_fulfilment": (
            "Stripe receipt/invoice emails are payment records (PDF). The paid "
            f"installer download token is only in the status-host fulfilment SMTP "
            f"email (keygen + PPI + 1-hour download link). Set public name to "
            f"{PUBLIC_BUSINESS_NAME} and support to {SUPPORT_EMAIL} in Stripe "
            "so receipt footers match the product brand."
        ),
    }


def stripe_public_business_guide() -> dict[str, Any]:
    """Operator steps: show **RASKUL** and **rus@…** on Stripe customer emails.

    Stripe's native receipt/invoice HTML cannot include a per-purchase download
    token. Branding/support only. Pure helper (no network).
    """
    return {
        "public_business_name": PUBLIC_BUSINESS_NAME,
        "support_email": SUPPORT_EMAIL,
        "what_customers_see": (
            f"Checkout and Stripe receipt/invoice footers should show "
            f"{PUBLIC_BUSINESS_NAME} (not a personal legal name) and "
            f"Questions? Contact us at {SUPPORT_EMAIL}."
        ),
        "dashboard": {
            "public_details": STRIPE_PUBLIC_DETAILS_DASHBOARD_URL,
            "customer_emails": STRIPE_CUSTOMER_EMAILS_DASHBOARD_URL,
            "account_settings": STRIPE_ACCOUNT_SETTINGS_DASHBOARD_URL,
            "steps": [
                (
                    "Settings → Public details (or Business settings → Public info): "
                    f"set **Public business name** / statement descriptor brand to "
                    f"**{PUBLIC_BUSINESS_NAME}**."
                ),
                (
                    "Settings → Customer emails / Public details: set **Support email** "
                    f"(and “Questions? Contact us at…”) to **{SUPPORT_EMAIL}**."
                ),
                (
                    "Settings → Customer emails → custom domain: verify "
                    "restoreprivacy.online so receipts From-address is on-brand "
                    "(see stripe_email_domain_dns_expected / DMARC)."
                ),
                (
                    "Do **not** expect the Stripe receipt PDF to include "
                    "/download?token=… — that link is only in the status-host "
                    "fulfilment email after checkout.session.completed."
                ),
            ],
        },
        "account_api": {
            "endpoint": "POST https://api.stripe.com/v1/accounts",
            "fields": {
                "business_profile[name]": PUBLIC_BUSINESS_NAME,
                "business_profile[support_email]": SUPPORT_EMAIL,
                "settings[dashboard][display_name]": PUBLIC_BUSINESS_NAME,
            },
            "note": (
                "Platform accounts may reject some fields with 403; complete "
                "remaining fields in Dashboard. Script: "
                "scripts/configure_stripe_public_profile.py"
            ),
            "update_helper": "update_stripe_account_public_profile",
        },
        "status_host_fulfilment": {
            "from_display": PUBLIC_BUSINESS_NAME,
            "reply_to": SUPPORT_EMAIL,
            "body_footer": FULFILMENT_SUPPORT_FOOTER,
            "includes_download_token": True,
            "download_ttl_hours": DOWNLOAD_LINK_TTL_HOURS,
        },
    }


def update_stripe_account_public_profile(
    *,
    secret_key: str | None = None,
    http_post: HttpPostFn | None = None,
    business_name: str = PUBLIC_BUSINESS_NAME,
    support_email: str = SUPPORT_EMAIL,
) -> dict[str, Any]:
    """Best-effort POST /v1/account to set public name + support email.

    Returns ``{ok, status, error?, applied?}``. Platform accounts may 403 on
    some settings — then Dashboard steps in :func:`stripe_public_business_guide`
    remain authoritative. Never logs the secret key.
    """
    key = (secret_key if secret_key is not None else stripe_secret_key()).strip()
    if not key:
        return {
            "ok": False,
            "status": 0,
            "error": "STRIPE_SECRET_KEY not configured",
            "applied": False,
            "guide": stripe_public_business_guide()["dashboard"],
        }
    name = (business_name or PUBLIC_BUSINESS_NAME).strip() or PUBLIC_BUSINESS_NAME
    email = (support_email or SUPPORT_EMAIL).strip() or SUPPORT_EMAIL
    body = urllib.parse.urlencode(
        [
            ("business_profile[name]", name),
            ("business_profile[support_email]", email),
            ("settings[dashboard][display_name]", name),
        ]
    ).encode("utf-8")
    post = http_post or _default_http_post
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    # Stripe Account API for the platform account is often GET/POST /v1/account
    status, raw = post(
        "https://api.stripe.com/v1/account",
        headers,
        body,
    )
    if status >= 400:
        # Retry with only business_profile fields (some accounts reject dashboard settings)
        body2 = urllib.parse.urlencode(
            [
                ("business_profile[name]", name),
                ("business_profile[support_email]", email),
            ]
        ).encode("utf-8")
        status2, raw2 = post(
            "https://api.stripe.com/v1/account",
            headers,
            body2,
        )
        if status2 >= 400:
            return {
                "ok": False,
                "status": status2,
                "error": (raw2 or raw or b"")[:400].decode("utf-8", errors="replace"),
                "applied": False,
                "wanted_name": name,
                "wanted_support_email": email,
                "guide": stripe_public_business_guide()["dashboard"],
            }
        status, raw = status2, raw2
    try:
        data = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        data = {}
    bp = data.get("business_profile") if isinstance(data, dict) else {}
    if not isinstance(bp, dict):
        bp = {}
    return {
        "ok": True,
        "status": status,
        "applied": True,
        "observed_name": str(bp.get("name") or ""),
        "observed_support_email": str(bp.get("support_email") or ""),
        "wanted_name": name,
        "wanted_support_email": email,
    }


# Stripe products/prices for catalog subscription checkout (not Payment Links).
# Names: Monthly VPN plan / Yearly VPN plan. Old “download a vpn” product archived.
DEFAULT_STRIPE_PRODUCT_ID_MONTHLY = "prod_UwcybkCi0spmDk"
DEFAULT_STRIPE_PRODUCT_ID_YEARLY = "prod_Uwcy4ghppuxS2C"
DEFAULT_STRIPE_PRICE_ID_MONTHLY = "price_1TwjilJDavQ2TJW6fyxzCIkA"
DEFAULT_STRIPE_PRICE_ID_YEARLY = "price_1TwjimJDavQ2TJW6wEKr4upj"
STRIPE_PRODUCT_NAME_MONTHLY = "Monthly VPN plan"
STRIPE_PRODUCT_NAME_YEARLY = "Yearly VPN plan"


# Shipped Render blueprint mount (render.yaml disk.mountPath + subdir).
# Free instances cannot attach disks; production uses plan starter + this path.
RENDER_PAYMENT_DISK_MOUNT = "/var/data"
RENDER_PAYMENT_DATA_DIR = "/var/data/rpt-payment"
PAYMENT_DB_FILENAME = "paid_downloads.sqlite3"


def _data_dir() -> Path:
    """Durable licence + paid-download grant store directory.

    Prefer ``RPT_PAYMENT_DATA_DIR`` on a **persistent** volume (Render disk /
    host path). Production blueprint sets this to ``/var/data/rpt-payment`` on
    the ``rpt-payment-data`` disk so admin history survives redeploy. Default
    (env unset) is ``status_page/data`` next to this module for local/dev — **not**
    residual-node runtime paths. Residual fleet wipe/rebuild must not delete
    this tree (see :mod:`node.disk_encryption` payment-store protection).
    """
    raw = os.environ.get("RPT_PAYMENT_DATA_DIR", "").strip()
    if raw:
        p = Path(raw)
    else:
        p = Path(__file__).resolve().parent / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def payment_data_dir() -> Path:
    """Public alias: durable admin licence/grants directory."""
    return _data_dir()


def legacy_payment_db_candidates() -> list[Path]:
    """Paths that may hold a pre-disk / ephemeral paid_downloads.sqlite3.

    Used only to **copy into** the durable dir when the durable DB is clearly
    absent/empty so admin history does not silently disappear after attaching
    ``RPT_PAYMENT_DATA_DIR``. Never used to overwrite a non-empty durable file.
    """
    here = Path(__file__).resolve().parent
    out: list[Path] = [
        here / "data" / PAYMENT_DB_FILENAME,
        here / PAYMENT_DB_FILENAME,
        # Common Render layout when rootDir is status_page or monorepo root
        Path("/opt/render/project/src/status_page/data") / PAYMENT_DB_FILENAME,
        Path("/opt/render/project/src/data") / PAYMENT_DB_FILENAME,
        Path("/var/data") / PAYMENT_DB_FILENAME,
    ]
    # Dedup while preserving order
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


# Probe result for migrate safety: never treat lock/error as "empty".
_DB_PROBE_ABSENT = "absent"
_DB_PROBE_EMPTY = "empty"
_DB_PROBE_HAS_HISTORY = "has_history"
_DB_PROBE_UNKNOWN = "unknown"

_migrate_once_lock = __import__("threading").Lock()
_migrate_once_done = False


def payment_db_probe(path: Path) -> dict[str, Any]:
    """Classify payment DB file for safe migrate decisions.

    Returns keys:
      state: absent | empty | has_history | unknown
      grants, entitlements: int counts when known (else 0)
      error: optional short message when unknown

    **Critical:** sqlite lock / OperationalError → ``unknown`` (not empty).
    Only absent / verified-empty may be replaced by legacy copy.
    """
    p = Path(path)
    try:
        if not p.is_file():
            return {
                "state": _DB_PROBE_ABSENT,
                "grants": 0,
                "entitlements": 0,
                "error": "",
            }
        size = p.stat().st_size
        if size == 0:
            return {
                "state": _DB_PROBE_EMPTY,
                "grants": 0,
                "entitlements": 0,
                "error": "",
            }
        if size < 64:
            # Too small for a real SQLite header — treat as empty shell
            return {
                "state": _DB_PROBE_EMPTY,
                "grants": 0,
                "entitlements": 0,
                "error": "",
            }
    except OSError as exc:
        return {
            "state": _DB_PROBE_UNKNOWN,
            "grants": 0,
            "entitlements": 0,
            "error": f"stat:{exc}"[:80],
        }

    try:
        # timeout short; do not hang forever under lock contention
        # as_uri() → file:///… works on Windows and POSIX
        uri = p.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=2.0)
        try:
            # Confirm SQLite header / readable schema
            try:
                conn.execute("SELECT 1").fetchone()
            except sqlite3.Error as exc:
                return {
                    "state": _DB_PROBE_UNKNOWN,
                    "grants": 0,
                    "entitlements": 0,
                    "error": f"open:{exc}"[:80],
                }
            try:
                g = int(conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0])
            except sqlite3.OperationalError as exc:
                # missing table → empty schema, not lock
                msg = str(exc).lower()
                if "no such table" in msg:
                    g = 0
                else:
                    return {
                        "state": _DB_PROBE_UNKNOWN,
                        "grants": 0,
                        "entitlements": 0,
                        "error": f"grants:{exc}"[:80],
                    }
            except sqlite3.Error as exc:
                return {
                    "state": _DB_PROBE_UNKNOWN,
                    "grants": 0,
                    "entitlements": 0,
                    "error": f"grants:{exc}"[:80],
                }
            try:
                e = int(
                    conn.execute("SELECT COUNT(*) FROM connect_entitlements").fetchone()[
                        0
                    ]
                )
            except sqlite3.OperationalError as exc:
                msg = str(exc).lower()
                if "no such table" in msg:
                    e = 0
                else:
                    return {
                        "state": _DB_PROBE_UNKNOWN,
                        "grants": 0,
                        "entitlements": 0,
                        "error": f"ents:{exc}"[:80],
                    }
            except sqlite3.Error as exc:
                return {
                    "state": _DB_PROBE_UNKNOWN,
                    "grants": 0,
                    "entitlements": 0,
                    "error": f"ents:{exc}"[:80],
                }
            g = max(0, g)
            e = max(0, e)
            if g + e > 0:
                return {
                    "state": _DB_PROBE_HAS_HISTORY,
                    "grants": g,
                    "entitlements": e,
                    "error": "",
                }
            return {
                "state": _DB_PROBE_EMPTY,
                "grants": 0,
                "entitlements": 0,
                "error": "",
            }
        finally:
            conn.close()
    except sqlite3.OperationalError as exc:
        # locked database / busy → must NOT migrate over
        return {
            "state": _DB_PROBE_UNKNOWN,
            "grants": 0,
            "entitlements": 0,
            "error": f"op:{exc}"[:80],
        }
    except sqlite3.Error as exc:
        return {
            "state": _DB_PROBE_UNKNOWN,
            "grants": 0,
            "entitlements": 0,
            "error": f"sql:{exc}"[:80],
        }
    except OSError as exc:
        return {
            "state": _DB_PROBE_UNKNOWN,
            "grants": 0,
            "entitlements": 0,
            "error": f"os:{exc}"[:80],
        }


def payment_db_history_counts(path: Path) -> tuple[int, int]:
    """Return (grant_count, entitlement_count).

    On probe failure returns (0, 0) for display only — callers that decide
    migrate must use :func:`payment_db_probe` and refuse ``unknown``.
    """
    probe = payment_db_probe(path)
    if probe["state"] in (_DB_PROBE_HAS_HISTORY, _DB_PROBE_EMPTY):
        return int(probe["grants"]), int(probe["entitlements"])
    return 0, 0


def payment_db_has_history(path: Path) -> bool:
    return payment_db_probe(path)["state"] == _DB_PROBE_HAS_HISTORY


def payment_db_is_safe_migrate_dest(path: Path) -> bool:
    """True only when dest is absent or verified empty (never unknown/locked)."""
    return payment_db_probe(path)["state"] in (_DB_PROBE_ABSENT, _DB_PROBE_EMPTY)


def _acquire_migrate_file_lock(lock_path: Path):
    """Cross-platform exclusive file lock for one-shot migrate (context manager)."""
    import contextlib

    @contextlib.contextmanager
    def _cm():
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(lock_path, "a+b")
        try:
            try:
                if os.name == "nt":
                    import msvcrt

                    fh.seek(0)
                    if fh.read(1) == b"":
                        fh.write(b"0")
                        fh.flush()
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            except OSError as exc:
                # Could not lock — skip migrate this call (do not overwrite)
                yield False, f"lock_failed:{exc}"[:80]
                return
            yield True, ""
        finally:
            try:
                if os.name == "nt":
                    import msvcrt

                    fh.seek(0)
                    try:
                        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                else:
                    import fcntl

                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                fh.close()
            except OSError:
                pass

    return _cm()


def ensure_payment_db_migrated_from_legacy() -> dict[str, Any]:
    """One-shot copy of legacy DB into durable path when dest is clearly empty.

    Safety rules (must not destroy live history):
    - Only when dest probe is ``absent`` or ``empty`` (verified zero rows / no file).
    - Never when dest is ``has_history`` or ``unknown`` (lock/error/busy).
    - Process-level once flag + exclusive file lock around the check+copy.
    - Not invoked from :func:`db_path` on every open — only :func:`init_db`.
    """
    global _migrate_once_done
    import shutil

    dest_dir = payment_data_dir()
    dest = dest_dir / PAYMENT_DB_FILENAME
    status: dict[str, Any] = {
        "dest": str(dest),
        "migrated": False,
        "source": "",
        "reason": "",
    }

    if _migrate_once_done:
        status["reason"] = "already_ran"
        return status

    with _migrate_once_lock:
        if _migrate_once_done:
            status["reason"] = "already_ran"
            return status

        lock_path = dest_dir / ".paid_downloads.migrate.lock"
        with _acquire_migrate_file_lock(lock_path) as (locked, lock_err):
            if not locked:
                status["reason"] = lock_err or "lock_failed"
                # Do not set _migrate_once_done — allow retry next init
                return status

            dest_probe = payment_db_probe(dest)
            status["dest_state"] = dest_probe["state"]
            if dest_probe["state"] == _DB_PROBE_HAS_HISTORY:
                status["reason"] = "dest_has_history"
                _migrate_once_done = True
                return status
            if dest_probe["state"] == _DB_PROBE_UNKNOWN:
                # Locked / unreadable durable file — refuse overwrite
                status["reason"] = f"dest_unknown:{dest_probe.get('error') or ''}"[:120]
                _migrate_once_done = True
                return status
            if dest_probe["state"] not in (_DB_PROBE_ABSENT, _DB_PROBE_EMPTY):
                status["reason"] = f"dest_not_migratable:{dest_probe['state']}"
                _migrate_once_done = True
                return status

            best: Path | None = None
            best_score = 0
            for cand in legacy_payment_db_candidates():
                try:
                    if cand.resolve() == dest.resolve():
                        continue
                except OSError:
                    if str(cand) == str(dest):
                        continue
                if not cand.is_file():
                    continue
                cp = payment_db_probe(cand)
                if cp["state"] != _DB_PROBE_HAS_HISTORY:
                    continue
                score = int(cp["grants"]) + int(cp["entitlements"])
                if score > best_score:
                    best = cand
                    best_score = score

            if best is None or best_score <= 0:
                status["reason"] = "no_legacy_history"
                _migrate_once_done = True
                return status

            # Re-check dest immediately before replace (TOCTOU)
            dest_probe2 = payment_db_probe(dest)
            if dest_probe2["state"] not in (_DB_PROBE_ABSENT, _DB_PROBE_EMPTY):
                status["reason"] = f"dest_changed:{dest_probe2['state']}"
                _migrate_once_done = True
                return status

            try:
                tmp = dest.with_suffix(".sqlite3.migrate-tmp")
                shutil.copy2(best, tmp)
                # Atomic replace only after successful copy
                os.replace(str(tmp), str(dest))
                status["migrated"] = True
                status["source"] = str(best)
                status["reason"] = "copied_legacy_to_durable"
                status["rows"] = best_score
            except OSError as exc:
                status["reason"] = f"copy_failed:{exc}"[:120]
                try:
                    tmp = dest.with_suffix(".sqlite3.migrate-tmp")
                    if tmp.is_file():
                        tmp.unlink(missing_ok=True)  # type: ignore[arg-type]
                except OSError:
                    pass

            _migrate_once_done = True
            return status


def reset_payment_migrate_once_for_tests() -> None:
    """Test helper: allow another migrate attempt in-process."""
    global _migrate_once_done
    _migrate_once_done = False


def payment_store_durability_status() -> dict[str, Any]:
    """Operator-facing: path, env, disk vs ephemeral, row counts."""
    # One-shot migrate only via init_db path (do not re-run on every status read
    # beyond the once-flag; init_db is safe and list helpers call it).
    init_db()
    path = db_path()
    env_raw = os.environ.get("RPT_PAYMENT_DATA_DIR", "").strip()
    path_s = str(path).replace("\\", "/")
    on_render_disk = path_s.startswith(RENDER_PAYMENT_DISK_MOUNT.rstrip("/") + "/") or (
        path_s == RENDER_PAYMENT_DATA_DIR
        or path_s.startswith(RENDER_PAYMENT_DATA_DIR + "/")
    )
    probe = payment_db_probe(path)
    g = int(probe.get("grants") or 0) if probe["state"] != _DB_PROBE_UNKNOWN else 0
    e = (
        int(probe.get("entitlements") or 0)
        if probe["state"] != _DB_PROBE_UNKNOWN
        else 0
    )
    ephemeral_risk = not env_raw or not on_render_disk
    return {
        "db_path": str(path),
        "data_dir": str(payment_data_dir()),
        "env_set": bool(env_raw),
        "env_value": env_raw or "",
        "on_render_disk": on_render_disk,
        "ephemeral_risk": ephemeral_risk,
        "grant_count": g,
        "licence_count": e,
        "db_state": probe["state"],
        "filename": PAYMENT_DB_FILENAME,
        "render_expected_dir": RENDER_PAYMENT_DATA_DIR,
    }


def db_path() -> Path:
    """Path to paid_downloads.sqlite3 (no migrate side-effect on every open)."""
    return _data_dir() / PAYMENT_DB_FILENAME


def payment_store_paths() -> dict[str, str]:
    """Paths for operator docs / wipe exclusion (string form)."""
    d = payment_data_dir()
    return {
        "data_dir": str(d),
        "db": str(db_path()),
        "env_override": "RPT_PAYMENT_DATA_DIR",
        "filename": PAYMENT_DB_FILENAME,
        "render_disk_mount": RENDER_PAYMENT_DISK_MOUNT,
        "render_data_dir": RENDER_PAYMENT_DATA_DIR,
    }


def resolve_payment_data_dir(env: dict[str, str] | None = None) -> Path:
    """Pure-ish path resolution for tests: env dict or process environ.

    Does not create directories when *env* is provided (test-friendly);
    production :func:`payment_data_dir` still mkdir's.
    """
    e = env if env is not None else os.environ
    raw = str(e.get("RPT_PAYMENT_DATA_DIR", "") or "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent / "data"


def wipe_targets_exclude_payment_store(
    targets: list[str] | tuple[str, ...] | None,
    *,
    install_root: str = "/opt/restore-privacy",
) -> list[str]:
    """Drop any wipe candidates that would erase licence/grant admin data."""
    try:
        from node.disk_encryption import is_payment_store_wipe_protected
    except Exception:  # noqa: BLE001

        def is_payment_store_wipe_protected(  # type: ignore[misc]
            path: str, *, install_root: str = install_root
        ) -> bool:
            s = str(path).replace("\\", "/").lower()
            return "paid_downloads.sqlite3" in s or "/status_page/data" in s

    out: list[str] = []
    for t in targets or ():
        s = str(t)
        if is_payment_store_wipe_protected(s, install_root=install_root):
            continue
        out.append(s)
    return out


def payment_store_survives_residual_wipe() -> bool:
    """Honesty helper: product residual wipe plans must not list the payment DB."""
    try:
        from node.disk_encryption import plan_wipe

        plan = plan_wipe(install_root="/opt/restore-privacy", aggressive_secrets=True)
        remaining = wipe_targets_exclude_payment_store(
            plan.get("targets") or [], install_root="/opt/restore-privacy"
        )
        # All planned targets should already exclude payment store; if any
        # payment path remained after exclude, something is wrong.
        protected_hits = [
            t
            for t in (plan.get("targets") or [])
            if t not in remaining
        ]
        # surviving means: no payment path in raw plan (exclude is no-op)
        return len(protected_hits) == 0 and all(
            "paid_downloads" not in str(t).lower()
            and "status_page/data" not in str(t).replace("\\", "/").lower()
            for t in (plan.get("targets") or [])
        )
    except Exception:  # noqa: BLE001
        return False


def _env_or_processor_store(*keys: str) -> str:
    """Read secret/config from process env, then admin-persisted processor_env.json.

    Ensures values saved via ``/admin`` show as **set** after save and after
    process restart when the gitignored store is still present. Host/Render env
    always wins when already set.
    """
    for key in keys:
        val = os.environ.get(key, "").strip()
        if val:
            return val
    try:
        from processor_plugins import load_stored_processor_env

        stored = load_stored_processor_env()
        for key in keys:
            val = (stored.get(key) or "").strip()
            if val:
                return val
    except Exception:
        pass
    return ""


def stripe_secret_key() -> str:
    return _env_or_processor_store("STRIPE_SECRET_KEY")


def stripe_webhook_secret() -> str:
    return _env_or_processor_store("STRIPE_WEBHOOK_SECRET")


def stripe_price_id() -> str:
    """Optional **one-time** Price id for package Checkout only.

    Prefer ``STRIPE_CHECKOUT_PRICE_ID`` / ``STRIPE_ONE_TIME_PRICE_ID``.

    Legacy ``STRIPE_PRICE_ID`` is **ignored by default** for Checkout because operators
    often paste a Payment Link **recurring** price here, which Stripe rejects with
    mode=payment. Set ``STRIPE_ALLOW_LEGACY_PRICE_ID=1`` to use ``STRIPE_PRICE_ID``
    only when that price is known one-time.

    Empty is OK: Checkout uses ``unit_amount`` = £2.45 when no one-time price id.
    """
    for key in ("STRIPE_CHECKOUT_PRICE_ID", "STRIPE_ONE_TIME_PRICE_ID"):
        raw = _env_or_processor_store(key)
        if raw:
            return raw
    if os.environ.get("STRIPE_ALLOW_LEGACY_PRICE_ID", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return _env_or_processor_store("STRIPE_PRICE_ID")
    return ""


def stripe_payment_link_price_id() -> str:
    """Price id on the operator Payment Link (may be recurring) — display only.

    Not used for package Checkout session create (payment mode).
    """
    for key in ("STRIPE_PAYMENT_LINK_PRICE_ID", "RPT_STRIPE_PAYMENT_LINK_PRICE_ID"):
        raw = os.environ.get(key, "").strip()
        if raw:
            return raw
    return DEFAULT_STRIPE_PAYMENT_LINK_PRICE_ID


# Legacy Payment Link URLs (inactive; catalog primary path is site ``/pay``).
# Kept for env override / renew fallbacks when Checkout Session cannot be created.
DEFAULT_STRIPE_PAYMENT_PAGE_URL = (
    "https://buy.stripe.com/cNi7sM4uOeWQ9TBe0q7kc00"
)
DEFAULT_STRIPE_PAYMENT_LINK_ID = "plink_1TvTu6JDavQ2TJW6FeL0dIh9"
# Prefer new Monthly VPN plan price id; env can override.
DEFAULT_STRIPE_PAYMENT_LINK_PRICE_ID = DEFAULT_STRIPE_PRICE_ID_MONTHLY
# Catalog pay product mode (single source of truth with desired_payment_link_trial_fields).
CATALOG_STRIPE_PAYMENT_MODE = "subscription"
DEFAULT_STRIPE_PAYMENT_PAGE_URL_YEARLY = (
    "https://buy.stripe.com/6oUbJ23qK2a43vdbSi7kc01"
)
DEFAULT_STRIPE_PAYMENT_LINK_ID_YEARLY = "plink_1TwbuPJDavQ2TJW6wl7LUUY0"
DEFAULT_STRIPE_PAYMENT_LINK_PRICE_ID_YEARLY = DEFAULT_STRIPE_PRICE_ID_YEARLY
# USD presentment Payment Links (required for true USD charge when Adaptive Pricing
# cannot present the visitor currency). Override with STRIPE_PAYMENT_PAGE_URL_USD /
# STRIPE_PAYMENT_PAGE_URL_YEARLY_USD. When unset, catalog pay buttons for USD
# presentment use host ``/pay/start?...&currency=usd`` which creates a Stripe
# Checkout Session in **USD** (needs STRIPE_SECRET_KEY) or redirects to the USD
# Payment Link when configured.
DEFAULT_STRIPE_PAYMENT_PAGE_URL_USD = ""
DEFAULT_STRIPE_PAYMENT_PAGE_URL_YEARLY_USD = ""

# Customer-facing licence status (OK | EXPIRED) for clients + admin.
LICENCE_STATUS_OK = "OK"
LICENCE_STATUS_EXPIRED = "EXPIRED"
BILLING_INTERVAL_MONTH = "month"
BILLING_INTERVAL_YEAR = "year"

# Seconds-based bounds for tests (calendar month/year, not fixed 30d/365d).
SECONDS_PER_DAY = 86400.0
# One calendar month is ~28–31 days; one year ~365–366.
MIN_MONTH_SECONDS = 27 * SECONDS_PER_DAY
MAX_MONTH_SECONDS = 32 * SECONDS_PER_DAY
MIN_YEAR_SECONDS = 364 * SECONDS_PER_DAY
MAX_YEAR_SECONDS = 367 * SECONDS_PER_DAY


def normalize_billing_interval(interval: str = BILLING_INTERVAL_MONTH) -> str:
    """Return ``month`` or ``year`` from free-form interval labels."""
    iv = (interval or BILLING_INTERVAL_MONTH).strip().lower()
    if iv in ("year", "yearly", "annual", "annually"):
        return BILLING_INTERVAL_YEAR
    return BILLING_INTERVAL_MONTH


def period_end_for_billing_interval(
    start_ts: float,
    interval: str = BILLING_INTERVAL_MONTH,
) -> float:
    """Unix timestamp **one calendar month** or **one calendar year** after *start_ts*.

    Used as the Connect entitlement ``valid_until`` fallback when Stripe
    ``current_period_end`` is not yet available. UTC calendar arithmetic
    (handles month-end and leap-day edge cases).
    """
    iv = normalize_billing_interval(interval)
    start = datetime.fromtimestamp(float(start_ts), tz=timezone.utc)
    if iv == BILLING_INTERVAL_YEAR:
        try:
            end = start.replace(year=start.year + 1)
        except ValueError:
            # 29 Feb → 28 Feb next non-leap year
            end = start.replace(year=start.year + 1, day=28)
    else:
        month = start.month + 1
        year = start.year
        if month > 12:
            month = 1
            year += 1
        day = min(start.day, monthrange(year, month)[1])
        end = start.replace(year=year, month=month, day=day)
    return float(end.timestamp())


def stripe_period_end_from_checkout_object(obj: dict[str, Any] | None) -> float | None:
    """``current_period_end`` from an expanded subscription on a Checkout Session."""
    if not isinstance(obj, dict):
        return None
    sub = obj.get("subscription")
    if isinstance(sub, dict):
        pe = sub.get("current_period_end")
        if pe is not None:
            try:
                return float(pe)
            except (TypeError, ValueError):
                return None
    return None


def valid_until_for_paid_interval(
    interval: str = BILLING_INTERVAL_MONTH,
    *,
    now: float | None = None,
    stripe_period_end: float | None = None,
) -> float:
    """Paid catalog grant period end: Stripe period when future, else month/year fallback.

    Paid monthly/yearly activations must **never** leave ``valid_until=None``
    (unlimited). Admin failsafe keygens remain separate (explicit unlimited).
    """
    t = float(now if now is not None else time.time())
    if stripe_period_end is not None:
        try:
            pe = float(stripe_period_end)
            if pe > t:
                return pe
        except (TypeError, ValueError):
            pass
    return period_end_for_billing_interval(t, interval)


def parse_auto_renew_choice(value: Any) -> bool:
    """Customer auto-renew preference: default **True** unless explicitly off."""
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if s in ("0", "false", "no", "off", "disable", "disabled", "unchecked"):
        return False
    if s in ("", "1", "true", "yes", "on", "enable", "enabled", "checked"):
        return True
    return True


def parse_auto_renew_form_values(values: list[Any] | tuple[Any, ...] | None) -> bool:
    """Parse multi-value form field (hidden ``0`` + checkbox ``1`` pattern).

    Last value wins so an unchecked box (only hidden ``0``) disables renew.
    """
    if not values:
        return True
    return parse_auto_renew_choice(values[-1])


def auto_renew_from_checkout_object(obj: dict[str, Any] | None) -> bool:
    """Customer auto-renew preference from Checkout Session / subscription metadata."""
    if not isinstance(obj, dict):
        return True
    meta = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    if "auto_renew" in meta:
        return parse_auto_renew_choice(meta.get("auto_renew"))
    sub = obj.get("subscription")
    if isinstance(sub, dict):
        sm = sub.get("metadata") if isinstance(sub.get("metadata"), dict) else {}
        if "auto_renew" in sm:
            return parse_auto_renew_choice(sm.get("auto_renew"))
    return True


def apply_subscription_auto_renew_preference(
    subscription_id: str,
    *,
    auto_renew: bool,
    http_post: "HttpPostFn | None" = None,
    secret_key: str | None = None,
) -> dict[str, Any]:
    """Set Stripe Subscription ``cancel_at_period_end`` from customer auto-renew choice.

    *auto_renew* True → cancel_at_period_end=false (keep recurring).
    *auto_renew* False → cancel_at_period_end=true (no further charges after period).
    Best-effort: returns ``{ok, ...}`` without raising on network errors.
    """
    sub = (subscription_id or "").strip()
    if not sub:
        return {"ok": False, "error": "missing_subscription_id"}
    key = (secret_key or "").strip() or stripe_secret_key()
    if not key:
        return {"ok": False, "error": "stripe_unconfigured"}
    cancel_at_end = "false" if auto_renew else "true"
    body = urllib.parse.urlencode(
        {"cancel_at_period_end": cancel_at_end}
    ).encode("utf-8")
    post = http_post or _default_http_post
    try:
        status, raw = post(
            f"https://api.stripe.com/v1/subscriptions/{urllib.parse.quote(sub)}",
            {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"request_failed:{exc!r}"}
    if status >= 400:
        return {
            "ok": False,
            "error": f"http_{status}",
            "body_prefix": (raw or b"")[:200].decode("utf-8", errors="replace"),
        }
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        data = {}
    return {
        "ok": True,
        "subscription_id": sub,
        "cancel_at_period_end": bool(data.get("cancel_at_period_end"))
        if isinstance(data, dict)
        else (not auto_renew),
        "auto_renew": auto_renew,
    }


def stripe_subscription_price_id_monthly() -> str:
    for key in (
        "STRIPE_PRICE_ID_MONTHLY",
        "STRIPE_SUBSCRIPTION_PRICE_ID_MONTHLY",
        "RPT_STRIPE_PRICE_ID_MONTHLY",
    ):
        raw = _env_or_processor_store(key)
        if raw:
            return raw
    return DEFAULT_STRIPE_PRICE_ID_MONTHLY


def stripe_subscription_price_id_yearly() -> str:
    for key in (
        "STRIPE_PRICE_ID_YEARLY",
        "STRIPE_SUBSCRIPTION_PRICE_ID_YEARLY",
        "RPT_STRIPE_PRICE_ID_YEARLY",
    ):
        raw = _env_or_processor_store(key)
        if raw:
            return raw
    return DEFAULT_STRIPE_PRICE_ID_YEARLY


def stripe_subscription_price_id_for_interval(
    interval: str = BILLING_INTERVAL_MONTH,
) -> str:
    """Recurring Price id for Monthly VPN plan or Yearly VPN plan."""
    iv = (interval or BILLING_INTERVAL_MONTH).strip().lower()
    if iv in ("year", "yearly", "annual", "annually"):
        return stripe_subscription_price_id_yearly()
    return stripe_subscription_price_id_monthly()


def stripe_product_name_for_interval(interval: str = BILLING_INTERVAL_MONTH) -> str:
    iv = (interval or BILLING_INTERVAL_MONTH).strip().lower()
    if iv in ("year", "yearly", "annual", "annually"):
        return STRIPE_PRODUCT_NAME_YEARLY
    return STRIPE_PRODUCT_NAME_MONTHLY


def site_pay_plan_path(
    platform: str = "",
    *,
    interval: str = "",
) -> str:
    """Relative path to the site-hosted Select your plan page."""
    plat = (platform or "").strip().lower()
    params: dict[str, str] = {}
    if plat:
        params["platform"] = plat
    iv = (interval or "").strip().lower()
    if iv in ("year", "yearly", "annual", "annually"):
        params["interval"] = BILLING_INTERVAL_YEAR
    elif iv in ("month", "monthly"):
        params["interval"] = BILLING_INTERVAL_MONTH
    if not params:
        return SITE_PAY_PLAN_PATH
    return f"{SITE_PAY_PLAN_PATH}?{urllib.parse.urlencode(params)}"


def site_pay_plan_href(
    platform: str = "",
    *,
    interval: str = "",
    base_url: str | None = None,
) -> str:
    """Absolute or relative URL for the site plan page (primary catalog pay entry)."""
    path = site_pay_plan_path(platform, interval=interval)
    base = (base_url if base_url is not None else public_base_url() or "").rstrip("/")
    if base:
        return f"{base}{path}"
    return path


def _normalize_stripe_pay_url(raw: str) -> str:
    raw = (raw or "").strip().rstrip("/")
    if "donate.stripe.com" in raw.lower():
        raw = re.sub(r"(?i)donate\.stripe\.com", "buy.stripe.com", raw)
    return raw


def stripe_payment_page_url() -> str:
    """Operator Stripe **monthly** subscription Payment Link URL. Public, non-secret.

    Override with ``STRIPE_PAYMENT_PAGE_URL`` or ``RPT_STRIPE_PAYMENT_PAGE_URL``.
    Default is the catalog subscription link (buy.stripe.com), not a donate tip page.
    Legacy ``donate.stripe.com`` hosts are rewritten to ``buy.stripe.com`` so
    public buy buttons always use the product Payment Link family.
    """
    raw = ""
    for key in ("STRIPE_PAYMENT_PAGE_URL", "RPT_STRIPE_PAYMENT_PAGE_URL"):
        raw = os.environ.get(key, "").strip()
        if raw:
            break
    if not raw:
        raw = DEFAULT_STRIPE_PAYMENT_PAGE_URL
    return _normalize_stripe_pay_url(raw)


def stripe_payment_page_url_yearly() -> str:
    """Yearly subscription Payment Link URL (public).

    Override with ``STRIPE_PAYMENT_PAGE_URL_YEARLY`` /
    ``RPT_STRIPE_PAYMENT_PAGE_URL_YEARLY``. Default is the catalog yearly
    Payment Link (distinct buy.stripe.com path from monthly).
    """
    raw = ""
    for key in (
        "STRIPE_PAYMENT_PAGE_URL_YEARLY",
        "RPT_STRIPE_PAYMENT_PAGE_URL_YEARLY",
    ):
        raw = os.environ.get(key, "").strip()
        if raw:
            break
    if not raw:
        raw = DEFAULT_STRIPE_PAYMENT_PAGE_URL_YEARLY
    if not raw:
        # Last-resort fallback only when default empty (should not ship that way)
        raw = stripe_payment_page_url()
    return _normalize_stripe_pay_url(raw)


def stripe_payment_link_id_yearly() -> str:
    """Yearly Payment Link id (plink_…). Override with env when operator rotates."""
    for key in (
        "STRIPE_PAYMENT_LINK_ID_YEARLY",
        "RPT_STRIPE_PAYMENT_LINK_ID_YEARLY",
    ):
        raw = os.environ.get(key, "").strip()
        if raw:
            return raw
    return DEFAULT_STRIPE_PAYMENT_LINK_ID_YEARLY


def stripe_payment_link_price_id_yearly() -> str:
    """Yearly recurring Price id on the yearly Payment Link."""
    for key in (
        "STRIPE_PAYMENT_LINK_PRICE_ID_YEARLY",
        "RPT_STRIPE_PAYMENT_LINK_PRICE_ID_YEARLY",
    ):
        raw = os.environ.get(key, "").strip()
        if raw:
            return raw
    return DEFAULT_STRIPE_PAYMENT_LINK_PRICE_ID_YEARLY


def stripe_payment_page_url_for_interval(interval: str = BILLING_INTERVAL_MONTH) -> str:
    """Payment Link base URL for *interval* (``month`` or ``year``)."""
    iv = (interval or BILLING_INTERVAL_MONTH).strip().lower()
    if iv in ("year", "yearly", "annual", "annually"):
        return stripe_payment_page_url_yearly()
    return stripe_payment_page_url()


def stripe_payment_page_url_usd() -> str:
    """Monthly **USD** Payment Link (public). Empty if operator has not set one.

    Override with ``STRIPE_PAYMENT_PAGE_URL_USD`` / ``RPT_STRIPE_PAYMENT_PAGE_URL_USD``.
    """
    raw = ""
    for key in ("STRIPE_PAYMENT_PAGE_URL_USD", "RPT_STRIPE_PAYMENT_PAGE_URL_USD"):
        raw = os.environ.get(key, "").strip()
        if raw:
            break
    if not raw:
        raw = DEFAULT_STRIPE_PAYMENT_PAGE_URL_USD
    return _normalize_stripe_pay_url(raw) if raw else ""


def stripe_payment_page_url_yearly_usd() -> str:
    """Yearly **USD** Payment Link (public). Falls back to monthly USD URL."""
    raw = ""
    for key in (
        "STRIPE_PAYMENT_PAGE_URL_YEARLY_USD",
        "RPT_STRIPE_PAYMENT_PAGE_URL_YEARLY_USD",
    ):
        raw = os.environ.get(key, "").strip()
        if raw:
            break
    if not raw:
        raw = DEFAULT_STRIPE_PAYMENT_PAGE_URL_YEARLY_USD or stripe_payment_page_url_usd()
    return _normalize_stripe_pay_url(raw) if raw else ""


def stripe_payment_page_url_usd_for_interval(
    interval: str = BILLING_INTERVAL_MONTH,
) -> str:
    """USD Payment Link base for *interval*, or empty string if not configured."""
    iv = (interval or BILLING_INTERVAL_MONTH).strip().lower()
    if iv in ("year", "yearly", "annual", "annually"):
        return stripe_payment_page_url_yearly_usd()
    return stripe_payment_page_url_usd()


def usd_pay_start_path(
    platform: str,
    *,
    interval: str = BILLING_INTERVAL_MONTH,
) -> str:
    """Host path that starts a **USD** Checkout / Payment Link (not the GBP link)."""
    plat = (platform or "").strip().lower() or "windows"
    iv = (interval or BILLING_INTERVAL_MONTH).strip().lower()
    if iv not in ("year", "yearly", "annual", "annually"):
        iv = BILLING_INTERVAL_MONTH
    else:
        iv = BILLING_INTERVAL_YEAR
    q = urllib.parse.urlencode(
        {"platform": plat, "interval": iv, "currency": "usd"}
    )
    return f"/pay/start?{q}"


def encode_client_reference_id(
    platform: str, *, interval: str = BILLING_INTERVAL_MONTH
) -> str:
    """Encode platform + billing interval for Stripe ``client_reference_id``."""
    plat = (platform or "").strip().lower()
    iv = (interval or BILLING_INTERVAL_MONTH).strip().lower()
    if iv in ("year", "yearly", "annual", "annually"):
        iv = BILLING_INTERVAL_YEAR
    else:
        iv = BILLING_INTERVAL_MONTH
    if not plat:
        return iv
    return f"{plat}|{iv}"


def parse_client_reference_id(ref: str) -> tuple[str, str]:
    """Return ``(platform, interval)`` from Stripe client_reference_id."""
    s = (ref or "").strip().lower()
    if not s:
        return "", BILLING_INTERVAL_MONTH
    if "|" in s:
        plat, _, rest = s.partition("|")
        iv = rest.strip()
        if iv in ("year", "yearly", "annual", "annually"):
            return plat.strip(), BILLING_INTERVAL_YEAR
        return plat.strip(), BILLING_INTERVAL_MONTH
    if s.endswith("-year") or s.endswith("_year"):
        for sep in ("-year", "_year"):
            if s.endswith(sep):
                return s[: -len(sep)], BILLING_INTERVAL_YEAR
    return s, BILLING_INTERVAL_MONTH


def stripe_payment_page_href_for_platform(
    platform: str,
    *,
    interval: str = BILLING_INTERVAL_MONTH,
    currency: str = "",
    locale: str = "",
    base_url: str | None = None,
    direct_stripe: bool = False,
) -> str:
    """Primary catalog/renew pay entry: **site-hosted** plan page (``/pay``).

    Visitors select Monthly or Annual on the status host (main-site style), then
    checkout starts a Stripe **subscription** Session for the chosen plan only.

    *interval* pre-selects the plan on the page (``month`` or ``year``).
    *currency* / *locale* are accepted for API compatibility (presentment is
    applied when the Checkout Session is created).

    Pass *direct_stripe*=True for the legacy buy.stripe.com Payment Link path
    (inactive links; not the catalog primary route).
    """
    plat = (platform or "").strip().lower()
    _ = (currency, locale)  # reserved for Checkout Session presentment
    if not direct_stripe:
        return site_pay_plan_href(plat, interval=interval, base_url=base_url)

    # --- Legacy direct Stripe Payment Link (operator override / tests) ---
    try:
        from local_currency import (
            FALLBACK_CURRENCY,
            currency_to_stripe_locale,
            stripe_presentment_or_usd,
        )
    except ImportError:  # pragma: no cover
        from status_page.local_currency import (  # type: ignore
            FALLBACK_CURRENCY,
            currency_to_stripe_locale,
            stripe_presentment_or_usd,
        )

    presentment = ""
    if (currency or "").strip():
        presentment = stripe_presentment_or_usd(currency)

    if presentment == FALLBACK_CURRENCY:
        usd_base = stripe_payment_page_url_usd_for_interval(interval)
        if usd_base:
            params: dict[str, str] = {"locale": "en"}
            if plat:
                params["client_reference_id"] = encode_client_reference_id(
                    plat, interval=interval
                )
            q = urllib.parse.urlencode(params)
            sep = "&" if "?" in usd_base else "?"
            return f"{usd_base}{sep}{q}"
        path = usd_pay_start_path(plat or "windows", interval=interval)
        base = (base_url or public_base_url() or "").rstrip("/")
        if base:
            return f"{base}{path}"
        return path

    base = stripe_payment_page_url_for_interval(interval)
    loc = (locale or "").strip()
    if not loc and presentment:
        loc = currency_to_stripe_locale(presentment)
    params = {}
    if plat:
        params["client_reference_id"] = encode_client_reference_id(
            plat, interval=interval
        )
    if loc:
        params["locale"] = loc
    if not params:
        return base
    q = urllib.parse.urlencode(params)
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{q}"


def stripe_payment_link_id() -> str:
    """Stripe Payment Link id (plink_…). Public identifier — not a secret key.

    Override with ``STRIPE_PAYMENT_LINK_ID`` or ``RPT_STRIPE_PAYMENT_LINK_ID``.
    """
    for key in ("STRIPE_PAYMENT_LINK_ID", "RPT_STRIPE_PAYMENT_LINK_ID"):
        raw = os.environ.get(key, "").strip()
        if raw:
            return raw
    return DEFAULT_STRIPE_PAYMENT_LINK_ID


def is_stripe_catalog_payment_page_url(url: str) -> bool:
    """True when *url* is a Stripe-hosted Payment Link (buy or legacy donate host)."""
    u = (url or "").strip().lower()
    if not u.startswith("https://"):
        return False
    return (
        "buy.stripe.com/" in u
        or "donate.stripe.com/" in u
        or "checkout.stripe.com/" in u
        or "stripe.com/" in u
    )


def stripe_remaining_required_keys() -> list[str]:
    """Env keys still needed for paid-download Checkout + webhook fulfilment.

    The payment page URL alone never clears this list.
    """
    missing: list[str] = []
    if not stripe_secret_key():
        missing.append("STRIPE_SECRET_KEY")
    if not stripe_webhook_secret():
        missing.append("STRIPE_WEBHOOK_SECRET")
    # public_base_url always has a default; still flag empty override if explicitly blank
    base = os.environ.get("RPT_PUBLIC_BASE_URL", "").strip()
    if not base and public_base_url() in ("", "http://127.0.0.1:10000"):
        # Recommend setting production base URL when still on local default
        missing.append("RPT_PUBLIC_BASE_URL")
    return missing


# Production Render status service (Stripe webhook destination host).
DEFAULT_PRODUCTION_PUBLIC_BASE_URL = "https://restoreprivacy.online"
STRIPE_WEBHOOK_PATH = "/webhook/stripe"
# Event operators must select when adding the endpoint in Stripe Dashboard.
# completed → grant download + activate Connect entitlement;
# failure / refund / dispute → revoke Connect entitlement for that session.
STRIPE_WEBHOOK_EVENTS = (
    "checkout.session.completed",
    "checkout.session.async_payment_failed",
    "checkout.session.expired",
    "payment_intent.payment_failed",
    "charge.failed",
    "charge.refunded",
    "charge.dispute.created",
    "invoice.payment_failed",
    "invoice.paid",
    "customer.subscription.updated",
    "customer.subscription.deleted",
)

# Operator checklist copy (Dashboard → Webhooks → select events).
STRIPE_WEBHOOK_EVENT_PURPOSE = {
    "checkout.session.completed": "Paid checkout → mint download + activate Connect entitlement",
    "checkout.session.async_payment_failed": "Async pay fail → revoke Connect",
    "checkout.session.expired": "Checkout expired unpaid → revoke if any",
    "payment_intent.payment_failed": "Card/charge fail → revoke Connect",
    "charge.failed": "Charge fail → revoke Connect",
    "charge.refunded": "Refund → revoke Connect (revoked)",
    "charge.dispute.created": "Dispute → revoke Connect",
    "invoice.payment_failed": "Invoice fail (subscription dunning) → mark failed if no remaining period",
    "invoice.paid": "Invoice paid → renew subscription valid_until / keep active",
    "customer.subscription.updated": "Cancel-at-period-end → keep usable until current_period_end",
    "customer.subscription.deleted": "Subscription ended → revoke Connect (end of period or immediate cancel)",
}


def public_base_url() -> str:
    """Canonical public site URL for success/cancel/webhook (no trailing slash)."""
    return os.environ.get("RPT_PUBLIC_BASE_URL", "http://127.0.0.1:10000").rstrip("/")


def production_public_base_url() -> str:
    """Public base for operator-facing production URLs (custom domain status host)."""
    raw = os.environ.get("RPT_PUBLIC_BASE_URL", "").strip()
    if raw and not raw.startswith("http://127.0.0.1") and not raw.startswith("http://localhost"):
        return raw.rstrip("/")
    return DEFAULT_PRODUCTION_PUBLIC_BASE_URL


def stripe_webhook_endpoint_url(*, production: bool = True) -> str:
    """Full URL Stripe should POST events to (paste into Dashboard → Webhooks).

    When ``production`` is True (default), uses the canonical public origin
    (restoreprivacy.online) so operators always have a copy-paste endpoint.
    """
    base = production_public_base_url() if production else public_base_url()
    return f"{base.rstrip('/')}{STRIPE_WEBHOOK_PATH}"


def production_success_return_url() -> str:
    """Stripe after_completion / Checkout success URL template (Dashboard paste).

    Includes the Checkout session id placeholder Stripe substitutes after payment
    so the buyer lands on thank-you + auto-download on the public origin.

    **Do not** append ``&platform=`` or ``&platform={anything}`` — Stripe only
    expands ``{CHECKOUT_SESSION_ID}``. Platform is carried by Payment Link
    ``client_reference_id`` (BUY tile query) and resolved on the success page.
    """
    base = production_public_base_url().rstrip("/")
    return f"{base}{DEFAULT_SUCCESS_PATH}?session_id={{CHECKOUT_SESSION_ID}}"


def platform_from_stripe_checkout_session(sess: dict[str, Any] | None) -> str:
    """Catalog platform from a Checkout Session object, or empty string.

    Prefers ``client_reference_id`` (Payment Link BUY tile; may be
    ``platform|month`` / ``platform|year``), then ``metadata.platform``.
    Only returns known catalog keys.
    """
    if not isinstance(sess, dict):
        return ""
    ref = str(sess.get("client_reference_id") or "").strip().lower()
    plat, _iv = parse_client_reference_id(ref)
    if platform_filename(plat):
        return plat
    if platform_filename(ref):
        return ref
    meta = sess.get("metadata") if isinstance(sess.get("metadata"), dict) else {}
    meta_plat = str(meta.get("platform") or "").strip().lower()
    if platform_filename(meta_plat):
        return meta_plat
    return ""


def billing_interval_from_stripe_checkout_session(
    sess: dict[str, Any] | None,
) -> str:
    """``month`` or ``year`` from session client_reference_id / metadata."""
    if not isinstance(sess, dict):
        return BILLING_INTERVAL_MONTH
    ref = str(sess.get("client_reference_id") or "").strip().lower()
    _plat, iv = parse_client_reference_id(ref)
    if iv == BILLING_INTERVAL_YEAR:
        return BILLING_INTERVAL_YEAR
    meta = sess.get("metadata") if isinstance(sess.get("metadata"), dict) else {}
    miv = str(meta.get("billing_interval") or meta.get("interval") or "").strip().lower()
    if miv in ("year", "yearly", "annual", "annually"):
        return BILLING_INTERVAL_YEAR
    return BILLING_INTERVAL_MONTH


def resolve_platform_from_checkout_session(
    session_id: str,
    *,
    http_get: HttpGetFn | None = None,
    secret_key: str | None = None,
) -> str:
    """Look up Checkout Session on Stripe and return catalog platform if known."""
    sess = retrieve_checkout_session(
        session_id, http_get=http_get, secret_key=secret_key
    )
    return platform_from_stripe_checkout_session(sess)


def stripe_webhook_operator_guidance() -> dict[str, object]:
    """Non-secret fields for admin/docs: endpoint URL + required events."""
    return {
        "endpoint_url": stripe_webhook_endpoint_url(production=True),
        "path": STRIPE_WEBHOOK_PATH,
        "events": list(STRIPE_WEBHOOK_EVENTS),
        "event_purpose": dict(STRIPE_WEBHOOK_EVENT_PURPOSE),
        "primary_event": STRIPE_WEBHOOK_EVENTS[0],
        "method": "POST",
        "note": (
            "Add this URL in Stripe Dashboard → Developers → Webhooks and select "
            "ALL events listed in STRIPE_WEBHOOK_EVENTS (not only "
            "checkout.session.completed). Copy the signing secret into "
            "STRIPE_WEBHOOK_SECRET (Render env). Subscriptions stay usable until "
            "current_period_end after cancel-at-period-end; Connect is revoked "
            "when the period ends (customer.subscription.deleted) or on refund. "
            "Set Payment Link after_completion redirect to "
            "production_success_return_url(). Never commit the secret. "
            "See status_page/docs/STRIPE_WEBHOOK_CHECKLIST.md."
        ),
        "success_return_url": production_success_return_url(),
        "checklist_doc": "status_page/docs/STRIPE_WEBHOOK_CHECKLIST.md",
    }


def stripe_configured() -> bool:
    return bool(stripe_secret_key())


@dataclass(frozen=True)
class CheckoutRequest:
    platform: str
    filename: str
    success_url: str
    cancel_url: str


def platform_filename(platform: str) -> str | None:
    """Current-catalog installer filename for a platform (always latest ship pin)."""
    from downloads import current_catalog_version

    plat = (platform or "").strip().lower()
    if not plat:
        return None
    for a in available_downloads():
        if a.platform == plat:
            # Guard: filename must embed the live catalog version.
            if current_catalog_version() not in a.filename:
                return None
            return a.filename
    return None


def resolve_paid_grant_filename(
    platform: str, *, metadata_filename: str = ""
) -> str | None:
    """Bind a paid grant to the **current** catalog package for ``platform``.

    Always returns the live :func:`platform_filename` for a known platform so a
    pay-time grant cannot freeze a stale older version string from Stripe
    metadata (e.g. a leftover ``…-0.2.9-…`` name after the catalog moved on).
    Unknown platforms return None. Optional ``metadata_filename`` is ignored
    unless it exactly equals the current catalog name (then still that name).
    """
    plat = (platform or "").strip().lower()
    if not plat:
        return None
    current = platform_filename(plat)
    if not current:
        return None
    meta = (metadata_filename or "").strip()
    # Never accept non-catalog or stale version filenames into grants.
    if meta and meta != current:
        return current
    return current


def grant_delivery_filename(
    *, platform: str = "", stored_filename: str = ""
) -> str | None:
    """Installer name for fulfilling a paid download token.

    Prefer live :func:`platform_filename` for a known platform so a grant row
    that still stores an older pin (e.g. ``…-0.2.9-…``) never streams that
    binary. Falls back to :func:`_safe_catalog_filename` only when the stored
    name is already in the current catalog set.
    """
    plat = (platform or "").strip().lower()
    if plat:
        current = platform_filename(plat)
        if current:
            return current
    return _safe_catalog_filename(stored_filename)


def asset_download_url(filename: str) -> str | None:
    """Canonical GitHub release asset URL (bookkeeping only — not a free public href).

    Paid fulfilment must use :func:`open_release_asset` (local disk or authenticated
    GitHub API) so installers still work when the repo is **private**.
    """
    from downloads import is_current_catalog_filename

    if not is_current_catalog_filename(filename):
        return None
    for a in RELEASE_ASSETS:
        if a.filename == filename:
            return a.url
    return None


def github_auth_token() -> str:
    """Server-side token for private release asset fetch (never expose to browsers)."""
    for key in ("RPT_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return ""


# Dedicated Helsinki paid-installer store (NOT the Iceland residual node).
# Iceland residual monopin remains 82.221.101.241:44044 for VPN only.
DEFAULT_VPS_ASSET_HOST = "135.181.152.10"
DEFAULT_VPS_ASSET_PORT = 8081
DEFAULT_VPS_ASSET_REMOTE_ROOT = "/opt/restore-privacy/paid_assets"
# Preferred public base (HTTPS via sslip.io) when RPT_VPS_ASSET_BASE is unset.
DEFAULT_VPS_ASSET_BASE = "https://135.181.152.10.sslip.io/paid-assets"
# HTTP path prefix on the paid-asset server.
VPS_ASSET_HTTP_PREFIX = "/paid-assets"
# Residual node IP — never use as the default paid-installer CDN.
ICELAND_RESIDUAL_NODE_HOST = "82.221.101.241"


def vps_asset_fetch_token() -> str:
    """Shared secret for status host → Helsinki paid-asset fetch (never browser-facing).

    Reads process env first, then admin-persisted processor store (same keys),
    so a token saved via ``/admin`` works without a Render dashboard API key.
    """
    for key in ("RPT_ASSET_FETCH_TOKEN", "RPT_VPS_ASSET_TOKEN"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    try:
        from processor_plugins import load_stored_processor_env

        stored = load_stored_processor_env()
        for key in ("RPT_ASSET_FETCH_TOKEN", "RPT_VPS_ASSET_TOKEN"):
            val = (stored.get(key) or "").strip()
            if val:
                return val
    except Exception:
        pass
    return ""


def vps_asset_base_url() -> str:
    """Base URL for Helsinki paid installers (no trailing slash).

    Override with ``RPT_VPS_ASSET_BASE`` e.g.
    ``https://135.181.152.10.sslip.io/paid-assets`` or
    ``http://135.181.152.10:8081/paid-assets``.
    Default is the dedicated store host — **not** the Iceland residual node.
    """
    raw = os.environ.get("RPT_VPS_ASSET_BASE", "").strip().rstrip("/")
    if not raw:
        try:
            from processor_plugins import load_stored_processor_env

            raw = (load_stored_processor_env().get("RPT_VPS_ASSET_BASE") or "").strip().rstrip("/")
        except Exception:
            raw = ""
    if raw:
        return raw
    # Prefer full default base (HTTPS) when host/port env not overridden.
    # When only host/port are set, still prefer the public HTTPS sslip default for
    # browser-facing helpers; server-side proxy may override via RPT_VPS_ASSET_BASE.
    host_env = (os.environ.get("RPT_VPS_ASSET_HOST") or "").strip()
    port_env = (os.environ.get("RPT_VPS_ASSET_PORT") or "").strip()
    if not host_env and not port_env:
        return DEFAULT_VPS_ASSET_BASE.rstrip("/")
    # Explicit host without BASE: if it is the default store host, use HTTPS base
    host = host_env or DEFAULT_VPS_ASSET_HOST
    if host in (DEFAULT_VPS_ASSET_HOST, "135.181.152.10") and not port_env:
        return DEFAULT_VPS_ASSET_BASE.rstrip("/")
    port = port_env or str(DEFAULT_VPS_ASSET_PORT)
    # Loopback / private operator override may stay HTTP for server-side fetch only
    return f"http://{host}:{port}{VPS_ASSET_HTTP_PREFIX}"


def vps_asset_url(filename: str, *, version: str | None = None) -> str:
    """Full URL for one catalog installer on the Helsinki paid-asset store."""
    from downloads import RELEASE_VERSION

    ver = (version or RELEASE_VERSION).strip()
    base = vps_asset_base_url()
    return f"{base}/{ver}/{filename}"


def catalog_filenames() -> frozenset[str]:
    """Filenames for the **current** catalog only (never prior tags)."""
    from downloads import is_current_catalog_filename

    return frozenset(
        a.filename for a in RELEASE_ASSETS if is_current_catalog_filename(a.filename)
    )


def asset_search_dirs() -> list[Path]:
    """Directories that may hold release installers for local proxy fulfilment.

    Prefer ``status_page/assets/{VERSION}/`` first — that path is what Render can
    ship when ``rootDir`` is ``status_page`` (repo ``releases/`` is not deployed).
    Also includes the dedicated store on-disk layout when status runs co-located
    with the Helsinki paid-asset host
    (``/opt/restore-privacy/paid_assets/{VERSION}``).
    """
    out: list[Path] = []
    raw = os.environ.get("RPT_ASSET_DIR", "").strip()
    if raw:
        out.append(Path(raw).expanduser())
    from downloads import RELEASE_VERSION  # local import avoids cycles at module load

    status = Path(__file__).resolve().parent
    # Deploy root-friendly (Render rootDir=status_page)
    out.append(status / "assets" / RELEASE_VERSION)
    # Monorepo checkout: releases/{VERSION} (gitignored; local/dev only)
    out.append(status.parent / "releases" / RELEASE_VERSION)
    # Helsinki store layout (when fulfilment is co-located with the asset host)
    remote_root = os.environ.get(
        "RPT_VPS_ASSET_REMOTE_ROOT", DEFAULT_VPS_ASSET_REMOTE_ROOT
    ).strip()
    if remote_root:
        out.append(Path(remote_root) / RELEASE_VERSION)
    return out


def content_type_for_filename(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".apk"):
        return "application/vnd.android.package-archive"
    if lower.endswith(".exe"):
        return "application/vnd.microsoft.portable-executable"
    if lower.endswith(".zip"):
        return "application/zip"
    if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        return "application/gzip"
    return "application/octet-stream"


def _safe_catalog_filename(filename: str) -> str | None:
    """Return basename only when it is a current catalog package; else None.

    Blocks path traversal and non-catalog names before any disk/HTTP open.
    """
    raw = (filename or "").strip()
    if not raw or raw in (".", ".."):
        return None
    # Reject separators and absolute paths (Windows/Unix)
    if any(sep in raw for sep in ("/", "\\", "\x00")):
        return None
    name = Path(raw).name
    if name != raw or name in (".", ".."):
        return None
    if name not in catalog_filenames():
        return None
    return name


def open_release_asset(
    filename: str,
    *,
    urlopen: Callable[..., Any] | None = None,
) -> dict[str, Any] | None:
    """Open installer bytes for a **paid** redeem (proxy/stream, not free public redirect).

    **Call only after a paid grant token has been validated.** This helper does not
    enforce payment itself; HTTP ``/download`` must gate with lookup/consume.

    Resolution order:
      1. Local file under :func:`asset_search_dirs` (operator-staged / VPS on-disk)
      2. Helsinki paid-asset HTTP store (:func:`vps_asset_url` + fetch token)
      3. GitHub Releases API with :func:`github_auth_token` (private repos)
      4. Direct release download URL with the same token (fallback)

    Returns dict with keys: filename, content_type, content_length (int|None),
    body (readable binary file-like or bytes), source (str). Caller must close
    file-like bodies. Returns None if the filename is not a catalog asset or
    no source is available.
    """
    filename = _safe_catalog_filename(filename) or ""
    if not filename:
        return None
    open_url = urlopen or urllib.request.urlopen

    # 1) Local disk (status assets, monorepo releases, VPS paid_assets when co-located)
    for base in asset_search_dirs():
        try:
            base_r = base.resolve()
            path = (base_r / filename).resolve()
            path.relative_to(base_r)
        except (OSError, ValueError):
            continue
        try:
            if path.is_file() and path.stat().st_size > 0:
                fh = path.open("rb")
                return {
                    "filename": filename,
                    "content_type": content_type_for_filename(filename),
                    "content_length": path.stat().st_size,
                    "body": fh,
                    "source": "local",
                }
        except OSError:
            continue

    # 2) Helsinki paid-asset HTTP store (status on Render → dedicated store host).
    # Spool the full object before returning so a VPS mid-stream reset does not
    # leave the browser with a partial body after the grant was opened (paired
    # with consume-after-successful-client-stream in app.py /download).
    vps_token = vps_asset_fetch_token()
    if vps_token:
        try:
            import tempfile

            vps_url = vps_asset_url(filename)
            headers = {
                "User-Agent": "restore-privacy-status-fulfilment",
                "X-RPT-Asset-Token": vps_token,
            }
            req = urllib.request.Request(vps_url, headers=headers)
            resp = open_url(req, timeout=180)
            try:
                # 8 MiB memory spool then disk — fine for catalog installers
                spool = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
                total = 0
                while True:
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    spool.write(chunk)
                    total += len(chunk)
                spool.seek(0)
                hdr_len = resp.headers.get("Content-Length")
                clen = (
                    int(hdr_len)
                    if hdr_len and str(hdr_len).isdigit()
                    else (total if total > 0 else None)
                )
                if total <= 0:
                    try:
                        spool.close()
                    except Exception:  # noqa: BLE001
                        pass
                    raise OSError("empty_vps_asset_body")
                return {
                    "filename": filename,
                    "content_type": content_type_for_filename(filename),
                    "content_length": clen,
                    "body": spool,
                    "source": "vps",
                }
            finally:
                try:
                    resp.close()
                except Exception:  # noqa: BLE001
                    pass
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
            pass

    token = github_auth_token()
    from downloads import GITHUB_OWNER, GITHUB_REPO, RELEASE_TAG

    # 3) GitHub API asset download (private-repo safe with token)
    api_headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "restore-privacy-status-fulfilment",
    }
    if token:
        api_headers["Authorization"] = f"Bearer {token}"
    meta_url = (
        f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
        f"/releases/tags/{RELEASE_TAG}"
    )
    try:
        req = urllib.request.Request(meta_url, headers=api_headers)
        with open_url(req, timeout=60) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
        asset_id = None
        for asset in meta.get("assets") or []:
            if asset.get("name") == filename:
                asset_id = asset.get("id")
                break
        if asset_id is not None:
            dl_headers = {
                "Accept": "application/octet-stream",
                "User-Agent": "restore-privacy-status-fulfilment",
            }
            if token:
                dl_headers["Authorization"] = f"Bearer {token}"
            asset_url = (
                f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
                f"/releases/assets/{asset_id}"
            )
            dl_req = urllib.request.Request(asset_url, headers=dl_headers)
            resp = open_url(dl_req, timeout=120)
            length = resp.headers.get("Content-Length")
            return {
                "filename": filename,
                "content_type": content_type_for_filename(filename),
                "content_length": int(length) if length and length.isdigit() else None,
                "body": resp,
                "source": "github_api",
            }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, ValueError, OSError):
        pass

    # 3) Direct release URL (public repos, or private with token redirect support)
    url = asset_download_url(filename)
    if not url:
        return None
    headers = {"User-Agent": "restore-privacy-status-fulfilment"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = open_url(req, timeout=120)
        length = resp.headers.get("Content-Length")
        return {
            "filename": filename,
            "content_type": content_type_for_filename(filename),
            "content_length": int(length) if length and length.isdigit() else None,
            "body": resp,
            "source": "github_url",
        }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None


def paid_fulfilment_mode() -> str:
    """How /download delivers installers: always server-side proxy (not free GH redirect)."""
    return "proxy"


def _escape_html_text(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def run_as_administrator_instruction(
    *, filename: str = "", platform: str = ""
) -> str:
    """User-facing residual install elevation guidance (honest per platform)."""
    plat = (platform or "").strip().lower()
    name = (filename or "").lower()
    if not plat:
        if name.endswith(".exe"):
            plat = "windows"
        elif name.endswith(".apk"):
            plat = "android"
        elif "macos" in name or name.endswith("-macos.zip"):
            plat = "macos"
        elif "ios" in name or name.endswith("-ios.zip"):
            plat = "ios"
        elif "linux" in name or name.endswith(".tar.gz"):
            plat = "linux"
    if plat == "windows" or name.endswith(".exe"):
        return (
            "Please run the file as administrator: right-click the downloaded installer "
            "→ Run as administrator (approve UAC). Residual full-tunnel VPN needs elevation."
        )
    if plat == "linux" or "linux" in name:
        return (
            "Please run the installer as administrator (e.g. with sudo) so residual "
            "full-tunnel routes can be installed."
        )
    if plat == "macos" or "macos" in name:
        return (
            "Please open the app and approve macOS VPN / administrator prompts when asked "
            "so residual Packet Tunnel can activate."
        )
    if plat == "android" or name.endswith(".apk"):
        return (
            "Please install the APK and grant VPN permission when Android asks "
            "(system VPN consent is required for residual tunnel)."
        )
    if plat == "ios" or "ios" in name:
        return (
            "Please install the app with your device tooling and grant VPN permission "
            "when iOS asks (Packet Tunnel requires user approval)."
        )
    return (
        "Please run the downloaded file as administrator / with elevated privileges "
        "and approve any system VPN prompts so residual protection can install."
    )


def render_post_payment_thankyou_html(
    *,
    download_path: str,
    filename: str,
    platform: str = "",
    session_id: str = "",
    purchase_id: str = "",
    keygen: str = "",
) -> str:
    """Thank-you page body: auto-start download + run-as-administrator copy.

    **Exactly one** auto-start mechanism: a hidden iframe whose ``src`` is the paid
    ``/download?token=…`` path (or a short-lived signed Helsinki host URL minted
    for the same grant). The visible fallback anchor is **manual only** (no
    script click / meta-refresh) and uses the **same** href as the iframe.

    Grant validity (see app ``/download`` + :func:`lookup_download_token`):
      * Time-window only (default **1 hour** via ``RPT_DOWNLOAD_TOKEN_TTL_SEC``).
      * Same token may be fetched **multiple times** while unexpired (retry if
        the connection drops mid-download).
      * ``used_at`` is audit bookkeeping only and does **not** invalidate the link.

    *purchase_id* is the durable product purchase identifier (distinct from the
    time-limited download token). Buyers are **strongly advised** to note it so the
    operator can re-issue a secondary download link after the window expires or
    the installer is lost.

    *keygen* is the subscription unlock code (also emailed). Clients require
    licence accept then keygen entry for Connect.
    """
    link = (download_path or "").strip()
    try:
        from host_delivery import is_signed_helsinki_delivery_url  # type: ignore
    except Exception:  # noqa: BLE001
        try:
            from status_page.host_delivery import (  # type: ignore
                is_signed_helsinki_delivery_url,
            )
        except Exception:  # noqa: BLE001

            def is_signed_helsinki_delivery_url(u: str) -> bool:  # type: ignore
                return False

    if link.startswith("/download"):
        pass  # normal paid grant path
    elif is_signed_helsinki_delivery_url(link):
        pass  # browser→Helsinki (short-lived sig); not free public GitHub
    else:
        raise ValueError(
            "download_path must be a paid /download?token= path "
            "or a signed Helsinki paid-assets delivery URL"
        )
    if "github.com" in link.lower():
        raise ValueError("download_path must not be an external free release URL")
    fname = (filename or "package").strip() or "package"
    fname_esc = _escape_html_text(fname)
    link_esc = _escape_html_text(link)
    admin = _escape_html_text(
        run_as_administrator_instruction(filename=fname, platform=platform)
    )
    plat = (platform or "").strip().lower()
    plat_label = {
        "windows": "Windows",
        "android": "Android",
        "macos": "macOS",
        "ios": "iOS",
        "linux": "Linux",
    }.get(plat, plat or "your package")
    sid = (session_id or "").strip()
    sid_esc = _escape_html_text(sid)
    pid = normalize_purchase_id(purchase_id) or (purchase_id or "").strip().upper()
    pid_esc = _escape_html_text(pid)
    kg = normalize_keygen(keygen) if keygen else ""
    if not kg and sid:
        try:
            ent = get_connect_entitlement(sid)
            if ent:
                kg = normalize_keygen(str(ent.get("keygen") or ""))
        except Exception:  # noqa: BLE001
            kg = ""
    kg_esc = _escape_html_text(kg)
    purchase_block = ""
    if pid:
        purchase_block = f"""
  <div class="msg purchase-id-box" id="purchase-id-box" role="region"
       aria-labelledby="purchase-id-heading">
    <p id="purchase-id-heading"><strong>Your product purchase identifier</strong></p>
    <p class="purchase-id-value"><code id="product-purchase-id">{pid_esc}</code></p>
    <p class="purchase-id-advice" id="purchase-id-advice">
      <strong>STRONG ADVICE — SAVE THIS IDENTIFIER NOW:</strong>
      write it down or store it somewhere safe (password manager, email to yourself).
      It is <strong>not</strong> your download link. If the installer is lost
      after the download window expires, contact the operator with this
      identifier so a <strong>secondary download link</strong> can be recreated.
      Without this identifier, re-fulfilment may not be possible.
    </p>
  </div>"""
    keygen_block = ""
    if kg:
        keygen_block = f"""
  <div class="msg keygen-box" id="keygen-box" role="region"
       aria-labelledby="keygen-heading"
       data-keygen-prominent="1">
    <p id="keygen-heading" class="keygen-heading-label"><strong>{_escape_html_text(KEYGEN_UNLOCK_INSTRUCTION)}</strong></p>
    <p class="keygen-value" id="keygen-value-line">
      <code id="product-keygen" class="product-keygen-display">{kg_esc}</code>
    </p>
    <p class="keygen-copy-row">
      <button type="button" class="keygen-copy-btn" id="keygen-copy-btn"
              data-copy-target="product-keygen"
              aria-label="Copy keygen to clipboard">Copy keygen</button>
      <span class="keygen-copy-status" id="keygen-copy-status" aria-live="polite"></span>
    </p>
    <p class="keygen-advice" id="keygen-advice">
      Install → accept licence terms → enter this keygen in the app to unlock.
      Your subscription is active once payment succeeds (monthly or yearly plan).
      If payment fails later, this keygen becomes useless and Connect locks until
      an active subscription is restored.
    </p>
  </div>
  <script id="thankyou-keygen-copy-script" src="/static/thankyou_keygen_copy.js"></script>"""
    ent_path = f"/api/connect-entitlement-file?session_id={urllib.parse.quote(sid)}" if sid else ""
    ent_path_esc = _escape_html_text(ent_path)
    ent_block = ""
    if sid:
        ent_block = f"""
  <p class="msg entitlement-note" id="connect-entitlement-note">
    <strong>STRONG DISCLAIMER — PAYMENT REQUIRED FOR CONNECT:</strong>
    payment session <code id="connect-session-id">{sid_esc}</code> is active.
    If payment <strong>fails at any time</strong> (refund, dispute, failed charge),
    the ability to <strong>Connect with the Restore Privacy app is cancelled</strong>
    for this purchase/install until you complete a successful payment again.
  </p>
  <p class="msg" id="entitlement-import-hint">
    <strong>Unlock Connect:</strong> accept the licence, then enter your
    <strong>keygen</strong> (above / in your fulfilment email) in Settings.
    Optional auto-import:
    <a class="dl" id="entitlement-file-link" href="{ent_path_esc}"
       download="payment_entitlement.json">payment_entitlement.json</a>
    downloads with your package. Fallback: paste keygen or session
    <code>{sid_esc}</code>. Subscriptions stay usable until the paid period
    ends after cancel.
  </p>
  <iframe id="auto-entitlement-frame" data-src="{ent_path_esc}" src="about:blank"
    style="width:0;height:0;border:0;position:absolute"
    title="Automatic payment entitlement download" aria-hidden="true"></iframe>
  <script id="thankyou-entitlement-script" src="/static/thankyou_entitlement.js"></script>"""
    # Emphasize Windows admin wording for .exe; still show admin phrase for all.
    admin_lead = "Please run the file as administrator."
    btn = f"Download {plat_label} package"
    return f"""
<section id="post-pay-thankyou" class="thankyou" aria-labelledby="thank-you-heading"
         data-page-lifetime="until-tab-close">
  <h1 id="thank-you-heading">Thank you</h1>
  <p class="msg" id="pay-success">Payment confirmed. Your <strong id="paid-platform-label">{_escape_html_text(plat_label)}</strong> installer is ready:</p>
  <p class="pkg" id="paid-package-name"><strong>{fname_esc}</strong></p>
  {keygen_block}
  {purchase_block}
  {ent_block}
  <p class="msg admin-run" id="run-as-admin-instruction">
    <strong>{_escape_html_text(admin_lead)}</strong>
    {admin}
  </p>
  <p class="msg" id="auto-download-note">please wait for your download.. packaging...</p>
  <!-- Installer first (time-limited grant, reusable within TTL). Entitlement file
       is deferred only when session_id is present (script inside ent_block).
       No script click on package. No meta-refresh / no page-close timer. -->
  <iframe id="auto-download-frame" src="{link_esc}" style="width:0;height:0;border:0;position:absolute"
    title="Automatic product download" aria-hidden="true"></iframe>
  <p>
    <a class="dl" id="success-download-link" href="{link_esc}"
       data-manual-download="1" data-platform="{_escape_html_text(plat)}"
       data-filename="{fname_esc}" data-available-until-tab-close="1"
       data-download-ttl-hours="{DOWNLOAD_LINK_TTL_HOURS}">
      { _escape_html_text(btn) } (if it did not start)
    </a>
  </p>
  <p class="msg" id="download-lifetime-note" data-download-ttl-hours="{DOWNLOAD_LINK_TTL_HOURS}">
    <strong>Download link validity:</strong>
    {_escape_html_text(DOWNLOAD_LINK_VALIDITY_ADVICE)}
    This page stays open until you close the tab. Keep it open until your
    download finishes; if the connection drops, use the same link again
    within the window.</p>
  <p><a href="/">Home</a></p>
</section>
"""


# --- SQLite store -----------------------------------------------------------------


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path()), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def generate_purchase_id() -> str:
    """Mint a unique durable product purchase identifier (not a download token).

    Format ``RPT-XXXX-XXXX-XXXX`` (12 hex chars) — stable across re-issued
    download tokens for the same paid purchase.
    """
    raw = secrets.token_hex(6).upper()
    return f"RPT-{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"


def normalize_purchase_id(purchase_id: str | None) -> str:
    """Normalize operator/buyer-entered purchase id for lookup (uppercase, strip)."""
    s = (purchase_id or "").strip().upper().replace(" ", "")
    # Allow missing dashes: RPTA7K2… → leave as entered if already dashed
    if s.startswith("RPT") and "-" not in s and len(s) == 15:
        # RPT + 12 hex
        body = s[3:]
        s = f"RPT-{body[0:4]}-{body[4:8]}-{body[8:12]}"
    return s


# --- Subscription keygen (human-enterable unlock code bound to entitlement) ---

KEYGEN_UNLOCK_INSTRUCTION = (
    "USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY"
)

# Distinct from PPI (RPT-XXXX-…) so buyers do not confuse purchase id with unlock.
KEYGEN_PREFIX = "RPT-KEY-"

# Admin one-month free tester subscription (not a paid customer grant).
TESTER_MONTH_PPI = "TESTER - one month"
TESTER_MONTH_SESSION_PREFIX = "tester_month_"
TESTER_MONTH_REASON = "tester_one_month"


def generate_keygen() -> str:
    """Mint a unique human-enterable subscription keygen.

    Format ``RPT-KEY-XXXX-XXXX-XXXX`` (12 hex chars after prefix). Bound to the
    Stripe-backed connect entitlement; only active while subscription/payment
    remains active on the status host.
    """
    raw = secrets.token_hex(6).upper()
    return f"{KEYGEN_PREFIX}{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"


def normalize_keygen(keygen: str | None) -> str:
    """Normalize customer-entered keygen for lookup (uppercase, strip spaces)."""
    s = (keygen or "").strip().upper().replace(" ", "")
    if not s:
        return ""
    # Accept RPTKEY… without separators → RPT-KEY-XXXX-XXXX-XXXX
    if s.startswith("RPTKEY") and "-" not in s and len(s) == 18:
        body = s[6:]
        s = f"{KEYGEN_PREFIX}{body[0:4]}-{body[4:8]}-{body[8:12]}"
    elif s.startswith("RPT-KEY") and s.count("-") == 1 and len(s) == 19:
        # RPT-KEY + 12 hex no inner dashes
        body = s.replace("RPT-KEY", "").replace("-", "")
        if len(body) == 12:
            s = f"{KEYGEN_PREFIX}{body[0:4]}-{body[4:8]}-{body[8:12]}"
    return s


def _migrate_grants_purchase_id(conn: sqlite3.Connection) -> None:
    cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(grants)").fetchall()}
    if "purchase_id" not in cols:
        conn.execute("ALTER TABLE grants ADD COLUMN purchase_id TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_grants_purchase_id ON grants(purchase_id)"
    )


def init_db() -> None:
    # One-shot legacy → durable copy before opening (empty durable must not hide history)
    ensure_payment_db_migrated_from_legacy()
    conn = _connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS grants (
                token TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                platform TEXT NOT NULL,
                session_id TEXT,
                amount_pence INTEGER NOT NULL,
                currency TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                used_at REAL,
                status TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_grants_session ON grants(session_id);
            CREATE INDEX IF NOT EXISTS idx_grants_created ON grants(created_at);
            CREATE TABLE IF NOT EXISTS connect_entitlements (
                session_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                platform TEXT,
                reason TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_entitlements_status
                ON connect_entitlements(status);
            CREATE TABLE IF NOT EXISTS device_entitlements (
                device_pub_hex TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_device_ent_session
                ON device_entitlements(session_id);
            """
        )
        _ensure_payment_intent_columns(conn)
        _migrate_grants_purchase_id(conn)
        _ensure_keygen_column(conn)
        _ensure_keygen_activated_at_column(conn)
    finally:
        conn.close()


def _ensure_keygen_column(conn: sqlite3.Connection) -> None:
    """Add unique keygen column on connect_entitlements (subscription unlock)."""
    ent_cols = {
        str(r[1]) for r in conn.execute("PRAGMA table_info(connect_entitlements)")
    }
    if "keygen" not in ent_cols:
        conn.execute(
            "ALTER TABLE connect_entitlements ADD COLUMN keygen TEXT"
        )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_entitlements_keygen "
        "ON connect_entitlements(keygen) WHERE keygen IS NOT NULL AND keygen != ''"
    )


def _ensure_keygen_activated_at_column(conn: sqlite3.Connection) -> None:
    """First successful client keygen verify stamp (tester licence list gate)."""
    ent_cols = {
        str(r[1]) for r in conn.execute("PRAGMA table_info(connect_entitlements)")
    }
    if "keygen_activated_at" not in ent_cols:
        conn.execute(
            "ALTER TABLE connect_entitlements ADD COLUMN keygen_activated_at REAL"
        )


def is_tester_month_session(session_id: str | None) -> bool:
    """True for admin one-month tester mint sessions (not paid customers)."""
    return str(session_id or "").startswith(TESTER_MONTH_SESSION_PREFIX)


def is_tester_month_ppi(purchase_id: str | None) -> bool:
    """True when grant/licence PPI is the tester one-month label."""
    raw = (purchase_id or "").strip()
    if raw == TESTER_MONTH_PPI:
        return True
    # Tolerate normalize_purchase_id style (upper, no spaces)
    compact = raw.upper().replace(" ", "")
    return compact == "TESTER-ONEMONTH"


def is_tester_month_grant(row: dict[str, Any] | None) -> bool:
    """True when a grant row belongs to a one-month tester mint."""
    if not isinstance(row, dict):
        return False
    if is_tester_month_session(str(row.get("session_id") or "")):
        return True
    if is_tester_month_ppi(str(row.get("purchase_id") or "")):
        return True
    return False


def _ensure_payment_intent_columns(conn: sqlite3.Connection) -> None:
    """Add payment_intent_id / subscription fields for refunds + period end."""
    ent_cols = {
        str(r[1]) for r in conn.execute("PRAGMA table_info(connect_entitlements)")
    }
    if "payment_intent_id" not in ent_cols:
        conn.execute(
            "ALTER TABLE connect_entitlements ADD COLUMN payment_intent_id TEXT"
        )
    if "valid_until" not in ent_cols:
        conn.execute(
            "ALTER TABLE connect_entitlements ADD COLUMN valid_until REAL"
        )
    if "subscription_id" not in ent_cols:
        conn.execute(
            "ALTER TABLE connect_entitlements ADD COLUMN subscription_id TEXT"
        )
    if "customer_email" not in ent_cols:
        conn.execute(
            "ALTER TABLE connect_entitlements ADD COLUMN customer_email TEXT"
        )
    if "billing_interval" not in ent_cols:
        conn.execute(
            "ALTER TABLE connect_entitlements ADD COLUMN billing_interval TEXT"
        )
    grant_cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(grants)")}
    if "payment_intent_id" not in grant_cols:
        conn.execute("ALTER TABLE grants ADD COLUMN payment_intent_id TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_entitlements_pi "
        "ON connect_entitlements(payment_intent_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_entitlements_sub "
        "ON connect_entitlements(subscription_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_grants_pi ON grants(payment_intent_id)"
    )


# --- Connect entitlement (payment success → may Connect; failure → block) -----

ENTITLEMENT_ACTIVE = "active"
ENTITLEMENT_FAILED = "failed"
ENTITLEMENT_REVOKED = "revoked"


def _mint_unique_keygen(conn: sqlite3.Connection) -> str:
    """Generate a keygen not already stored (retry on rare collision)."""
    for _ in range(12):
        kg = generate_keygen()
        row = conn.execute(
            "SELECT 1 FROM connect_entitlements WHERE keygen = ?", (kg,)
        ).fetchone()
        if row is None:
            return kg
    # Extremely unlikely; fall back to longer entropy
    return f"{KEYGEN_PREFIX}{secrets.token_hex(8).upper()}"


def assign_keygen_for_session(
    session_id: str,
    *,
    keygen: str | None = None,
    now: float | None = None,
) -> str:
    """Ensure *session_id* has a unique keygen; return it (create if missing).

    Idempotent: keeps an existing keygen on re-fulfilment so the customer email
    and client unlock stay stable for the same paid session.
    """
    sid = (session_id or "").strip()
    if not sid:
        return ""
    init_db()
    t = now if now is not None else time.time()
    want = normalize_keygen(keygen) if keygen else ""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT keygen FROM connect_entitlements WHERE session_id = ?",
            (sid,),
        ).fetchone()
        if row is not None:
            existing = normalize_keygen(str(row["keygen"] or ""))
            if existing:
                return existing
            kg = want or _mint_unique_keygen(conn)
            conn.execute(
                "UPDATE connect_entitlements SET keygen = ?, updated_at = ? "
                "WHERE session_id = ?",
                (kg, t, sid),
            )
            return kg
        # Entitlement row may not exist yet — create minimal active + keygen
        kg = want or _mint_unique_keygen(conn)
        conn.execute(
            """
            INSERT INTO connect_entitlements(
                session_id, status, platform, reason, created_at, updated_at,
                keygen
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                sid,
                ENTITLEMENT_ACTIVE,
                "",
                "payment_succeeded",
                t,
                t,
                kg,
            ),
        )
        return kg
    finally:
        conn.close()


def activate_connect_entitlement(
    session_id: str,
    *,
    platform: str = "",
    payment_intent_id: str = "",
    subscription_id: str = "",
    valid_until: float | None = None,
    keygen: str | None = None,
    customer_email: str = "",
    billing_interval: str = "",
    now: float | None = None,
) -> str:
    """Mark Checkout session as paid/active for Connect entitlement.

    *valid_until* is a unix timestamp after which Connect is no longer allowed
    (subscription period end). ``None`` means no time limit — used only for
    **admin failsafe** / legacy paths; paid monthly/yearly catalog grants always
    pass a finite period from :func:`process_checkout_completed_event`.

    Returns the bound **keygen** (minted once per session if not already set).
    """
    sid = (session_id or "").strip()
    if not sid:
        return ""
    init_db()
    t = now if now is not None else time.time()
    plat = (platform or "").strip().lower()
    pi = (payment_intent_id or "").strip()
    sub = (subscription_id or "").strip()
    email = (customer_email or "").strip().lower()
    iv = (billing_interval or "").strip().lower()
    if iv in ("year", "yearly", "annual", "annually"):
        iv = BILLING_INTERVAL_YEAR
    elif iv:
        iv = BILLING_INTERVAL_MONTH
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT platform, payment_intent_id, subscription_id, valid_until, keygen, "
            "customer_email, billing_interval "
            "FROM connect_entitlements WHERE session_id = ?",
            (sid,),
        )
        row = cur.fetchone()
        keep_keygen = ""
        if row:
            keep_plat = plat or (row["platform"] or "")
            keep_pi = pi or (row["payment_intent_id"] or "")
            keep_sub = sub or (row["subscription_id"] or "")
            if valid_until is None:
                keep_vu = row["valid_until"]
            else:
                keep_vu = float(valid_until)
            existing_kg = ""
            try:
                existing_kg = normalize_keygen(str(row["keygen"] or ""))
            except (KeyError, IndexError, TypeError):
                existing_kg = ""
            keep_keygen = (
                normalize_keygen(keygen)
                if keygen
                else existing_kg
            ) or existing_kg or _mint_unique_keygen(conn)
            try:
                keep_email = email or str(row["customer_email"] or "")
            except (KeyError, IndexError, TypeError):
                keep_email = email
            try:
                keep_iv = iv or str(row["billing_interval"] or "") or BILLING_INTERVAL_MONTH
            except (KeyError, IndexError, TypeError):
                keep_iv = iv or BILLING_INTERVAL_MONTH
            conn.execute(
                """
                UPDATE connect_entitlements
                SET status = ?, platform = ?, reason = ?, updated_at = ?,
                    payment_intent_id = ?, subscription_id = ?, valid_until = ?,
                    keygen = ?, customer_email = ?, billing_interval = ?
                WHERE session_id = ?
                """,
                (
                    ENTITLEMENT_ACTIVE,
                    keep_plat,
                    "payment_succeeded",
                    t,
                    keep_pi,
                    keep_sub,
                    keep_vu,
                    keep_keygen,
                    keep_email,
                    keep_iv,
                    sid,
                ),
            )
        else:
            keep_keygen = normalize_keygen(keygen) if keygen else _mint_unique_keygen(conn)
            conn.execute(
                """
                INSERT INTO connect_entitlements(
                    session_id, status, platform, reason, created_at, updated_at,
                    payment_intent_id, subscription_id, valid_until, keygen,
                    customer_email, billing_interval
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    sid,
                    ENTITLEMENT_ACTIVE,
                    plat,
                    "payment_succeeded",
                    t,
                    t,
                    pi,
                    sub,
                    float(valid_until) if valid_until is not None else None,
                    keep_keygen,
                    email,
                    iv or BILLING_INTERVAL_MONTH,
                ),
            )
        if pi:
            conn.execute(
                "UPDATE grants SET payment_intent_id = ? WHERE session_id = ?",
                (pi, sid),
            )
        return keep_keygen
    finally:
        conn.close()


def revoke_connect_entitlement(
    session_id: str,
    *,
    reason: str = "payment_failed",
    status: str = ENTITLEMENT_FAILED,
    now: float | None = None,
) -> bool:
    """Revoke Connect for a payment session (failed charge, refund, etc.)."""
    sid = (session_id or "").strip()
    if not sid:
        return False
    init_db()
    t = now if now is not None else time.time()
    st = (status or ENTITLEMENT_FAILED).strip().lower()
    if st not in (ENTITLEMENT_FAILED, ENTITLEMENT_REVOKED):
        st = ENTITLEMENT_FAILED
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT session_id FROM connect_entitlements WHERE session_id = ?",
            (sid,),
        )
        row = cur.fetchone()
        if row:
            conn.execute(
                """
                UPDATE connect_entitlements
                SET status = ?, reason = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (st, str(reason or st)[:200], t, sid),
            )
        else:
            conn.execute(
                """
                INSERT INTO connect_entitlements(
                    session_id, status, platform, reason, created_at, updated_at
                ) VALUES (?,?,?,?,?,?)
                """,
                (sid, st, "", str(reason or st)[:200], t, t),
            )
        # Also mark related download grants revoked so tokens cannot re-serve
        conn.execute(
            "UPDATE grants SET status = 'revoked' WHERE session_id = ? AND status = 'granted'",
            (sid,),
        )
        conn.execute(
            "DELETE FROM device_entitlements WHERE session_id = ?",
            (sid,),
        )
    finally:
        conn.close()
    return True


def _entitlement_connect_allowed(
    status: str,
    valid_until: float | None,
    *,
    now: float | None = None,
) -> bool:
    """Active only when status is active and period (if any) has not ended."""
    if (status or "").strip().lower() != ENTITLEMENT_ACTIVE:
        return False
    if valid_until is None:
        return True
    t = now if now is not None else time.time()
    try:
        return float(valid_until) > float(t)
    except (TypeError, ValueError):
        return False


def licence_status_from_entitlement(
    ent: dict[str, Any] | None,
    *,
    now: float | None = None,
) -> str:
    """Normalize grant/entitlement row to customer-facing **OK** or **EXPIRED**.

    OK = Connect allowed (active subscription/payment, period not ended).
    EXPIRED = failed, revoked, period ended, unknown, or missing entitlement.
    """
    if not isinstance(ent, dict) or not ent:
        return LICENCE_STATUS_EXPIRED
    t = now if now is not None else time.time()
    if ent.get("connect_allowed") is True:
        return LICENCE_STATUS_OK
    status = str(ent.get("status") or "").strip().lower()
    vu = ent.get("valid_until")
    if status == ENTITLEMENT_ACTIVE and _entitlement_connect_allowed(
        status, float(vu) if vu is not None else None, now=t
    ):
        return LICENCE_STATUS_OK
    return LICENCE_STATUS_EXPIRED


def get_connect_entitlement(
    session_id: str, *, now: float | None = None
) -> dict[str, Any] | None:
    """Return entitlement row for session_id, or None if unknown."""
    sid = (session_id or "").strip()
    if not sid:
        return None
    init_db()
    t = now if now is not None else time.time()
    conn = _connect()
    try:
        cur = conn.execute(
            """
            SELECT session_id, status, platform, reason, created_at, updated_at,
                   payment_intent_id, subscription_id, valid_until, keygen,
                   customer_email, billing_interval
            FROM connect_entitlements WHERE session_id = ?
            """,
            (sid,),
        )
        row = cur.fetchone()
        if not row:
            return None
        vu = row["valid_until"]
        try:
            vu_f = float(vu) if vu is not None else None
        except (TypeError, ValueError):
            vu_f = None
        status = row["status"]
        allowed = _entitlement_connect_allowed(status, vu_f, now=t)
        # Auto-expire at period end for API honesty (subscription cancelled)
        if status == ENTITLEMENT_ACTIVE and vu_f is not None and not allowed:
            conn.execute(
                """
                UPDATE connect_entitlements
                SET status = ?, reason = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (ENTITLEMENT_REVOKED, "subscription_period_ended", t, sid),
            )
            status = ENTITLEMENT_REVOKED
            # Revoke bound devices for this session
            conn.execute(
                "DELETE FROM device_entitlements WHERE session_id = ?", (sid,)
            )
        try:
            kg = normalize_keygen(str(row["keygen"] or ""))
        except (KeyError, IndexError, TypeError):
            kg = ""
        try:
            email = str(row["customer_email"] or "").strip()
        except (KeyError, IndexError, TypeError):
            email = ""
        try:
            bill_iv = str(row["billing_interval"] or "").strip() or BILLING_INTERVAL_MONTH
        except (KeyError, IndexError, TypeError):
            bill_iv = BILLING_INTERVAL_MONTH
        connect_ok = (
            _entitlement_connect_allowed(status, vu_f, now=t)
            if status == ENTITLEMENT_ACTIVE
            else False
        )
        out = {
            "session_id": row["session_id"],
            "status": status,
            "platform": row["platform"] or "",
            "reason": row["reason"] or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "payment_intent_id": row["payment_intent_id"] or "",
            "subscription_id": row["subscription_id"] or "",
            "valid_until": vu_f,
            "keygen": kg,
            "customer_email": email,
            "billing_interval": bill_iv,
            "connect_allowed": connect_ok,
        }
        out["licence_status"] = licence_status_from_entitlement(out, now=t)
        return out
    finally:
        conn.close()


def mark_keygen_activated(
    session_id: str, *, now: float | None = None
) -> bool:
    """Stamp first successful keygen activation (idempotent).

    Used so admin **Licence database** can show tester mints only after the
    client has successfully verified the keygen (not at operator mint time).
    Returns True when a stamp was written (first activation).
    """
    sid = (session_id or "").strip()
    if not sid:
        return False
    init_db()
    t = float(now if now is not None else time.time())
    conn = _connect()
    try:
        cur = conn.execute(
            """
            UPDATE connect_entitlements
            SET keygen_activated_at = ?, updated_at = ?
            WHERE session_id = ?
              AND (keygen_activated_at IS NULL OR keygen_activated_at = 0)
            """,
            (t, t, sid),
        )
        return int(cur.rowcount or 0) > 0
    finally:
        conn.close()


def get_connect_entitlement_by_keygen(
    keygen: str, *, now: float | None = None
) -> dict[str, Any] | None:
    """Lookup entitlement by customer keygen (subscription unlock path).

    Returns the same shape as :func:`get_connect_entitlement`. When the bound
    subscription/payment is failed/revoked or period ended, ``connect_allowed``
    is False — the keygen is useless until a new active entitlement exists.

    First successful lookup stamps ``keygen_activated_at`` (client keygen
    activation path) so tester licences can appear in the admin licence list.

    **App version is not a factor:** the same ``RPT-KEY-…`` remains valid across
    monopin upgrades while the subscription is active. Clients must re-enter
    the original keygen on a newer build without needing a new mint.
    """
    kg = normalize_keygen(keygen)
    if not kg or not kg.startswith("RPT-KEY-"):
        return None
    init_db()
    t = now if now is not None else time.time()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT session_id FROM connect_entitlements WHERE keygen = ?",
            (kg,),
        ).fetchone()
        if not row:
            return None
        sid = str(row["session_id"] or "")
    finally:
        conn.close()
    if not sid:
        return None
    # Real client activation path: first successful keygen verify.
    mark_keygen_activated(sid, now=t)
    return get_connect_entitlement(sid, now=t)


def connect_entitlement_allows(session_id: str, *, now: float | None = None) -> bool:
    ent = get_connect_entitlement(session_id, now=now)
    if not ent:
        return False
    return bool(ent.get("connect_allowed"))


def normalize_device_pub_hex(raw: str) -> str:
    """Return 64-char lowercase hex for a 32-byte Ed25519 device public key."""
    s = (raw or "").strip().lower().replace(":", "").replace(" ", "")
    if s.startswith("0x"):
        s = s[2:]
    if len(s) != 64:
        return ""
    try:
        bytes.fromhex(s)
    except ValueError:
        return ""
    return s


def bind_device_entitlement(
    session_id: str,
    device_pub_hex: str,
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Bind a client device Ed25519 pub to a paid session (node HELLO gate).

    Requires the session entitlement to currently allow Connect.
    """
    sid = (session_id or "").strip()
    pub = normalize_device_pub_hex(device_pub_hex)
    if not sid or not pub:
        return {"ok": False, "error": "missing_session_or_device_pub"}
    ent = get_connect_entitlement(sid, now=now)
    if not ent or not ent.get("connect_allowed"):
        return {"ok": False, "error": "entitlement_not_active", "session_id": sid}
    t = now if now is not None else time.time()
    init_db()
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO device_entitlements(device_pub_hex, session_id, created_at, updated_at)
            VALUES (?,?,?,?)
            ON CONFLICT(device_pub_hex) DO UPDATE SET
                session_id = excluded.session_id,
                updated_at = excluded.updated_at
            """,
            (pub, sid, t, t),
        )
    finally:
        conn.close()
    return {
        "ok": True,
        "device_pub_hex": pub,
        "session_id": sid,
        "connect_allowed": True,
        "valid_until": ent.get("valid_until"),
        "status": ent.get("status"),
    }


def get_device_entitlement(
    device_pub_hex: str, *, now: float | None = None
) -> dict[str, Any]:
    """Lookup Connect allowance for a device public key (node residual gate)."""
    pub = normalize_device_pub_hex(device_pub_hex)
    if not pub:
        return {
            "device_pub_hex": "",
            "connect_allowed": False,
            "status": "unknown",
            "error": "bad_device_pub",
        }
    init_db()
    t = now if now is not None else time.time()
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT session_id FROM device_entitlements WHERE device_pub_hex = ?",
            (pub,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return {
            "device_pub_hex": pub,
            "connect_allowed": False,
            "status": "unknown",
            "reason": "device_not_bound",
        }
    sid = str(row["session_id"])
    ent = get_connect_entitlement(sid, now=t)
    if not ent:
        return {
            "device_pub_hex": pub,
            "session_id": sid,
            "connect_allowed": False,
            "status": "unknown",
            "reason": "session_missing",
        }
    return {
        "device_pub_hex": pub,
        "session_id": sid,
        "status": ent["status"],
        "valid_until": ent.get("valid_until"),
        "connect_allowed": bool(ent.get("connect_allowed")),
        "reason": ent.get("reason") or "",
    }


def find_session_id_by_subscription(subscription_id: str) -> str:
    sub = (subscription_id or "").strip()
    if not sub:
        return ""
    init_db()
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT session_id FROM connect_entitlements "
            "WHERE subscription_id = ? LIMIT 1",
            (sub,),
        )
        row = cur.fetchone()
        return str(row["session_id"]) if row else ""
    finally:
        conn.close()


def set_entitlement_valid_until(
    session_id: str,
    valid_until: float | None,
    *,
    reason: str = "subscription_period",
    now: float | None = None,
) -> bool:
    """Keep entitlement active until *valid_until* (subscription cancel-at-period-end)."""
    sid = (session_id or "").strip()
    if not sid:
        return False
    init_db()
    t = now if now is not None else time.time()
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT session_id FROM connect_entitlements WHERE session_id = ?",
            (sid,),
        )
        if not cur.fetchone():
            return False
        # If period already ended, revoke immediately
        if valid_until is not None and float(valid_until) <= t:
            conn.execute(
                """
                UPDATE connect_entitlements
                SET status = ?, reason = ?, valid_until = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (ENTITLEMENT_REVOKED, "subscription_period_ended", float(valid_until), t, sid),
            )
            conn.execute(
                "DELETE FROM device_entitlements WHERE session_id = ?", (sid,)
            )
        else:
            conn.execute(
                """
                UPDATE connect_entitlements
                SET status = ?, reason = ?, valid_until = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (
                    ENTITLEMENT_ACTIVE,
                    str(reason or "subscription_period")[:200],
                    float(valid_until) if valid_until is not None else None,
                    t,
                    sid,
                ),
            )
    finally:
        conn.close()
    return True


def _session_id_from_stripe_object(obj: dict[str, Any]) -> str:
    """Extract Checkout session id from various Stripe event objects."""
    if not isinstance(obj, dict):
        return ""
    # checkout.session.*
    oid = str(obj.get("id") or "")
    if oid.startswith("cs_"):
        return oid
    # payment_intent / charge may embed session via metadata
    meta = obj.get("metadata") or {}
    if isinstance(meta, dict):
        for key in ("checkout_session_id", "session_id", "cs_id"):
            v = str(meta.get(key) or "").strip()
            if v.startswith("cs_"):
                return v
    for key in ("checkout_session", "session"):
        nested = obj.get(key)
        if isinstance(nested, str) and nested.startswith("cs_"):
            return nested
        if isinstance(nested, dict):
            nid = str(nested.get("id") or "")
            if nid.startswith("cs_"):
                return nid
    return oid if oid.startswith("cs_") else ""


def _payment_intent_id_from_stripe_object(obj: dict[str, Any]) -> str:
    """Extract PaymentIntent id (pi_…) from charge / PI / session objects."""
    if not isinstance(obj, dict):
        return ""
    oid = str(obj.get("id") or "")
    if oid.startswith("pi_"):
        return oid
    pi = obj.get("payment_intent")
    if isinstance(pi, str) and pi.startswith("pi_"):
        return pi
    if isinstance(pi, dict):
        pid = str(pi.get("id") or "")
        if pid.startswith("pi_"):
            return pid
    meta = obj.get("metadata") or {}
    if isinstance(meta, dict):
        for key in ("payment_intent_id", "payment_intent", "pi_id"):
            v = str(meta.get(key) or "").strip()
            if v.startswith("pi_"):
                return v
    return ""


def find_session_id_by_payment_intent(payment_intent_id: str) -> str:
    """Map Stripe PaymentIntent → Checkout session_id from stored entitlements/grants.

    Payment Link charges often omit checkout_session_id metadata; we bind
    ``payment_intent_id`` at paid checkout completion so refunds still revoke.
    """
    pi = (payment_intent_id or "").strip()
    if not pi.startswith("pi_"):
        return ""
    init_db()
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT session_id FROM connect_entitlements "
            "WHERE payment_intent_id = ? LIMIT 1",
            (pi,),
        )
        row = cur.fetchone()
        if row and row["session_id"]:
            return str(row["session_id"])
        cur = conn.execute(
            "SELECT session_id FROM grants WHERE payment_intent_id = ? "
            "AND session_id IS NOT NULL AND session_id != '' LIMIT 1",
            (pi,),
        )
        row = cur.fetchone()
        if row and row["session_id"]:
            return str(row["session_id"])
    finally:
        conn.close()
    return ""


def client_entitlement_file_payload(session_id: str) -> dict[str, Any] | None:
    """JSON body for payment_entitlement.json download (client product data)."""
    ent = get_connect_entitlement(session_id)
    if not ent:
        return None
    return {
        "session_id": ent["session_id"],
        "status": ent["status"],
        "platform": ent.get("platform") or "",
        "reason": ent.get("reason") or "",
        "updated_at": float(ent.get("updated_at") or time.time()),
        "valid_until": ent.get("valid_until"),
        "connect_allowed": bool(ent.get("connect_allowed")),
        "keygen": ent.get("keygen") or "",
    }


def customer_email_from_checkout_object(
    obj: dict[str, Any],
    *,
    http_get: HttpGetFn | None = None,
    secret_key: str | None = None,
    fetch_customer: bool = True,
) -> str:
    """Extract customer email from a Stripe Checkout Session object.

    Prefers session fields (``customer_email``, ``customer_details.email``).
    When only a Customer id is present (common on some Payment Link payloads),
    optionally GETs ``/v1/customers/{id}`` so fulfilment mail is not skipped.
    """
    if not isinstance(obj, dict):
        return ""
    for key in ("customer_email", "customer_details"):
        if key == "customer_email":
            em = str(obj.get("customer_email") or "").strip()
            if em and "@" in em:
                return em
        else:
            details = obj.get("customer_details") or {}
            if isinstance(details, dict):
                em = str(details.get("email") or "").strip()
                if em and "@" in em:
                    return em
    # Nested customer object sometimes present
    cust = obj.get("customer")
    if isinstance(cust, dict):
        em = str(cust.get("email") or "").strip()
        if em and "@" in em:
            return em
    details = obj.get("customer_details")
    if isinstance(details, dict):
        em = str(details.get("email") or "").strip()
        if em and "@" in em:
            return em
    # Customer id only — resolve via Stripe API when secret is available
    if fetch_customer and isinstance(cust, str) and cust.startswith("cus_"):
        em = retrieve_customer_email(
            cust, http_get=http_get, secret_key=secret_key
        )
        if em:
            return em
    return ""


def retrieve_customer_email(
    customer_id: str,
    *,
    http_get: HttpGetFn | None = None,
    secret_key: str | None = None,
) -> str:
    """GET Stripe Customer and return email, or empty string."""
    cid = (customer_id or "").strip()
    if not cid.startswith("cus_"):
        return ""
    key = (secret_key if secret_key is not None else stripe_secret_key()).strip()
    if not key:
        return ""
    url = "https://api.stripe.com/v1/customers/" + urllib.parse.quote(cid, safe="")
    getter = http_get or _default_http_get
    status, raw = getter(url, {"Authorization": f"Bearer {key}"})
    if status != 200 or not raw:
        return ""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    em = str(data.get("email") or "").strip()
    return em if em and "@" in em else ""


def absolute_download_url(token: str, *, base_url: str | None = None) -> str:
    """Build a public absolute ``/download?token=…`` URL for fulfilment email.

    Prefers *base_url*, then :func:`public_base_url`. When that is still a local
    loopback default, falls back to :func:`production_public_base_url` so
    customers never receive ``http://127.0.0.1/…`` download links.
    """
    tok = (token or "").strip()
    if not tok:
        return ""
    base = (base_url if base_url is not None else public_base_url()).rstrip("/")
    low = base.lower()
    if (
        not base
        or low.startswith("http://127.0.0.1")
        or low.startswith("http://localhost")
        or low.startswith("https://127.0.0.1")
        or low.startswith("https://localhost")
    ):
        base = production_public_base_url().rstrip("/")
    q = urllib.parse.quote(tok, safe="")
    return f"{base}/download?token={q}"


def build_fulfilment_email_payload(
    *,
    to_email: str,
    keygen: str,
    purchase_id: str,
    download_url: str,
    platform: str = "",
    session_id: str = "",
    filename: str = "",
) -> dict[str, Any]:
    """Build the customer fulfilment email (keygen + PPI + download link).

    Pure helper — no I/O. Used by tests and :func:`send_fulfilment_email`.
    Body always includes :data:`KEYGEN_UNLOCK_INSTRUCTION`, the customer
    **KEYGEN** (``RPT-KEY-…``), the absolute download URL (when provided),
    :data:`DOWNLOAD_LINK_VALIDITY_ADVICE` (1-hour reusable), and support
    contact :data:`SUPPORT_EMAIL` (``rus@…``).

    **Not** Stripe's receipt/invoice PDF — those cannot carry KEYGEN or the
    paid download token.
    """
    to_addr = (to_email or "").strip()
    kg = normalize_keygen(keygen)
    pid = normalize_purchase_id(purchase_id) or (purchase_id or "").strip().upper()
    dl = (download_url or "").strip()
    # Relative path → absolute production URL for the customer inbox
    if dl.startswith("/download"):
        dl = absolute_download_url(
            urllib.parse.parse_qs(urllib.parse.urlparse(dl).query).get("token", [""])[0]
            or "",
        ) or (production_public_base_url().rstrip("/") + dl)
    elif dl and not (dl.startswith("http://") or dl.startswith("https://")):
        base = production_public_base_url().rstrip("/")
        dl = f"{base}/{dl.lstrip('/')}"
    plat = (platform or "").strip().lower()
    sid = (session_id or "").strip()
    fname = (filename or "").strip()
    subject = (
        f"Your {PUBLIC_BUSINESS_NAME} Restore Privacy download, KEYGEN, and unlock"
    )
    ttl_label = (
        f"{DOWNLOAD_LINK_TTL_HOURS} hour"
        f"{'s' if DOWNLOAD_LINK_TTL_HOURS != 1 else ''}"
    )
    has_keygen = bool(kg and kg.upper().startswith("RPT-KEY-"))
    if has_keygen:
        kg_line = f"Keygen: {kg}"
    else:
        # Should not happen after a successful paid session; keep observable
        kg_line = (
            f"Keygen: (missing — contact {SUPPORT_EMAIL} with your PPI for a new keygen)"
        )
    if dl:
        dl_line = (
            f"Download link (valid {ttl_label}; re-download if interrupted): {dl}"
        )
    else:
        # Should not happen after a successful grant; keep observable for support
        dl_line = (
            f"Download link: (missing — contact {SUPPORT_EMAIL} with your PPI)"
        )
    body_lines = [
        f"Thank you for purchasing Restore Privacy from {PUBLIC_BUSINESS_NAME}.",
        "",
        "This email contains your **KEYGEN** (to unlock the app) and your "
        f"**download link** (valid for {ttl_label}).",
        "",
        KEYGEN_UNLOCK_INSTRUCTION,
        "",
        kg_line,
        f"Product purchase identifier (PPI): {pid}",
        dl_line,
        "",
        DOWNLOAD_LINK_VALIDITY_ADVICE,
        "",
        "Install flow: Install → accept licence terms and conditions → enter keygen → unlock.",
        "Your subscription is active once payment succeeds "
        "(£2.45/month or £27.93/year — Annual saves 5%).",
        "The keygen only unlocks Connect while your subscription/payment is active.",
        "If payment fails later (failed charge, refund, dispute, or subscription ends),",
        "this keygen becomes useless and the app locks until payment is active again.",
        "",
        "Note: Stripe's own receipt / invoice email is only a payment record "
        f"(PDF). Your KEYGEN and installer download link are in **this** email "
        f"(download link valid for {ttl_label} only).",
        "",
    ]
    if fname:
        body_lines.append(f"Package: {fname}")
    if plat:
        body_lines.append(f"Platform: {plat}")
    if sid:
        body_lines.append(f"Checkout session (support): {sid}")
    body_lines.extend(
        [
            "",
            "Save this email. Keep your KEYGEN; the download link expires after "
            "the time window above while the keygen stays bound to your entitlement.",
            "",
            FULFILMENT_SUPPORT_FOOTER,
            f"— {PUBLIC_BUSINESS_NAME}",
        ]
    )
    body = "\n".join(body_lines) + "\n"
    return {
        "to": to_addr,
        "subject": subject,
        "body": body,
        "keygen": kg,
        "purchase_id": pid,
        "download_url": dl,
        "platform": plat,
        "session_id": sid,
        "filename": fname,
        "unlock_instruction": KEYGEN_UNLOCK_INSTRUCTION,
        "has_keygen": has_keygen,
        "support_email": SUPPORT_EMAIL,
        "business_name": PUBLIC_BUSINESS_NAME,
        "has_download_url": bool(dl and "/download?token=" in dl),
    }


# Env keys read by :func:`fulfilment_smtp_config` / send path (Render blueprint + docs).
FULFILMENT_SMTP_ENV_KEYS: tuple[str, ...] = (
    "RPT_FULFILMENT_SMTP_HOST",
    "RPT_FULFILMENT_SMTP_PORT",
    "RPT_FULFILMENT_SMTP_USER",
    "RPT_FULFILMENT_SMTP_PASSWORD",
    "RPT_FULFILMENT_FROM_EMAIL",
    "RPT_FULFILMENT_SMTP_TLS",
)


def fulfilment_smtp_env_keys() -> list[str]:
    """Documented SMTP env keys the fulfilment mailer actually reads (no secrets)."""
    return list(FULFILMENT_SMTP_ENV_KEYS)


def fulfilment_smtp_config() -> dict[str, Any]:
    """Read optional SMTP for transactional fulfilment email.

    Uses process env first, then admin-persisted ``processor_env.json`` (same
    path as Stripe secrets) so /admin SMTP fields work after save/restart.
    """
    host = _env_or_processor_store("RPT_FULFILMENT_SMTP_HOST")
    port_raw = (
        _env_or_processor_store("RPT_FULFILMENT_SMTP_PORT") or "587"
    ).strip() or "587"
    try:
        port = int(port_raw)
    except ValueError:
        port = 587
    user = _env_or_processor_store("RPT_FULFILMENT_SMTP_USER")
    password = _env_or_processor_store("RPT_FULFILMENT_SMTP_PASSWORD")
    from_addr = (
        _env_or_processor_store("RPT_FULFILMENT_FROM_EMAIL", "RPT_FULFILMENT_SMTP_FROM")
        or "noreply@restoreprivacy.online"
    ).strip()
    tls_raw = (
        _env_or_processor_store("RPT_FULFILMENT_SMTP_TLS") or "1"
    ).strip().lower()
    use_tls = tls_raw not in ("0", "false", "no", "off")
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_addr": from_addr,
        "use_tls": use_tls,
        "configured": bool(host),
        "env_keys": fulfilment_smtp_env_keys(),
    }


def probe_fulfilment_smtp_login(
    cfg: dict[str, Any] | None = None,
    *,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Attempt real SMTP connect + STARTTLS + login (no message sent).

    Proves production credentials work end-to-end against the provider without
    delivering mail. Returns non-secret ``{ok, stage, error?}``.
    """
    c = cfg if isinstance(cfg, dict) else fulfilment_smtp_config()
    host = str(c.get("host") or "").strip()
    if not host:
        return {
            "ok": False,
            "stage": "config",
            "error": "smtp_not_configured",
            "detail": "RPT_FULFILMENT_SMTP_HOST empty",
        }
    try:
        import smtplib

        port = int(c.get("port") or 587)
        user = str(c.get("user") or "")
        password = str(c.get("password") or "")
        with smtplib.SMTP(host, port, timeout=float(timeout)) as smtp:
            smtp.ehlo()
            if c.get("use_tls"):
                smtp.starttls()
                smtp.ehlo()
            if user:
                smtp.login(user, password)
            # quit on context exit — no send_message
        return {
            "ok": True,
            "stage": "login",
            "error": None,
            "detail": "SMTP connect+login succeeded (no message sent)",
            "host_set": True,
            "tls": bool(c.get("use_tls")),
            "auth_used": bool(user),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "stage": "smtp",
            "error": type(exc).__name__,
            "detail": str(exc)[:240],
            "host_set": True,
            "tls": bool(c.get("use_tls")),
            "auth_used": bool(str(c.get("user") or "")),
        }


def assess_fulfilment_smtp_readiness(
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map SMTP env presence → operator enablement verdict (no secrets in output).

    Code's ``configured`` flag is **host non-empty** only (send path skips when
    host unset). Real provider send typically also needs user + password.
    """
    c = cfg if isinstance(cfg, dict) else fulfilment_smtp_config()
    host = bool(str(c.get("host") or "").strip())
    user = bool(str(c.get("user") or "").strip())
    password = bool(str(c.get("password") or "").strip())
    from_addr = bool(str(c.get("from_addr") or "").strip())
    port = c.get("port")
    try:
        port_ok = int(port) > 0
    except (TypeError, ValueError):
        port_ok = False
    use_tls = bool(c.get("use_tls"))
    # Presence map only — never echo secret values
    keys_present = {
        "RPT_FULFILMENT_SMTP_HOST": host,
        "RPT_FULFILMENT_SMTP_PORT": port_ok,
        "RPT_FULFILMENT_SMTP_USER": user,
        "RPT_FULFILMENT_SMTP_PASSWORD": password,
        "RPT_FULFILMENT_FROM_EMAIL": from_addr,
        "RPT_FULFILMENT_SMTP_TLS": True,  # defaulted when unset
    }
    if not host:
        status = "disabled"
        detail = (
            "SMTP host unset — send_fulfilment_email skips with smtp_not_configured"
        )
        email_flow_enabled = False
    elif host and (not user or not password):
        status = "host_only_incomplete_auth"
        detail = (
            "Host set so configured=True, but user and/or password empty — "
            "typical providers will fail login; set SMTP user + password on Render"
        )
        email_flow_enabled = False
    elif host and user and password and from_addr and port_ok:
        status = "ready_to_attempt_send"
        detail = (
            "Host + user + password + from + port present — fulfilment email "
            "will attempt SMTP send (TLS=%s)" % ("on" if use_tls else "off")
        )
        email_flow_enabled = True
    else:
        status = "partial"
        detail = "Host set but from address or port incomplete"
        email_flow_enabled = False
    missing = [k for k, ok in keys_present.items() if not ok and k != "RPT_FULFILMENT_SMTP_TLS"]
    return {
        "status": status,
        "email_flow_enabled": email_flow_enabled,
        "code_configured_flag": bool(c.get("configured")),
        "keys_present": keys_present,
        "missing_or_empty": missing,
        "port": int(port) if port_ok else None,
        "use_tls": use_tls,
        "detail": detail,
        "env_keys": fulfilment_smtp_env_keys(),
    }


def desired_payment_link_trial_fields() -> dict[str, Any]:
    """Target Stripe **subscription** catalog shape (single source of truth).

    Site plan page + Checkout Session use these amounts/products. Pure helper
    (no network). Configure script can sync Dashboard prices when
    ``STRIPE_SECRET_KEY`` is set.

    ``trial_period_days`` is **0** (Stripe field; not a product trial). Annual is 5% off 12× monthly.
    """
    return {
        "payment_link_id": DEFAULT_STRIPE_PAYMENT_LINK_ID,
        "payment_page_url": site_pay_plan_path(),  # site-hosted primary entry
        "price_id": stripe_subscription_price_id_monthly(),
        "payment_link_id_yearly": DEFAULT_STRIPE_PAYMENT_LINK_ID_YEARLY,
        "payment_page_url_yearly": site_pay_plan_path(interval=BILLING_INTERVAL_YEAR),
        "price_id_yearly": stripe_subscription_price_id_yearly(),
        "product_id_monthly": DEFAULT_STRIPE_PRODUCT_ID_MONTHLY,
        "product_id_yearly": DEFAULT_STRIPE_PRODUCT_ID_YEARLY,
        "product_name_monthly": STRIPE_PRODUCT_NAME_MONTHLY,
        "product_name_yearly": STRIPE_PRODUCT_NAME_YEARLY,
        "currency": PRICE_CURRENCY,
        "unit_amount_pence": PRICE_PENCE,
        "unit_amount_yearly_pence": PRICE_YEARLY_PENCE,
        "yearly_discount_percent": YEARLY_DISCOUNT_PERCENT,
        "recurring_interval": "month",
        "recurring_interval_yearly": "year",
        "trial_period_days": 0,
        "mode": CATALOG_STRIPE_PAYMENT_MODE,
        "catalog_entry": SITE_PAY_PLAN_PATH,
        # Legacy key name kept for tests/config (no trial product / no trial copy).
        "homepage_trial_sentence": (
            "Select your plan — Monthly or Annual (5% off yearly) — "
            "subscription starts when you pay"
        ),
    }


def render_pay_plan_page_html(
    platform: str = "",
    *,
    interval: str = BILLING_INTERVAL_MONTH,
    error: str = "",
) -> bytes:
    """Site-styled **Select your plan** page (Monthly | Annual) for one platform.

    Pure HTML builder (no network). Continue submits to ``POST /pay/checkout``
    which creates a Stripe subscription Checkout Session for the chosen plan.
    """
    try:
        from public_chrome import (
            PUBLIC_BRAND_TITLE,
            public_brand_header_html,
            public_head_open,
            public_page_close,
            public_site_css,
        )
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import (  # type: ignore
            PUBLIC_BRAND_TITLE,
            public_brand_header_html,
            public_head_open,
            public_page_close,
            public_site_css,
        )
    try:
        from downloads import available_downloads, platform_face_title
    except ImportError:  # pragma: no cover
        from status_page.downloads import (  # type: ignore
            available_downloads,
            platform_face_title,
        )

    plat = (platform or "").strip().lower()
    iv = (interval or BILLING_INTERVAL_MONTH).strip().lower()
    if iv in ("year", "yearly", "annual", "annually"):
        iv = BILLING_INTERVAL_YEAR
    else:
        iv = BILLING_INTERVAL_MONTH

    platforms = [a.platform for a in available_downloads()]
    if plat and plat not in platforms:
        plat = ""

    def _esc(s: str) -> str:
        return (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    opts = []
    for p in platforms:
        sel = " selected" if p == plat else ""
        opts.append(
            f'<option value="{_esc(p)}"{sel}>{_esc(platform_face_title(p))}</option>'
        )
    platform_options = "\n            ".join(opts)
    month_checked = " checked" if iv == BILLING_INTERVAL_MONTH else ""
    year_checked = " checked" if iv == BILLING_INTERVAL_YEAR else ""
    err_html = ""
    if (error or "").strip():
        err_html = (
            f'<p class="pay-error" id="pay-error" role="alert">'
            f"{_esc(error.strip())}</p>"
        )
    save_pct = YEARLY_DISCOUNT_PERCENT
    monthly_label = PRICE_LABEL
    yearly_label = PRICE_YEARLY_LABEL
    full_yearly = PRICE_YEARLY_FULL_LABEL
    product_m = STRIPE_PRODUCT_NAME_MONTHLY
    product_y = STRIPE_PRODUCT_NAME_YEARLY

    extra_css = """
.pay-plan-shell { max-width: 32rem; margin: 0 auto 2rem; }
.pay-plan-card {
  background: var(--rb-card); border-radius: var(--rb-radius);
  border: 1px solid var(--rb-card-border); padding: 1.25rem 1.35rem;
  box-shadow: 0 10px 28px rgba(4,12,28,0.35);
}
.pay-plan-card h2 {
  margin: 0 0 0.35rem; font-size: 1.15rem; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--rb-cream);
}
.pay-plan-lead { color: var(--rb-muted); font-size: 0.92rem; line-height: 1.45; margin: 0 0 1rem; }
.pay-field { margin: 0.85rem 0; text-align: left; }
.pay-field label.pay-label {
  display: block; font-weight: 700; font-size: 0.82rem; letter-spacing: 0.04em;
  text-transform: uppercase; color: var(--rb-muted); margin-bottom: 0.4rem;
}
.pay-field select {
  width: 100%; box-sizing: border-box; padding: 0.65rem 0.75rem;
  border-radius: 10px; border: 1px solid rgba(174,208,234,0.35);
  background: rgba(8,18,32,0.65); color: var(--rb-cream); font: inherit;
}
.pay-plans { display: flex; flex-direction: column; gap: 0.65rem; }
.pay-plan-option {
  display: block; cursor: pointer; border-radius: 12px;
  border: 1px solid rgba(174,208,234,0.28); padding: 0.85rem 0.95rem;
  background: rgba(8,18,32,0.45); transition: border-color 0.12s, box-shadow 0.12s;
}
.pay-plan-option:has(input:checked) {
  border-color: var(--rb-neon-cyan); box-shadow: 0 0 0 1px rgba(0,229,255,0.35);
  background: rgba(20,50,90,0.55);
}
.pay-plan-option input { margin-right: 0.55rem; accent-color: var(--rb-btn); }
.pay-plan-title { font-weight: 800; color: #fff; font-size: 1.02rem; }
.pay-plan-price { font-weight: 700; color: var(--rb-soft); margin-top: 0.2rem; }
.pay-plan-note { font-size: 0.82rem; color: var(--rb-muted); margin-top: 0.15rem; }
.pay-save-badge {
  display: inline-block; margin-left: 0.35rem; padding: 0.12rem 0.45rem;
  border-radius: 999px; font-size: 0.72rem; font-weight: 800;
  background: rgba(57,255,106,0.18); color: #39ff6a; letter-spacing: 0.03em;
}
.pay-was { text-decoration: line-through; opacity: 0.7; margin-right: 0.35rem; }
.pay-submit {
  width: 100%; margin-top: 1.15rem; padding: 0.85rem 1rem; border: 0;
  border-radius: 12px; font-weight: 800; font-size: 1rem; cursor: pointer;
  font-family: inherit; color: #fff;
  background: linear-gradient(180deg, var(--rb-btn) 0%, var(--rb-btn-deep) 100%);
  box-shadow: 0 4px 14px rgba(7,30,60,0.4);
}
.pay-submit:hover { filter: brightness(1.08); }
.pay-error {
  color: #fecaca; background: rgba(127,29,29,0.35); border: 1px solid #b91c1c;
  border-radius: 10px; padding: 0.65rem 0.85rem; margin: 0 0 0.85rem; text-align: left;
}
.pay-back { display: inline-block; margin-top: 1rem; color: var(--rb-link); font-weight: 600; }
.pay-auto-renew {
  margin: 1rem 0 0; text-align: left; padding: 0.75rem 0.85rem;
  border-radius: 10px; border: 1px solid rgba(174,208,234,0.22);
  background: rgba(8,18,32,0.4);
}
.pay-auto-renew label {
  display: flex; align-items: flex-start; gap: 0.5rem; cursor: pointer;
  font-weight: 700; color: var(--rb-cream); font-size: 0.95rem;
}
.pay-auto-renew input { margin-top: 0.2rem; accent-color: var(--rb-btn); }
.pay-auto-renew-help {
  margin: 0.4rem 0 0 1.55rem; font-size: 0.8rem; color: var(--rb-muted); line-height: 1.4;
}
"""
    try:
        from downloads import AUTO_RENEW_HELP, AUTO_RENEW_LABEL
    except ImportError:  # pragma: no cover
        from status_page.downloads import (  # type: ignore
            AUTO_RENEW_HELP,
            AUTO_RENEW_LABEL,
        )
    body = f"""
  <div class="page-shell pay-plan-shell" id="pay-plan-shell">
{public_brand_header_html(title=PUBLIC_BRAND_TITLE, active=None)}
    <section class="pay-plan-card panel-card" id="pay-plan-card" aria-labelledby="pay-plan-heading">
      <h2 id="pay-plan-heading">Select your plan</h2>
      <p class="pay-plan-lead" id="pay-plan-lead">
        One device licence. Choose <strong>Monthly</strong> (access for one month) or
        <strong>Annual</strong> (access for one year, save {save_pct}% vs paying monthly).
        Subscription starts when you pay. Without renewal after the paid period,
        Connect expires and the client becomes unusable until you renew.
        You will complete card payment securely on Stripe.
      </p>
      {err_html}
      <form id="pay-plan-form" class="pay-plan-form" method="post" action="/pay/checkout">
        <div class="pay-field" id="pay-platform-field">
          <label class="pay-label" for="pay-platform">Platform</label>
          <select name="platform" id="pay-platform" required aria-required="true">
            <option value="" disabled{" selected" if not plat else ""}>Choose your device…</option>
            {platform_options}
          </select>
        </div>
        <div class="pay-field" id="pay-interval-field">
          <span class="pay-label" id="pay-interval-label">Select your plan</span>
          <div class="pay-plans" role="radiogroup" aria-labelledby="pay-interval-label">
            <label class="pay-plan-option" id="pay-option-month" data-interval="month">
              <input type="radio" name="interval" value="month"{month_checked}
                     aria-label="Monthly VPN plan"/>
              <span class="pay-plan-title">{_esc(product_m)}</span>
              <div class="pay-plan-price">{_esc(monthly_label)} / month</div>
              <div class="pay-plan-note">Billed monthly · cancel anytime in Stripe</div>
            </label>
            <label class="pay-plan-option" id="pay-option-year" data-interval="year">
              <input type="radio" name="interval" value="year"{year_checked}
                     aria-label="Yearly VPN plan"/>
              <span class="pay-plan-title">{_esc(product_y)}
                <span class="pay-save-badge">SAVE {save_pct}%</span></span>
              <div class="pay-plan-price">
                <span class="pay-was">{_esc(full_yearly)}</span>{_esc(yearly_label)} / year
              </div>
              <div class="pay-plan-note">5% off vs 12 × monthly ({_esc(monthly_label)} × 12)</div>
            </label>
          </div>
        </div>
        <div class="pay-auto-renew" id="pay-auto-renew-field">
          <input type="hidden" name="auto_renew" value="0" id="pay-auto-renew-off"/>
          <label for="pay-auto-renew">
            <input type="checkbox" name="auto_renew" value="1" id="pay-auto-renew"
                   checked aria-describedby="pay-auto-renew-help"/>
            <span>{_esc(AUTO_RENEW_LABEL)}</span>
          </label>
          <p class="pay-auto-renew-help" id="pay-auto-renew-help">{_esc(AUTO_RENEW_HELP)}</p>
        </div>
        <button type="submit" class="pay-submit" id="pay-submit">
          Continue to secure checkout
        </button>
      </form>
      <a class="pay-back" id="pay-back-home" href="/">← Back to catalog</a>
    </section>
  </div>
"""
    html = (
        public_head_open(title="Select your plan — Restore Privacy", extra_css=extra_css)
        + body
        + public_page_close()
    )
    return html.encode("utf-8")


def _normalize_trial_days(value: Any) -> int | None:
    """Map Stripe trial_period_days to int; treat blank/None as no trial (None)."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def payment_link_matches_trial_subscription(price_obj: dict[str, Any]) -> dict[str, Any]:
    """Check a Stripe Price object against desired £2.45/mo + **no trial** fields.

    *price_obj* is a Stripe API Price dict (or redacted summary). Returns
    ``{ok, mismatches[], observed}`` without inventing success.

    Desired ``trial_period_days`` is 0: observed trial may be ``None`` (absent)
    or ``0``; any positive trial (e.g. 7) is a mismatch.
    """
    want = desired_payment_link_trial_fields()
    mismatches: list[str] = []
    if not isinstance(price_obj, dict):
        return {"ok": False, "mismatches": ["not_a_dict"], "observed": {}}
    currency = str(price_obj.get("currency") or "").strip().lower()
    amount = price_obj.get("unit_amount")
    try:
        amount_i = int(amount) if amount is not None else None
    except (TypeError, ValueError):
        amount_i = None
    recurring = price_obj.get("recurring") or {}
    if not isinstance(recurring, dict):
        recurring = {}
    interval = str(recurring.get("interval") or "").strip().lower()
    trial_i = _normalize_trial_days(recurring.get("trial_period_days"))
    if trial_i is None:
        trial_i = _normalize_trial_days(price_obj.get("trial_period_days"))
    # Some Dashboard prices put trial on the Payment Link / subscription_data
    # rather than the Price; callers may pass payment_link_trial_period_days.
    if currency != want["currency"]:
        mismatches.append(f"currency:{currency!r}!={want['currency']!r}")
    if amount_i != want["unit_amount_pence"]:
        mismatches.append(f"unit_amount:{amount_i!r}!={want['unit_amount_pence']}")
    if interval != want["recurring_interval"]:
        mismatches.append(f"interval:{interval!r}!={want['recurring_interval']!r}")
    link_trial_i = _normalize_trial_days(price_obj.get("payment_link_trial_period_days"))
    effective_trial = trial_i if trial_i is not None else link_trial_i
    want_trial = int(want["trial_period_days"] or 0)
    # No-trial target: None (absent) and 0 both OK; positive days fail.
    if want_trial == 0:
        if effective_trial is not None and int(effective_trial) != 0:
            mismatches.append(
                f"trial_period_days:{effective_trial!r}!=0 (must be 0)"
            )
    elif effective_trial != want_trial:
        mismatches.append(
            f"trial_period_days:{effective_trial!r}!={want_trial}"
        )
    observed = {
        "currency": currency,
        "unit_amount": amount_i,
        "interval": interval,
        "trial_period_days": effective_trial if effective_trial is not None else 0,
        "price_id": str(price_obj.get("id") or ""),
        "type": str(price_obj.get("type") or ""),
    }
    return {"ok": len(mismatches) == 0, "mismatches": mismatches, "observed": observed}


def _fulfilment_from_header(from_addr: str) -> str:
    """RFC-ish From with public business display name when address is bare."""
    raw = (from_addr or "").strip() or SUPPORT_EMAIL
    if "<" in raw and ">" in raw:
        return raw
    return f"{PUBLIC_BUSINESS_NAME} <{raw}>"


def send_fulfilment_email(
    payload: dict[str, Any],
    *,
    transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Send fulfilment email via SMTP (or injected *transport* for tests).

    Returns ``{ok, sent, error?, skipped?}``. Without SMTP host configured and
    without a transport, returns ok with ``skipped=True`` (payload still built
    by caller) so checkout fulfilment never fails on missing mail credentials.

    Sets **Reply-To** to :data:`SUPPORT_EMAIL` (``rus@restoreprivacy.online``)
    so customers can answer the fulfilment message.
    """
    if not isinstance(payload, dict):
        return {"ok": False, "sent": False, "error": "bad_payload"}
    to_addr = str(payload.get("to") or "").strip()
    if not to_addr or "@" not in to_addr:
        return {"ok": False, "sent": False, "error": "missing_to_email"}
    body = str(payload.get("body") or "")
    dl = str(payload.get("download_url") or "").strip()
    kg = str(payload.get("keygen") or "").strip()
    if not dl or "/download?token=" not in dl:
        # Observable when grant mint forgot the link — never pretend success
        if transport is None:
            print(
                "fulfilment_email_missing_download_url "
                f"to_domain={to_addr.split('@')[-1]!r} "
                f"has_body={bool(body)}",
                flush=True,
            )
    if not kg or not kg.upper().startswith("RPT-KEY-"):
        if transport is None:
            print(
                "fulfilment_email_missing_keygen "
                f"to_domain={to_addr.split('@')[-1]!r} "
                f"has_download={bool(dl and '/download?token=' in dl)}",
                flush=True,
            )
    if transport is not None:
        try:
            result = transport(payload)
            if isinstance(result, dict):
                return result
            return {"ok": True, "sent": True}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "sent": False, "error": str(exc)}
    cfg = fulfilment_smtp_config()
    if not cfg.get("configured"):
        return {
            "ok": True,
            "sent": False,
            "skipped": True,
            "error": "smtp_not_configured",
        }
    try:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = str(
            payload.get("subject")
            or f"Your {PUBLIC_BUSINESS_NAME} Restore Privacy download"
        )
        msg["From"] = _fulfilment_from_header(str(cfg["from_addr"]))
        msg["To"] = to_addr
        msg["Reply-To"] = SUPPORT_EMAIL
        msg.set_content(body)
        with smtplib.SMTP(str(cfg["host"]), int(cfg["port"]), timeout=30) as smtp:
            if cfg.get("use_tls"):
                smtp.starttls()
            user = str(cfg.get("user") or "")
            password = str(cfg.get("password") or "")
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        return {
            "ok": True,
            "sent": True,
            "skipped": False,
            "has_download_url": bool(dl and "/download?token=" in dl),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "sent": False, "error": str(exc)}


def fulfil_checkout_with_email(
    *,
    token: str,
    session_id: str,
    platform: str,
    filename: str,
    customer_email: str,
    keygen: str = "",
    purchase_id: str = "",
    base_url: str | None = None,
    transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """After paid grant: ensure **KEYGEN** + absolute download URL, then send.

    Order of work:
      1. Normalize / look up / mint keygen for the Checkout session (never leave
         blank when *session_id* exists after a paid grant).
      2. Build absolute ``/download?token=…`` URL when *token* is present.
      3. Build payload (body always has KEYGEN line + download line) and send.

    Returns dict with keygen, purchase_id, download_url, email payload, send result.
    """
    sid = (session_id or "").strip()
    plat = (platform or "").strip().lower()
    kg = normalize_keygen(keygen) if keygen else ""
    if sid and not kg:
        kg = normalize_keygen(assign_keygen_for_session(sid)) or ""
    # Still empty: force activate/mint so post-pay email never has blank Keygen
    if sid and not kg:
        kg = normalize_keygen(
            activate_connect_entitlement(sid, platform=plat)
        ) or ""
    if sid and not kg:
        kg = normalize_keygen(assign_keygen_for_session(sid)) or ""
    pid = normalize_purchase_id(purchase_id) if purchase_id else ""
    if not pid and token:
        pid = purchase_id_for_token(token) or ""
    tok = (token or "").strip()
    download_url = absolute_download_url(tok, base_url=base_url) if tok else ""
    path = f"/download?token={tok}" if tok else ""
    if tok and not download_url:
        print(
            f"fulfilment_download_url_empty session={sid!r} token_len={len(tok)}",
            flush=True,
        )
    if not kg:
        print(
            "fulfilment_email_missing_keygen "
            f"session={sid!r} has_token={bool(tok)}",
            flush=True,
        )
    email_payload = build_fulfilment_email_payload(
        to_email=customer_email,
        keygen=kg,
        purchase_id=pid or "",
        download_url=download_url,
        platform=plat or platform,
        session_id=sid,
        filename=filename,
    )
    # Prefer values normalized by the builder (canonical RPT-KEY- form)
    kg_out = str(email_payload.get("keygen") or kg or "")
    send_result = send_fulfilment_email(email_payload, transport=transport)
    return {
        "keygen": kg_out,
        "purchase_id": pid or email_payload.get("purchase_id") or "",
        "download_url": download_url or str(email_payload.get("download_url") or ""),
        "download_path": path,
        "email": email_payload,
        "send": send_result,
        "has_keygen": bool(email_payload.get("has_keygen")),
        "has_download_url": bool(email_payload.get("has_download_url")),
    }


def process_payment_failure_event(event: dict[str, Any]) -> str | None:
    """On failure/refund/dispute webhooks, revoke Connect entitlement.

    Returns session_id when revoked, else None.
    Subscription period end is handled by :func:`process_subscription_lifecycle_event`
    (cancel keeps access until ``current_period_end``).
    """
    etype = str(event.get("type") or "")
    fail_types = {
        "checkout.session.async_payment_failed",
        "checkout.session.expired",
        "payment_intent.payment_failed",
        "charge.failed",
        "charge.refunded",
        "charge.dispute.created",
        "invoice.payment_failed",
    }
    if etype not in fail_types:
        return None
    obj = event.get("data", {}).get("object") or {}
    if not isinstance(obj, dict):
        return None
    session_id = _session_id_from_stripe_object(obj)
    if not session_id and etype.startswith("checkout.session"):
        session_id = str(obj.get("id") or "")
    if not session_id:
        pi = _payment_intent_id_from_stripe_object(obj)
        if pi:
            session_id = find_session_id_by_payment_intent(pi)
    # invoice.payment_failed may only have subscription id
    if not session_id and etype == "invoice.payment_failed":
        sub = str(obj.get("subscription") or "")
        if sub:
            session_id = find_session_id_by_subscription(sub)
    if not session_id:
        return None
    if etype == "checkout.session.completed":
        return None
    # Subscription still inside paid period: do not hard-kill on invoice fail —
    # leave usable until valid_until / period end (cancel flow).
    if etype == "invoice.payment_failed":
        ent = get_connect_entitlement(session_id)
        if ent and ent.get("valid_until") and ent.get("connect_allowed"):
            return None
    reason = etype
    if etype in ("charge.refunded", "charge.dispute.created"):
        status = ENTITLEMENT_REVOKED
    else:
        status = ENTITLEMENT_FAILED
    revoke_connect_entitlement(session_id, reason=reason, status=status)
    return session_id


def process_subscription_lifecycle_event(
    event: dict[str, Any], *, now: float | None = None
) -> dict[str, Any] | None:
    """Handle subscription cancel / renew / delete for Connect entitlement.

    - ``customer.subscription.updated`` with cancel_at_period_end or status
      changes: keep **active** until ``current_period_end`` (product remains
      usable through the paid period).
    - ``customer.subscription.deleted``: revoke (end of period or immediate).
    - ``invoice.paid``: renew ``valid_until`` from line period end when present.
    """
    etype = str(event.get("type") or "")
    obj = event.get("data", {}).get("object") or {}
    if not isinstance(obj, dict):
        return None
    t = now if now is not None else time.time()

    if etype == "customer.subscription.deleted":
        sub_id = str(obj.get("id") or "")
        sid = find_session_id_by_subscription(sub_id)
        if not sid:
            # metadata may carry checkout session
            sid = _session_id_from_stripe_object(obj)
        if not sid:
            return None
        revoke_connect_entitlement(
            sid, reason="customer.subscription.deleted", status=ENTITLEMENT_REVOKED, now=t
        )
        return {"action": "revoked", "session_id": sid, "event_type": etype}

    if etype == "customer.subscription.updated":
        sub_id = str(obj.get("id") or "")
        sid = find_session_id_by_subscription(sub_id) or _session_id_from_stripe_object(obj)
        if not sid:
            return None
        # Always store subscription id for later deleted events
        status_sub = str(obj.get("status") or "").strip().lower()
        period_end = obj.get("current_period_end")
        try:
            pe = float(period_end) if period_end is not None else None
        except (TypeError, ValueError):
            pe = None
        cancel_at_end = bool(obj.get("cancel_at_period_end"))
        # Immediate cancel statuses
        if status_sub in ("canceled", "unpaid", "incomplete_expired"):
            # If period still in future and cancel_at_period_end, keep until pe
            if pe is not None and pe > t and cancel_at_end:
                set_entitlement_valid_until(
                    sid, pe, reason="subscription_cancel_at_period_end", now=t
                )
                # ensure subscription_id linked
                activate_connect_entitlement(
                    sid, subscription_id=sub_id, valid_until=pe, now=t
                )
                return {
                    "action": "period_end_scheduled",
                    "session_id": sid,
                    "valid_until": pe,
                    "event_type": etype,
                }
            revoke_connect_entitlement(
                sid, reason=f"subscription_{status_sub}", status=ENTITLEMENT_REVOKED, now=t
            )
            return {"action": "revoked", "session_id": sid, "event_type": etype}
        # Active / past_due / trialing — refresh period end when cancel scheduled
        if pe is not None:
            reason = (
                "subscription_cancel_at_period_end"
                if cancel_at_end
                else "subscription_period_active"
            )
            activate_connect_entitlement(
                sid, subscription_id=sub_id, valid_until=pe, now=t
            )
            set_entitlement_valid_until(sid, pe, reason=reason, now=t)
            return {
                "action": "period_updated",
                "session_id": sid,
                "valid_until": pe,
                "cancel_at_period_end": cancel_at_end,
                "event_type": etype,
            }
        if sub_id:
            activate_connect_entitlement(sid, subscription_id=sub_id, now=t)
        return {"action": "linked", "session_id": sid, "event_type": etype}

    if etype == "invoice.paid":
        sub_id = str(obj.get("subscription") or "")
        sid = find_session_id_by_subscription(sub_id) if sub_id else ""
        if not sid:
            sid = _session_id_from_stripe_object(obj)
        if not sid:
            return None
        # Prefer lines period end
        pe = None
        lines = (obj.get("lines") or {}).get("data") or []
        if isinstance(lines, list) and lines:
            period = lines[0].get("period") or {}
            if isinstance(period, dict) and period.get("end") is not None:
                try:
                    pe = float(period["end"])
                except (TypeError, ValueError):
                    pe = None
        if pe is None and obj.get("period_end") is not None:
            try:
                pe = float(obj["period_end"])
            except (TypeError, ValueError):
                pe = None
        # Fallback: extend by stored billing_interval (month/year) from *now*
        if pe is None:
            ent = get_connect_entitlement(sid)
            iv = BILLING_INTERVAL_MONTH
            if ent:
                iv = normalize_billing_interval(
                    str(ent.get("billing_interval") or BILLING_INTERVAL_MONTH)
                )
            pe = valid_until_for_paid_interval(iv, now=t)
        activate_connect_entitlement(
            sid,
            subscription_id=sub_id,
            valid_until=pe,
            now=t,
        )
        set_entitlement_valid_until(
            sid, pe, reason="invoice_paid_period", now=t
        )
        return {
            "action": "renewed",
            "session_id": sid,
            "valid_until": pe,
            "event_type": etype,
        }
    return None


def mint_download_token(
    *,
    filename: str,
    platform: str,
    session_id: str | None,
    amount_pence: int = PRICE_PENCE,
    currency: str = PRICE_CURRENCY,
    ttl_sec: int = TOKEN_TTL_SEC,
    now: float | None = None,
    purchase_id: str | None = None,
) -> str:
    """Create a time-limited download token bound to a **current catalog** asset.

    Valid for *ttl_sec* (default :data:`TOKEN_TTL_SEC` = 1 hour). The same token
    may be used for multiple downloads until ``expires_at``; usage does not burn it.

    Re-resolves the platform to the live catalog filename so callers cannot mint
    a stale version string. Raises ``ValueError`` if the platform is unknown.

    Assigns a durable :func:`generate_purchase_id` when *purchase_id* is omitted
    (new paid purchase). Pass an existing id when re-issuing a secondary download
    for the same paid purchase. Tester mints pass :data:`TESTER_MONTH_PPI`
    (stored literally; not a paid RPT-PPI).
    """
    plat = (platform or "").strip().lower()
    bound = resolve_paid_grant_filename(plat, metadata_filename=filename)
    if not bound or bound not in catalog_filenames():
        raise ValueError(f"cannot mint grant for unknown platform/package: {platform!r}")
    filename = bound
    platform = plat
    init_db()
    t = now if now is not None else time.time()
    token = secrets.token_urlsafe(32)
    if is_tester_month_ppi(purchase_id):
        pid = TESTER_MONTH_PPI
    else:
        pid = normalize_purchase_id(purchase_id) if purchase_id else ""
        if not pid:
            pid = generate_purchase_id()
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO grants(
                token, filename, platform, session_id, amount_pence, currency,
                created_at, expires_at, used_at, status, purchase_id
            ) VALUES (?,?,?,?,?,?,?,?,NULL,'granted',?)
            """,
            (
                token,
                filename,
                platform,
                session_id or "",
                int(amount_pence),
                currency,
                t,
                t + ttl_sec,
                pid,
            ),
        )
    finally:
        conn.close()
    return token


def purchase_id_for_token(token: str) -> str | None:
    """Return durable purchase_id for a grant token, if stored."""
    tok = (token or "").strip()
    if not tok:
        return None
    init_db()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT purchase_id FROM grants WHERE token = ?", (tok,)
        ).fetchone()
        if row is None:
            return None
        pid = row["purchase_id"] if "purchase_id" in row.keys() else None
        return normalize_purchase_id(str(pid or "")) or None
    finally:
        conn.close()


def find_paid_purchase_by_id(purchase_id: str) -> dict[str, Any] | None:
    """Lookup a **paid** grant lineage by durable purchase identifier.

    Returns the earliest grant row for that id (original paid package binding).
    Used status / consumed tokens still match — reissue mints a new token.
    Unknown or empty ids return None (fail closed).
    """
    pid = normalize_purchase_id(purchase_id)
    if not pid or not pid.startswith("RPT-"):
        return None
    init_db()
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT token, filename, platform, session_id, amount_pence, currency,
                   created_at, expires_at, used_at, status, purchase_id
            FROM grants
            WHERE purchase_id = ?
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (pid,),
        ).fetchone()
        if row is None:
            return None
        # Only full-price paid catalogue grants may reissue
        if int(row["amount_pence"] or 0) != PRICE_PENCE:
            return None
        st = str(row["status"] or "").strip().lower()
        # Rows are created as status=granted; used downloads keep status with used_at set
        if st not in ("granted", "used", "consumed"):
            return None
        return {
            "token": row["token"],
            "filename": row["filename"],
            "platform": row["platform"],
            "session_id": row["session_id"],
            "amount_pence": row["amount_pence"],
            "currency": row["currency"],
            "status": row["status"],
            "used_at": row["used_at"],
            "purchase_id": normalize_purchase_id(str(row["purchase_id"] or "")) or pid,
            "created_at": row["created_at"],
        }
    finally:
        conn.close()


def mint_subscriber_upgrade_download(
    *,
    platform: str,
    keygen: str = "",
    session_id: str = "",
    now: float | None = None,
    base_url: str | None = None,
    ttl_sec: int = TOKEN_TTL_SEC,
) -> dict[str, Any]:
    """Mint a time-limited monopin installer grant for an **active** subscriber.

    Used by the in-app "Get update" CTA so an entitled customer downloads the
    current catalog package for their device **without** going through Stripe
    Checkout again. Requires an active connect entitlement (keygen and/or
    session_id). Returns absolute ``download_url`` to ``/download?token=…`` so
    the browser/OS starts retrieving the installer immediately.

    Raises ``ValueError`` for unknown platform, missing credentials, or
    inactive/expired entitlement.
    """
    plat = (platform or "").strip().lower()
    fname = platform_filename(plat)
    if not fname:
        raise ValueError(f"unknown platform: {platform!r}")
    kg = normalize_keygen(keygen) if keygen else ""
    sid = (session_id or "").strip()
    ent: dict[str, Any] | None = None
    if kg:
        ent = get_connect_entitlement_by_keygen(kg, now=now)
    elif sid:
        ent = get_connect_entitlement(sid, now=now)
    else:
        raise ValueError("missing_keygen_or_session_id")
    if not ent or not ent.get("connect_allowed"):
        raise ValueError("entitlement_not_active")
    # Prefer bound session from entitlement for grant lineage
    bound_sid = str(ent.get("session_id") or sid or f"upgrade_{secrets.token_hex(8)}")
    # Prefer purchase lineage when present on prior grants for this session
    purchase_id = ""
    try:
        init_db()
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT purchase_id FROM grants
                WHERE session_id = ? AND purchase_id IS NOT NULL AND purchase_id != ''
                ORDER BY created_at DESC LIMIT 1
                """,
                (bound_sid,),
            ).fetchone()
            if row is not None:
                purchase_id = normalize_purchase_id(str(row["purchase_id"] or "")) or ""
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        purchase_id = ""
    token = mint_download_token(
        filename=fname,
        platform=plat,
        session_id=bound_sid,
        amount_pence=PRICE_PENCE,
        currency=PRICE_CURRENCY,
        ttl_sec=ttl_sec,
        now=now,
        purchase_id=purchase_id or None,
    )
    path = f"/download?token={token}"
    base = (base_url if base_url is not None else public_base_url()).rstrip("/")
    url = f"{base}{path}"
    if "github.com" in url.lower() and "releases/download" in url.lower():
        raise RuntimeError("refusing free GitHub release URL from subscriber upgrade mint")
    return {
        "ok": True,
        "token": token,
        "download_path": path,
        "download_url": url,
        "platform": plat,
        "filename": fname,
        "session_id": bound_sid,
        "keygen": str(ent.get("keygen") or kg or ""),
        "subscriber_upgrade": True,
        "catalog_version": fname.split("-")[3] if fname.count("-") >= 3 else "",
    }


def admin_mint_download_for_platform(
    platform: str,
    *,
    now: float | None = None,
    base_url: str | None = None,
    ttl_sec: int = TOKEN_TTL_SEC,
) -> dict[str, Any]:
    """Admin failsafe: mint a live time-limited download for a catalog platform.

    Does **not** require an RPT product purchase identifier. Intended for
    authenticated operators only (enforced at the HTTP layer). Creates a
    normal paid grant row so ``/download?token=`` works; does **not** emit free
    permanent GitHub installer URLs.

    Unlike customer RPT-PPI reissue, this is a silent failsafe mint — no
    durable customer-recovery audit log is written here.
    """
    plat = (platform or "").strip().lower()
    fname = platform_filename(plat)
    if not fname:
        raise ValueError(f"unknown platform: {platform!r}")
    # Distinct session prefix so grants are not confused with Stripe sessions
    session_id = f"admin_ondemand_{secrets.token_hex(8)}"
    token = mint_download_token(
        filename=fname,
        platform=plat,
        session_id=session_id,
        amount_pence=PRICE_PENCE,
        currency=PRICE_CURRENCY,
        ttl_sec=ttl_sec,
        now=now,
    )
    path = f"/download?token={token}"
    base = (base_url if base_url is not None else public_base_url()).rstrip("/")
    url = f"{base}{path}"
    if "github.com" in url.lower() and "releases/download" in url.lower():
        raise RuntimeError("refusing free GitHub release URL from admin_mint_download_for_platform")
    pid = purchase_id_for_token(token) or ""
    return {
        "token": token,
        "download_path": path,
        "download_url": url,
        "platform": plat,
        "filename": fname,
        "session_id": session_id,
        "purchase_id": pid,  # present in DB; not required to mint
        "admin_ondemand": True,
        "amount_pence": PRICE_PENCE,
    }


def admin_mint_keygen_failsafe(
    *,
    platform: str = "",
    note: str = "",
    now: float | None = None,
) -> dict[str, Any]:
    """Admin failsafe: mint a fresh active KEYGEN for licence unlock recovery.

    For operators helping customers who still need Connect unlock but lost their
    emailed keygen. Creates a **new** admin-prefixed entitlement session with a
    unique ``RPT-KEY-…`` code; does **not** require Stripe checkout or the lost
    code. Operator-only (HTTP layer enforces auth). Not a public free unlock.

    Returns ``keygen``, ``session_id``, optional ``platform`` / ``note``, and
    ``admin_keygen_failsafe: True``.
    """
    t = now if now is not None else time.time()
    plat = (platform or "").strip().lower()
    if plat and not platform_filename(plat):
        raise ValueError(f"unknown platform: {platform!r}")
    # Distinct session prefix so failsafe mints are not confused with Stripe sessions
    session_id = f"admin_keygen_{secrets.token_hex(10)}"
    note_clean = (note or "").strip()[:200]
    reason_note = "admin_keygen_failsafe"
    if note_clean:
        reason_note = f"admin_keygen_failsafe:{note_clean}"[:200]
    keygen = activate_connect_entitlement(
        session_id,
        platform=plat,
        payment_intent_id="",
        subscription_id="",
        valid_until=None,
        keygen=None,
        now=t,
    )
    kg = normalize_keygen(keygen)
    if not kg or not kg.startswith(KEYGEN_PREFIX):
        raise RuntimeError("admin_mint_keygen_failsafe failed to mint product keygen")
    # Stamp operator reason (activate uses payment_succeeded; overwrite for audit-ish clarity)
    conn = _connect()
    try:
        conn.execute(
            "UPDATE connect_entitlements SET reason = ?, updated_at = ? WHERE session_id = ?",
            (reason_note, t, session_id),
        )
    finally:
        conn.close()
    # Failsafe: verify via session (not by-keygen) so mint does not auto-activate
    # for licence-list gating (activation is client-path only).
    ent = get_connect_entitlement(session_id, now=t)
    if not ent or not ent.get("connect_allowed"):
        raise RuntimeError("admin failsafe keygen not active after mint")
    return {
        "keygen": kg,
        "session_id": session_id,
        "platform": plat,
        "note": note_clean,
        "status": str(ent.get("status") or ENTITLEMENT_ACTIVE),
        "connect_allowed": True,
        "admin_keygen_failsafe": True,
        "unlock_instruction": KEYGEN_UNLOCK_INSTRUCTION,
    }


def admin_mint_one_month_tester(
    platform: str,
    *,
    now: float | None = None,
    base_url: str | None = None,
    ttl_sec: int = TOKEN_TTL_SEC,
) -> dict[str, Any]:
    """Admin: mint a **one-month free tester** subscription for a catalog platform.

    Returns both a status-host time-limited **download link** and a product
    **keygen**, with PPI label :data:`TESTER_MONTH_PPI`. Entitlement
    ``valid_until`` is one calendar month after *now* (same helper as paid
    monthly). Download token exists for ``/download?token=`` fulfilment but is
    **excluded** from the admin Paid download grants list (paid customers only).
    Licence database lists the row only after first successful client keygen
    activation (:func:`get_connect_entitlement_by_keygen`).

    Operator-only (HTTP layer enforces auth). Not a free permanent GitHub URL.
    """
    t = float(now if now is not None else time.time())
    plat = (platform or "").strip().lower()
    fname = platform_filename(plat)
    if not fname:
        raise ValueError(f"unknown platform: {platform!r}")
    session_id = f"{TESTER_MONTH_SESSION_PREFIX}{secrets.token_hex(10)}"
    valid_until = period_end_for_billing_interval(t, BILLING_INTERVAL_MONTH)
    keygen = activate_connect_entitlement(
        session_id,
        platform=plat,
        payment_intent_id="",
        subscription_id="",
        valid_until=valid_until,
        keygen=None,
        billing_interval=BILLING_INTERVAL_MONTH,
        now=t,
    )
    kg = normalize_keygen(keygen)
    if not kg or not kg.startswith(KEYGEN_PREFIX):
        raise RuntimeError("admin_mint_one_month_tester failed to mint product keygen")
    conn = _connect()
    try:
        conn.execute(
            "UPDATE connect_entitlements SET reason = ?, updated_at = ? WHERE session_id = ?",
            (TESTER_MONTH_REASON, t, session_id),
        )
    finally:
        conn.close()
    token = mint_download_token(
        filename=fname,
        platform=plat,
        session_id=session_id,
        amount_pence=0,
        currency=PRICE_CURRENCY,
        ttl_sec=ttl_sec,
        now=t,
        purchase_id=TESTER_MONTH_PPI,
    )
    path = f"/download?token={token}"
    base = (base_url if base_url is not None else public_base_url()).rstrip("/")
    url = f"{base}{path}"
    if "github.com" in url.lower() and "releases/download" in url.lower():
        raise RuntimeError(
            "refusing free GitHub release URL from admin_mint_one_month_tester"
        )
    ent = get_connect_entitlement(session_id, now=t)
    if not ent or not ent.get("connect_allowed"):
        raise RuntimeError("tester entitlement not active after mint")
    return {
        "token": token,
        "download_path": path,
        "download_url": url,
        "platform": plat,
        "filename": fname,
        "session_id": session_id,
        "keygen": kg,
        "purchase_id": TESTER_MONTH_PPI,
        "ppi": TESTER_MONTH_PPI,
        "valid_until": float(ent.get("valid_until") or valid_until),
        "billing_interval": BILLING_INTERVAL_MONTH,
        "status": str(ent.get("status") or ENTITLEMENT_ACTIVE),
        "connect_allowed": True,
        "admin_tester_month": True,
        "unlock_instruction": KEYGEN_UNLOCK_INSTRUCTION,
        "amount_pence": 0,
    }


def seed_test_purchase_enabled() -> bool:
    """True only when operator explicitly opts into local/staging seed tools.

    Requires ``RPT_ADMIN_SEED_PURCHASE=1`` (or ``true``/``yes``/``on``).
    Never on by default — production must set the env deliberately.
    Seeded grants still require a time-limited ``/download?token=`` (no free unlock).
    """
    return os.environ.get("RPT_ADMIN_SEED_PURCHASE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def seed_test_purchase(
    platform: str = "windows",
    *,
    now: float | None = None,
    base_url: str | None = None,
    ttl_sec: int = TOKEN_TTL_SEC,
) -> dict[str, Any]:
    """Mint a **paid** test grant (full price) for admin reissue / recovery tests.

    Creates a durable product purchase identifier + time-limited download token for
    a catalog platform. Does **not** expose free permanent GitHub installer URLs.

    Raises ``ValueError`` if seeding is disabled or the platform is unknown.
    """
    if not seed_test_purchase_enabled():
        raise ValueError(
            "seed_test_purchase disabled — set RPT_ADMIN_SEED_PURCHASE=1 for local/staging only"
        )
    plat = (platform or "").strip().lower() or "windows"
    fname = platform_filename(plat)
    if not fname:
        raise ValueError(f"unknown platform for seed: {platform!r}")
    session_id = f"seed_test_{secrets.token_hex(8)}"
    token = mint_download_token(
        filename=fname,
        platform=plat,
        session_id=session_id,
        amount_pence=PRICE_PENCE,
        currency=PRICE_CURRENCY,
        ttl_sec=ttl_sec,
        now=now,
    )
    pid = purchase_id_for_token(token) or ""
    path = f"/download?token={token}"
    base = (base_url if base_url is not None else public_base_url()).rstrip("/")
    url = f"{base}{path}"
    if "github.com" in url.lower() and "releases/download" in url.lower():
        raise RuntimeError("refusing free GitHub release URL from seed_test_purchase")
    return {
        "purchase_id": pid,
        "token": token,
        "download_path": path,
        "download_url": url,
        "platform": plat,
        "filename": fname,
        "session_id": session_id,
        "seed": True,
        "amount_pence": PRICE_PENCE,
    }


def reissue_download_for_purchase_id(
    purchase_id: str,
    *,
    ttl_sec: int = TOKEN_TTL_SEC,
    now: float | None = None,
    base_url: str | None = None,
) -> dict[str, Any] | None:
    """Mint a **new** time-limited download token for a paid purchase_id.

    Returns dict with ``token``, ``download_path``, ``download_url``,
    ``purchase_id``, ``platform``, ``filename`` — or **None** if unknown/unpaid.
    Never returns free permanent GitHub installer URLs.
    """
    original = find_paid_purchase_by_id(purchase_id)
    if original is None:
        return None
    pid = str(original["purchase_id"])
    token = mint_download_token(
        filename=str(original["filename"]),
        platform=str(original["platform"]),
        session_id=str(original.get("session_id") or ""),
        amount_pence=int(original.get("amount_pence") or PRICE_PENCE),
        currency=str(original.get("currency") or PRICE_CURRENCY),
        ttl_sec=ttl_sec,
        now=now,
        purchase_id=pid,
    )
    path = f"/download?token={token}"
    base = (base_url if base_url is not None else public_base_url()).rstrip("/")
    return {
        "token": token,
        "download_path": path,
        "download_url": f"{base}{path}",
        "purchase_id": pid,
        "platform": original["platform"],
        "filename": original["filename"],
        "session_id": original.get("session_id") or "",
    }


def _grant_dict_from_row(row: sqlite3.Row) -> dict[str, Any]:
    keys = set(row.keys())
    pid = ""
    if "purchase_id" in keys and row["purchase_id"]:
        pid = normalize_purchase_id(str(row["purchase_id"])) or str(row["purchase_id"])
    stored = str(row["filename"] or "")
    plat = str(row["platform"] or "")
    # Delivery always rebinds to live catalog for known platforms
    live = grant_delivery_filename(platform=plat, stored_filename=stored) or stored
    return {
        "token": row["token"],
        "filename": live,
        "stored_filename": stored,
        "platform": row["platform"],
        "session_id": row["session_id"],
        "amount_pence": row["amount_pence"],
        "currency": row["currency"],
        "url": asset_download_url(live),
        "purchase_id": pid,
        "download_path": f"/download?token={row['token']}",
    }


def lookup_download_token(
    token: str, *, now: float | None = None
) -> dict[str, Any] | None:
    """Return grant if valid and non-expired — **does not** mark used.

    Time-window only (default 1 hour from mint). Prior downloads (``used_at``)
    do **not** invalidate the token while ``expires_at`` is still in the future.
    Revoked/unknown/expired tokens return ``None``.

    Use before opening the installer. Call :func:`consume_download_token` after a
    successful stream for **audit** (last-used timestamp); it does not gate reuse.

    ``filename`` is the **current catalog** package for the grant platform (never
    a stale pin still sitting in the SQLite row).
    """
    init_db()
    t = now if now is not None else time.time()
    tok = (token or "").strip()
    if not tok:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM grants WHERE token = ?", (tok,)
        ).fetchone()
        if row is None:
            return None
        st = str(row["status"] or "").strip().lower()
        # granted = fresh; used = downloaded at least once (still valid until expiry)
        if st not in ("granted", "used"):
            return None
        if float(row["expires_at"]) < t:
            return None
        d = _grant_dict_from_row(row)
        # Fail closed if we cannot deliver a current-catalog name
        if not _safe_catalog_filename(str(d.get("filename") or "")):
            return None
        return d
    finally:
        conn.close()


def consume_download_token(token: str, *, now: float | None = None) -> bool:
    """Record a download use for audit (``used_at`` / status).

    Does **not** invalidate the grant within its TTL — the same token remains
    redeemable until ``expires_at``. Returns True if the token is still within
    its validity window and the audit stamp was written.
    """
    init_db()
    t = now if now is not None else time.time()
    tok = (token or "").strip()
    if not tok:
        return False
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT status, used_at, expires_at FROM grants WHERE token = ?",
            (tok,),
        ).fetchone()
        if row is None:
            return False
        st = str(row["status"] or "").strip().lower()
        if st not in ("granted", "used"):
            return False
        if float(row["expires_at"]) < t:
            return False
        cur = conn.execute(
            "UPDATE grants SET used_at = ?, status = 'used' "
            "WHERE token = ? AND status IN ('granted', 'used')",
            (t, tok),
        )
        return cur.rowcount == 1
    finally:
        conn.close()


def redeem_download_token(
    token: str, *, now: float | None = None
) -> dict[str, Any] | None:
    """Lookup + audit-stamp in one step (helpers / tests).

    Within the TTL window this may succeed on **every** call (time-limited reuse).
    HTTP /download should use :func:`lookup_download_token` then
    :func:`consume_download_token` after a successful stream for audit only.
    """
    grant = lookup_download_token(token, now=now)
    if grant is None:
        return None
    if not consume_download_token(token, now=now):
        return None
    return grant


def _probe_vps_fetch_error() -> str | None:
    """Best-effort VPS connectivity diagnostic (no secret material)."""
    vps_token = vps_asset_fetch_token()
    if not vps_token:
        return "token_missing"
    assets = list(available_downloads())
    if not assets:
        return "empty_catalog"
    filename = assets[0].filename
    try:
        vps_url = vps_asset_url(filename)
        headers = {
            "User-Agent": "restore-privacy-status-fulfilment-probe",
            "X-RPT-Asset-Token": vps_token,
        }
        req = urllib.request.Request(vps_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=20) as resp:
            # Read nothing — headers only prove reachability
            code = getattr(resp, "status", 200)
            if int(code) >= 400:
                return f"http_{code}"
            return None
    except urllib.error.HTTPError as e:
        return f"http_{e.code}"
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        return f"urlerror:{type(reason).__name__}:{reason}"[:160]
    except TimeoutError:
        return "timeout"
    except OSError as e:
        return f"oserror:{type(e).__name__}"[:120]
    except Exception as e:  # noqa: BLE001
        return f"error:{type(e).__name__}"[:120]


def check_fulfilment_ready(
    *,
    platform: str | None = None,
    smtp_probe: bool = False,
) -> dict[str, Any]:
    """Probe that at least one catalog installer is openable (local or API).

    Closes the body immediately — used for production readiness evidence.
    Includes non-secret flags so operators can confirm VPS token match without
    printing the secret (``vps_token_configured``).

    When *platform* is set (e.g. ``macos``), only that catalog package is probed
    so live-test evidence can pin the paid macOS zip.

    When *smtp_probe* is True, attempts real SMTP connect+login (no mail sent)
    and attaches ``smtp_probe`` result for operator evidence.
    """
    vps_tok = bool(vps_asset_fetch_token())
    vps_base = vps_asset_base_url()
    smtp_ready = assess_fulfilment_smtp_readiness()
    meta: dict[str, Any] = {
        "vps_token_configured": vps_tok,
        "vps_asset_base": vps_base,
        "github_token_configured": bool(github_auth_token()),
        # Non-secret: why keygen receipt email may skip after purchase
        "email_flow_enabled": bool(smtp_ready.get("email_flow_enabled")),
        "smtp_status": smtp_ready.get("status"),
        "smtp_detail": smtp_ready.get("detail"),
        "smtp_missing": list(smtp_ready.get("missing_or_empty") or []),
    }
    if smtp_probe:
        meta["smtp_probe"] = probe_fulfilment_smtp_login()
    elif smtp_ready.get("email_flow_enabled"):
        # Config looks complete; only ?smtp_probe=1 proves provider login
        meta["smtp_login_unverified"] = True
        meta["smtp_probe_hint"] = "GET /health/fulfilment?smtp_probe=1"
    assets = list(available_downloads())
    want = (platform or "").strip().lower()
    if want:
        filtered = [a for a in assets if a.platform == want]
        if filtered:
            assets = filtered
        meta["probe_platform"] = want
    else:
        # Prefer macOS first for default probe (primary live-test package)
        assets = sorted(assets, key=lambda a: 0 if a.platform == "macos" else 1)
    for asset in assets:
        opened = open_release_asset(asset.filename)
        if opened is None:
            continue
        body = opened.get("body")
        try:
            if hasattr(body, "close"):
                body.close()
        except Exception:  # noqa: BLE001
            pass
        out = {
            "ok": True,
            "source": opened.get("source"),
            "probe_filename": asset.filename,
            "content_length": opened.get("content_length"),
            "probe_platform": asset.platform,
        }
        out.update(meta)
        return out
    if vps_tok:
        probe_err = _probe_vps_fetch_error()
        if probe_err:
            meta["vps_fetch_error"] = probe_err
    out = {
        "ok": False,
        "error": "no_asset_source",
        "hint": (
            "Set RPT_ASSET_FETCH_TOKEN + host installers on Helsinki store "
            "(scripts/host_paid_assets_vps.py), or stage status_page/assets/{version}/, "
            "or set RPT_GITHUB_TOKEN for private GitHub Release assets"
        ),
    }
    out.update(meta)
    return out


def list_recent_grants(limit: int | None = 50) -> list[dict[str, Any]]:
    """List grants newest-first from the shipped store.

    *limit* caps the row count when a positive int. Pass ``limit=None`` for the
    **full** completed-payment grant history (authenticated admin list). Used
    tokens remain in the store and are returned with status/used_at set.

    **Excludes** one-month tester mints (session ``tester_month_*`` / PPI
    :data:`TESTER_MONTH_PPI`) — Paid download grants UI is for paid customers
    only. Tester download tokens remain redeemable via ``/download?token=``.
    """
    init_db()
    conn = _connect()
    try:
        sql = """
            SELECT g.token, g.filename, g.platform, g.session_id, g.amount_pence,
                   g.currency, g.created_at, g.expires_at, g.used_at, g.status,
                   g.purchase_id,
                   e.valid_until AS entitlement_valid_until,
                   e.created_at AS entitlement_created_at,
                   e.status AS entitlement_status
            FROM grants g
            LEFT JOIN connect_entitlements e ON e.session_id = g.session_id
            ORDER BY g.created_at DESC
        """
        # Fetch all matching rows then filter tester; apply limit after filter so
        # paid grants are not starved by intermixed tester rows.
        t_now = time.time()
        rows = conn.execute(sql).fetchall()
        out = []
        for r in rows:
            d = {k: r[k] for k in r.keys()}
            if d.get("purchase_id"):
                raw_pid = str(d["purchase_id"])
                if is_tester_month_ppi(raw_pid):
                    d["purchase_id"] = TESTER_MONTH_PPI
                else:
                    d["purchase_id"] = (
                        normalize_purchase_id(raw_pid) or raw_pid
                    )
            if is_tester_month_grant(d):
                continue
            # Licence period from entitlement when present
            try:
                vu_f = (
                    float(d["entitlement_valid_until"])
                    if d.get("entitlement_valid_until") is not None
                    else None
                )
            except (TypeError, ValueError):
                vu_f = None
            try:
                init_f = (
                    float(d["entitlement_created_at"])
                    if d.get("entitlement_created_at") is not None
                    else float(d["created_at"]) if d.get("created_at") is not None else None
                )
            except (TypeError, ValueError):
                init_f = None
            ent_st = str(d.get("entitlement_status") or "")
            connect_ok = (
                _entitlement_connect_allowed(ent_st, vu_f, now=t_now)
                if ent_st
                else (vu_f is None or vu_f > t_now)
            )
            raw_status = str(d.get("status") or "")
            if not connect_ok or (
                vu_f is not None and vu_f <= t_now
            ) or ent_st in (ENTITLEMENT_REVOKED, ENTITLEMENT_FAILED):
                display_status = "ENDED"
            elif d.get("used_at") is not None:
                display_status = "used"
            else:
                display_status = raw_status or "granted"
            d["initiated_at"] = init_f
            d["initiated_date"] = format_admin_unix_date(init_f)
            d["expiry_at"] = vu_f
            d["expiry_date"] = format_admin_unix_date(vu_f)
            d["valid_until"] = vu_f
            d["display_status"] = display_status
            d["status"] = display_status
            out.append(d)
            if limit is not None and len(out) >= max(0, int(limit)):
                break
        return out
    finally:
        conn.close()


def list_all_grants() -> list[dict[str, Any]]:
    """Full **paid** grant history for operator admin (tester mints excluded)."""
    return list_recent_grants(limit=None)


def format_admin_unix_date(ts: float | None) -> str:
    """UTC calendar date ``YYYY-MM-DD`` for admin tables; empty if unknown."""
    if ts is None:
        return ""
    try:
        f = float(ts)
    except (TypeError, ValueError):
        return ""
    if f <= 0:
        return ""
    try:
        return datetime.fromtimestamp(f, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return ""


def admin_licence_display_status(
    *,
    connect_allowed: bool,
    licence_status: str = "",
) -> str:
    """Admin list status: ``OK`` while Connect allowed, else ``ENDED``."""
    if connect_allowed or str(licence_status or "").upper() == LICENCE_STATUS_OK:
        return "OK"
    return "ENDED"


def list_licences_for_admin(*, limit: int | None = None) -> list[dict[str, Any]]:
    """Read-only licence rows for admin: email, KEYGEN, PPI, OK|ENDED + dates.

    Joins connect_entitlements with grants (purchase_id). Info only — no write.

    One-month **tester** entitlements appear only after first successful
    keygen activation (``keygen_activated_at`` set by
    :func:`get_connect_entitlement_by_keygen`). Unused tester keys stay hidden.

    Expired / revoked rows remain listed with status **ENDED** (not hidden).
    """
    init_db()
    t = time.time()
    conn = _connect()
    try:
        sql = """
            SELECT e.session_id, e.status, e.platform, e.keygen, e.customer_email,
                   e.billing_interval, e.valid_until, e.updated_at, e.created_at,
                   e.keygen_activated_at,
                   (SELECT g.purchase_id FROM grants g
                    WHERE g.session_id = e.session_id
                    ORDER BY g.created_at DESC LIMIT 1) AS purchase_id
            FROM connect_entitlements e
            ORDER BY e.updated_at DESC
        """
        rows = conn.execute(sql).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            sid = str(r["session_id"] or "")
            try:
                activated_at = r["keygen_activated_at"]
            except (KeyError, IndexError, TypeError):
                activated_at = None
            # Tester: licence list only after keygen activation.
            if is_tester_month_session(sid):
                if activated_at is None or float(activated_at or 0) <= 0:
                    continue
            vu = r["valid_until"]
            try:
                vu_f = float(vu) if vu is not None else None
            except (TypeError, ValueError):
                vu_f = None
            try:
                created_f = float(r["created_at"]) if r["created_at"] is not None else None
            except (TypeError, ValueError, KeyError, IndexError):
                created_f = None
            status = str(r["status"] or "")
            connect_ok = _entitlement_connect_allowed(status, vu_f, now=t)
            kg = normalize_keygen(str(r["keygen"] or ""))
            pid = ""
            if r["purchase_id"]:
                raw_pid = str(r["purchase_id"])
                if is_tester_month_ppi(raw_pid) or is_tester_month_session(sid):
                    pid = TESTER_MONTH_PPI
                else:
                    pid = normalize_purchase_id(raw_pid) or raw_pid
            elif is_tester_month_session(sid):
                pid = TESTER_MONTH_PPI
            ent = {
                "session_id": sid,
                "status": status,
                "connect_allowed": connect_ok,
                "valid_until": vu_f,
                "keygen": kg,
            }
            raw_ls = licence_status_from_entitlement(ent, now=t)
            display = admin_licence_display_status(
                connect_allowed=connect_ok, licence_status=raw_ls
            )
            out.append(
                {
                    "email": str(r["customer_email"] or "").strip(),
                    "keygen": kg,
                    "purchase_id": pid,
                    "ppi": pid,
                    "licence_status": display,
                    "licence_status_raw": raw_ls,
                    "platform": str(r["platform"] or ""),
                    "billing_interval": str(r["billing_interval"] or "")
                    or BILLING_INTERVAL_MONTH,
                    "session_id": sid,
                    "status_raw": status,
                    "updated_at": r["updated_at"],
                    "created_at": created_f,
                    "initiated_at": created_f,
                    "initiated_date": format_admin_unix_date(created_f),
                    "expiry_at": vu_f,
                    "expiry_date": format_admin_unix_date(vu_f),
                    "valid_until": vu_f,
                    "keygen_activated_at": (
                        float(activated_at) if activated_at is not None else None
                    ),
                }
            )
            if limit is not None and len(out) >= max(0, int(limit)):
                break
        return out
    finally:
        conn.close()


# Explicit confirm token required by clear_all_licences_for_admin (no silent wipe).
CLEAR_ALL_LICENCES_CONFIRM = "CLEAR_ALL_LICENCES"


def clear_all_licences_for_admin(
    *,
    confirm: str,
    now: float | None = None,
) -> dict[str, Any]:
    """Delete all Connect licence rows so admin Licence database is empty.

    Intended for pre-BETA operator cleanup of self-test rows. Requires
    ``confirm == CLEAR_ALL_LICENCES_CONFIRM`` — refuses otherwise (no silent wipe).

    Removes every row from ``connect_entitlements`` and ``device_entitlements``
    so KEYGEN / device bindings cannot keep Connect live. Does **not** delete
    paid download ``grants`` history (separate admin table).

    Returns counts deleted and the durable DB path used.
    """
    if (confirm or "").strip() != CLEAR_ALL_LICENCES_CONFIRM:
        raise ValueError(
            "clear_all_licences_for_admin refused: confirm must be "
            f"{CLEAR_ALL_LICENCES_CONFIRM!r} (got {confirm!r})"
        )
    init_db()
    t = now if now is not None else time.time()
    path = db_path()
    conn = _connect()
    try:
        n_ent = int(
            conn.execute("SELECT COUNT(*) FROM connect_entitlements").fetchone()[0]
        )
        n_dev = int(
            conn.execute("SELECT COUNT(*) FROM device_entitlements").fetchone()[0]
        )
        conn.execute("DELETE FROM device_entitlements")
        conn.execute("DELETE FROM connect_entitlements")
        remaining_ent = int(
            conn.execute("SELECT COUNT(*) FROM connect_entitlements").fetchone()[0]
        )
        remaining_dev = int(
            conn.execute("SELECT COUNT(*) FROM device_entitlements").fetchone()[0]
        )
    finally:
        conn.close()
    return {
        "ok": True,
        "confirm": CLEAR_ALL_LICENCES_CONFIRM,
        "db_path": str(path),
        "deleted_connect_entitlements": n_ent,
        "deleted_device_entitlements": n_dev,
        "remaining_connect_entitlements": remaining_ent,
        "remaining_device_entitlements": remaining_dev,
        "cleared_at": t,
    }


# Explicit confirm token for clear_all_grants_for_admin (no silent wipe).
CLEAR_ALL_GRANTS_CONFIRM = "CLEAR_ALL_GRANTS"


def clear_all_grants_for_admin(
    *,
    confirm: str,
    now: float | None = None,
) -> dict[str, Any]:
    """Delete all paid download grant rows so admin grants table is empty.

    Pre-BETA operator cleanup of self-test download tokens/history. Requires
    ``confirm == CLEAR_ALL_GRANTS_CONFIRM`` — refuses otherwise.

    Deletes every row from ``grants`` only. Does **not** touch
    ``connect_entitlements`` / licences (use :func:`clear_all_licences_for_admin`).

    Returns counts deleted and the durable DB path used.
    """
    if (confirm or "").strip() != CLEAR_ALL_GRANTS_CONFIRM:
        raise ValueError(
            "clear_all_grants_for_admin refused: confirm must be "
            f"{CLEAR_ALL_GRANTS_CONFIRM!r} (got {confirm!r})"
        )
    init_db()
    t = now if now is not None else time.time()
    path = db_path()
    conn = _connect()
    try:
        n_g = int(conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0])
        conn.execute("DELETE FROM grants")
        remaining = int(conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0])
    finally:
        conn.close()
    return {
        "ok": True,
        "confirm": CLEAR_ALL_GRANTS_CONFIRM,
        "db_path": str(path),
        "deleted_grants": n_g,
        "remaining_grants": remaining,
        "cleared_at": t,
    }


def find_grant_by_session(
    session_id: str, *, now: float | None = None, unused_only: bool = True
) -> dict[str, Any] | None:
    """Map Stripe Checkout session id → grant (token + filename), if present.

    Does **not** mark the token used — that happens on /download redeem.
    """
    sid = (session_id or "").strip()
    if not sid:
        return None
    init_db()
    t = now if now is not None else time.time()
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT token, filename, platform, session_id, amount_pence, currency,
                   created_at, expires_at, used_at, status, purchase_id
            FROM grants WHERE session_id = ? ORDER BY created_at DESC LIMIT 1
            """,
            (sid,),
        ).fetchone()
        if row is None:
            return None
        if float(row["expires_at"]) < t:
            return None
        if unused_only and (row["status"] != "granted" or row["used_at"] is not None):
            return None
        pid = ""
        if "purchase_id" in row.keys() and row["purchase_id"]:
            pid = normalize_purchase_id(str(row["purchase_id"])) or str(row["purchase_id"])
        return {
            "token": row["token"],
            "filename": row["filename"],
            "platform": row["platform"],
            "session_id": row["session_id"],
            "amount_pence": row["amount_pence"],
            "currency": row["currency"],
            "status": row["status"],
            "used_at": row["used_at"],
            "purchase_id": pid,
            "download_path": f"/download?token={row['token']}",
            "url": asset_download_url(row["filename"]),
        }
    finally:
        conn.close()


def wait_for_grant_by_session(
    session_id: str,
    *,
    timeout_sec: float = 8.0,
    interval_sec: float = 0.25,
    now: float | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> dict[str, Any] | None:
    """Poll for webhook-minted grant after Checkout redirect (race-friendly)."""
    sleeper = sleep_fn or time.sleep
    start = time.time() if now is None else float(now)
    deadline = start + max(0.0, timeout_sec)
    while True:
        grant = find_grant_by_session(session_id, now=now)
        if grant is not None:
            return grant
        tcur = time.time() if now is None else float(now)
        if tcur >= deadline:
            return None
        sleeper(interval_sec)


HttpGetFn = Callable[[str, dict[str, str]], tuple[int, bytes]]


def _default_http_get(url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return int(resp.status), resp.read()
    except urllib.error.HTTPError as e:
        return int(e.code), e.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, b""


def retrieve_checkout_session(
    session_id: str,
    *,
    http_get: HttpGetFn | None = None,
    secret_key: str | None = None,
) -> dict[str, Any] | None:
    """GET Checkout Session from Stripe (server-side recovery when webhook lags).

    Returns the session object dict, or None on missing config / API failure.
    """
    sid = (session_id or "").strip()
    if not sid.startswith("cs_"):
        return None
    key = (secret_key if secret_key is not None else stripe_secret_key()).strip()
    if not key:
        return None
    url = (
        "https://api.stripe.com/v1/checkout/sessions/"
        + urllib.parse.quote(sid, safe="")
    )
    getter = http_get or _default_http_get
    status, raw = getter(url, {"Authorization": f"Bearer {key}"})
    if status != 200 or not raw:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def ensure_download_grant_for_paid_session(
    session_id: str,
    *,
    platform_hint: str = "",
    http_get: HttpGetFn | None = None,
    secret_key: str | None = None,
) -> dict[str, Any] | None:
    """If webhook missed, verify payment with Stripe and mint a download grant.

    Uses the live Checkout Session (payment_status, amount_total, client_reference_id).
    Optional *platform_hint* fills empty client_reference_id only after Stripe
    confirms the session is paid (never trusts the browser alone).
    """
    sid = (session_id or "").strip()
    if not sid:
        return None
    existing = find_grant_by_session(sid, unused_only=True)
    if existing is not None:
        return existing
    sess = retrieve_checkout_session(
        sid, http_get=http_get, secret_key=secret_key
    )
    if not sess:
        return None
    # Prefer Stripe client_reference_id / metadata; fall back to hint after paid path
    plat = platform_from_stripe_checkout_session(sess)
    hint = (platform_hint or "").strip().lower()
    if not plat and hint and platform_filename(hint):
        sess = dict(sess)
        sess["client_reference_id"] = hint
        meta = sess.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
        else:
            meta = dict(meta)
        meta.setdefault("platform", hint)
        sess["metadata"] = meta
    event = {"type": "checkout.session.completed", "data": {"object": sess}}
    token = process_checkout_completed_event(event)
    if not token:
        return None
    return find_grant_by_session(sid, unused_only=True)


def paid_session_needs_platform_picker(
    session_id: str,
    *,
    http_get: HttpGetFn | None = None,
    secret_key: str | None = None,
) -> bool:
    """True when Stripe shows paid but no platform is bound (picker UI)."""
    sess = retrieve_checkout_session(
        session_id, http_get=http_get, secret_key=secret_key
    )
    if not sess:
        return False
    payment_status = str(sess.get("payment_status") or "").strip().lower()
    if payment_status not in ("paid", "no_payment_required"):
        return False
    if platform_from_stripe_checkout_session(sess):
        return False
    return True


# --- Stripe Checkout (stdlib HTTP) -----------------------------------------------


HttpPostFn = Callable[[str, dict[str, str], bytes], tuple[int, bytes]]


def _default_http_post(
    url: str, headers: dict[str, str], body: bytes
) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return int(resp.status), resp.read()
    except urllib.error.HTTPError as e:
        return int(e.code), e.read()


def build_subscription_checkout_form_body(
    platform: str,
    filename: str,
    *,
    interval: str = BILLING_INTERVAL_MONTH,
    success_url: str,
    cancel_url: str,
    currency: str = PRICE_CURRENCY,
    auto_renew: bool = True,
) -> bytes:
    """Stripe Checkout Session body for **subscription** Monthly/Yearly VPN plan.

    Uses Dashboard Price ids for Monthly VPN plan / Yearly VPN plan. No trial.
    *currency* may be ``usd`` for presentment conversion via price_data fallback
    when a dedicated USD price is not configured (inline recurring price_data).

    *auto_renew*: when **False**, sets ``subscription_data[cancel_at_period_end]``
    so Stripe does not charge again after the paid month/year (customer still
    has access until period end).
    """
    plat = (platform or "").strip().lower()
    iv = normalize_billing_interval(interval)
    if iv == BILLING_INTERVAL_YEAR:
        amount = PRICE_YEARLY_PENCE
        product_name = STRIPE_PRODUCT_NAME_YEARLY
    else:
        amount = PRICE_PENCE
        product_name = STRIPE_PRODUCT_NAME_MONTHLY
    ref = encode_client_reference_id(plat, interval=iv)
    ccy = (currency or PRICE_CURRENCY).strip().lower() or PRICE_CURRENCY
    renew = bool(auto_renew)
    fields: list[tuple[str, str]] = [
        ("mode", "subscription"),
        ("success_url", success_url),
        ("cancel_url", cancel_url),
        ("client_reference_id", ref),
        ("metadata[platform]", plat),
        ("metadata[filename]", filename),
        ("metadata[billing_interval]", iv),
        ("metadata[amount_pence]", str(amount)),
        ("metadata[currency]", ccy if ccy == "usd" else PRICE_CURRENCY),
        ("metadata[product_name]", product_name),
        ("metadata[auto_renew]", "1" if renew else "0"),
        ("subscription_data[metadata][platform]", plat),
        ("subscription_data[metadata][billing_interval]", iv),
        ("subscription_data[metadata][auto_renew]", "1" if renew else "0"),
    ]
    # Prefer create-time cancel_at_period_end when the Stripe API version accepts
    # it; some accounts return parameter_unknown — then fulfilment applies
    # cancel_at_period_end on the Subscription after checkout.session.completed
    # (see apply_subscription_auto_renew_preference).
    if not renew:
        fields.append(("subscription_data[cancel_at_period_end]", "true"))
    # Prefer fixed recurring Price ids (GBP catalog products)
    price_id = stripe_subscription_price_id_for_interval(iv)
    if ccy == "usd":
        # Relative USD from GBP anchors (no separate USD Price required)
        try:
            from local_currency import FALLBACK_CURRENCY, convert_gbp_to_currency
        except ImportError:  # pragma: no cover
            from status_page.local_currency import (  # type: ignore
                FALLBACK_CURRENCY,
                convert_gbp_to_currency,
            )
        gbp = amount / 100.0
        cents = max(1, int(round(convert_gbp_to_currency(gbp, FALLBACK_CURRENCY) * 100)))
        fields.extend(
            [
                ("line_items[0][price_data][currency]", "usd"),
                ("line_items[0][price_data][unit_amount]", str(cents)),
                (
                    "line_items[0][price_data][recurring][interval]",
                    iv,
                ),
                (
                    "line_items[0][price_data][product_data][name]",
                    product_name,
                ),
                (
                    "line_items[0][price_data][product_data][description]",
                    f"{filename} · {plat}",
                ),
                ("line_items[0][quantity]", "1"),
            ]
        )
    elif price_id:
        fields.append(("line_items[0][price]", price_id))
        fields.append(("line_items[0][quantity]", "1"))
    else:
        fields.extend(
            [
                ("line_items[0][price_data][currency]", PRICE_CURRENCY),
                ("line_items[0][price_data][unit_amount]", str(amount)),
                ("line_items[0][price_data][recurring][interval]", iv),
                (
                    "line_items[0][price_data][product_data][name]",
                    product_name,
                ),
                (
                    "line_items[0][price_data][product_data][description]",
                    f"{filename} · {plat}",
                ),
                ("line_items[0][quantity]", "1"),
            ]
        )
    return urllib.parse.urlencode(fields).encode("utf-8")


def create_subscription_checkout_session(
    platform: str,
    *,
    interval: str = BILLING_INTERVAL_MONTH,
    base_url: str | None = None,
    http_post: HttpPostFn | None = None,
    currency: str = "",
    auto_renew: bool = True,
) -> dict[str, Any]:
    """Create a Stripe **subscription** Checkout Session for Monthly or Yearly VPN plan.

    Returns dict with id, url, platform, filename, amount_pence, currency,
    billing_interval, price_id, product_name, auto_renew.
    """
    filename = platform_filename(platform)
    if not filename:
        raise ValueError(f"unknown platform: {platform}")
    key = stripe_secret_key()
    if not key:
        raise ValueError("STRIPE_SECRET_KEY not configured")

    plat = (platform or "").strip().lower()
    iv = normalize_billing_interval(interval)
    if iv == BILLING_INTERVAL_YEAR:
        amount = PRICE_YEARLY_PENCE
    else:
        amount = PRICE_PENCE
    renew = bool(auto_renew)

    base = (base_url or public_base_url()).rstrip("/")
    success = (
        f"{base}{DEFAULT_SUCCESS_PATH}"
        f"?session_id={{CHECKOUT_SESSION_ID}}&platform={urllib.parse.quote(plat)}"
    )
    # Return to homepage Download client box (primary selection UX)
    cancel = (
        f"{base}/?platform={urllib.parse.quote(plat)}&interval={iv}#downloads"
    )

    presentment_ccy = PRICE_CURRENCY
    if (currency or "").strip():
        try:
            from local_currency import FALLBACK_CURRENCY, stripe_presentment_or_usd
        except ImportError:  # pragma: no cover
            from status_page.local_currency import (  # type: ignore
                FALLBACK_CURRENCY,
                stripe_presentment_or_usd,
            )
        if stripe_presentment_or_usd(currency) == FALLBACK_CURRENCY:
            presentment_ccy = "usd"

    body = build_subscription_checkout_form_body(
        plat,
        filename,
        interval=iv,
        success_url=success,
        cancel_url=cancel,
        currency=presentment_ccy,
        auto_renew=renew,
    )
    post = http_post or _default_http_post
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    status, raw = post(
        "https://api.stripe.com/v1/checkout/sessions",
        headers,
        body,
    )
    # Older Stripe API versions reject subscription_data[cancel_at_period_end]
    # at Session create — retry without it; metadata auto_renew still drives
    # post-checkout Subscription update.
    if status >= 400 and not renew and b"cancel_at_period_end" in (raw or b""):
        body_retry = build_subscription_checkout_form_body(
            plat,
            filename,
            interval=iv,
            success_url=success,
            cancel_url=cancel,
            currency=presentment_ccy,
            auto_renew=True,  # omit create-time cancel flag
        )
        # Force metadata auto_renew=0 on the retry body
        retry_fields = urllib.parse.parse_qsl(body_retry.decode("utf-8"))
        fixed: list[tuple[str, str]] = []
        for k, v in retry_fields:
            if k in (
                "metadata[auto_renew]",
                "subscription_data[metadata][auto_renew]",
            ):
                fixed.append((k, "0"))
            else:
                fixed.append((k, v))
        body_retry = urllib.parse.urlencode(fixed).encode("utf-8")
        status, raw = post(
            "https://api.stripe.com/v1/checkout/sessions",
            headers,
            body_retry,
        )
    if status >= 400:
        raise ValueError(f"stripe checkout create failed HTTP {status}: {raw[:300]!r}")
    data = json.loads(raw.decode("utf-8"))
    url = data.get("url")
    sid = data.get("id")
    if not url or not sid:
        raise ValueError("stripe response missing url/id")
    charge_ccy = presentment_ccy if presentment_ccy == "usd" else PRICE_CURRENCY
    return {
        "id": sid,
        "url": url,
        "platform": plat,
        "filename": filename,
        "amount_pence": amount if charge_ccy != "usd" else amount,
        "currency": charge_ccy,
        "billing_interval": iv,
        "price_id": stripe_subscription_price_id_for_interval(iv),
        "product_name": stripe_product_name_for_interval(iv),
        "mode": "subscription",
        "auto_renew": renew,
    }


def build_checkout_form_body(req: CheckoutRequest) -> bytes:
    """application/x-www-form-urlencoded body for Stripe Checkout Session create.

    Always uses ``mode=payment`` (one-time). Package downloads never attach a
    recurring Payment Link price — that causes HTTP 400 from Stripe.
    """
    fields: list[tuple[str, str]] = [
        ("mode", "payment"),
        ("success_url", req.success_url),
        ("cancel_url", req.cancel_url),
        ("client_reference_id", req.platform),
        ("metadata[platform]", req.platform),
        ("metadata[filename]", req.filename),
        ("metadata[amount_pence]", str(PRICE_PENCE)),
        ("metadata[currency]", PRICE_CURRENCY),
        # Always create a Stripe Customer so Checkout requires an email
        # (receipts, refunds, and operator contact). Guest pay without email
        # is disabled for package downloads.
        ("customer_creation", "always"),
    ]
    # One-time Dashboard price only (see stripe_price_id). Never use Payment Link
    # recurring price ids here.
    price_id = stripe_price_id()
    if price_id:
        fields.append(("line_items[0][price]", price_id))
        fields.append(("line_items[0][quantity]", "1"))
    else:
        # Inline one-time price_data — correct for payment mode (245 pence GBP).
        fields.extend(
            [
                ("line_items[0][price_data][currency]", PRICE_CURRENCY),
                ("line_items[0][price_data][unit_amount]", str(PRICE_PENCE)),
                (
                    "line_items[0][price_data][product_data][name]",
                    f"Restore Privacy download - {req.platform}",
                ),
                (
                    "line_items[0][price_data][product_data][description]",
                    req.filename,
                ),
                ("line_items[0][quantity]", "1"),
            ]
        )
    return urllib.parse.urlencode(fields).encode("utf-8")


def build_checkout_form_body_usd(
    req: CheckoutRequest,
    *,
    amount_gbp: float,
    interval: str = BILLING_INTERVAL_MONTH,
) -> bytes:
    """One-time Checkout body charged in **USD** (relative to GBP anchor).

    Used when Stripe cannot present the visitor currency — default presentment
    is USD, not silent GBP. Unit amount is integer US cents from
    :func:`local_currency.convert_gbp_to_currency`.
    """
    try:
        from local_currency import FALLBACK_CURRENCY, convert_gbp_to_currency
    except ImportError:  # pragma: no cover
        from status_page.local_currency import (  # type: ignore
            FALLBACK_CURRENCY,
            convert_gbp_to_currency,
        )

    usd_amount = convert_gbp_to_currency(float(amount_gbp), FALLBACK_CURRENCY)
    cents = max(1, int(round(usd_amount * 100)))
    iv = (interval or BILLING_INTERVAL_MONTH).strip().lower()
    ref = encode_client_reference_id(req.platform, interval=iv)
    fields: list[tuple[str, str]] = [
        ("mode", "payment"),
        ("success_url", req.success_url),
        ("cancel_url", req.cancel_url),
        ("client_reference_id", ref),
        ("metadata[platform]", req.platform),
        ("metadata[filename]", req.filename),
        ("metadata[amount_cents]", str(cents)),
        ("metadata[currency]", "usd"),
        ("metadata[gbp_anchor]", str(amount_gbp)),
        ("metadata[billing_interval]", iv),
        ("metadata[presentment]", "usd"),
        ("customer_creation", "always"),
        ("line_items[0][price_data][currency]", "usd"),
        ("line_items[0][price_data][unit_amount]", str(cents)),
        (
            "line_items[0][price_data][product_data][name]",
            f"Restore Privacy ({iv}) - {req.platform}",
        ),
        (
            "line_items[0][price_data][product_data][description]",
            req.filename,
        ),
        ("line_items[0][quantity]", "1"),
    ]
    return urllib.parse.urlencode(fields).encode("utf-8")


def create_checkout_session(
    platform: str,
    *,
    base_url: str | None = None,
    http_post: HttpPostFn | None = None,
    currency: str = "",
    interval: str = BILLING_INTERVAL_MONTH,
    auto_renew: bool = True,
) -> dict[str, Any]:
    """Create a Stripe Checkout Session for one package.

    Catalog default: **subscription** Checkout for Monthly or Yearly VPN plan
    (see :func:`create_subscription_checkout_session`). Pass
    ``RPT_CHECKOUT_ONE_TIME=1`` to force legacy one-time payment mode.

    When *currency* resolves to **USD** presentment, subscription session uses
    USD recurring price_data relative to GBP anchors.
    """
    if os.environ.get("RPT_CHECKOUT_ONE_TIME", "").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return create_subscription_checkout_session(
            platform,
            interval=interval,
            base_url=base_url,
            http_post=http_post,
            currency=currency,
            auto_renew=auto_renew,
        )

    filename = platform_filename(platform)
    if not filename:
        raise ValueError(f"unknown platform: {platform}")
    key = stripe_secret_key()
    if not key:
        raise ValueError("STRIPE_SECRET_KEY not configured")

    base = (base_url or public_base_url()).rstrip("/")
    success = (
        f"{base}{DEFAULT_SUCCESS_PATH}"
        f"?session_id={{CHECKOUT_SESSION_ID}}&platform={urllib.parse.quote(platform)}"
    )
    cancel = f"{base}{SITE_PAY_PLAN_PATH}?platform={urllib.parse.quote(platform)}"
    creq = CheckoutRequest(
        platform=platform,
        filename=filename,
        success_url=success,
        cancel_url=cancel,
    )
    try:
        from local_currency import (
            FALLBACK_CURRENCY,
            PRICE_MONTHLY_GBP,
            PRICE_YEARLY_GBP,
            convert_gbp_to_currency,
            stripe_presentment_or_usd,
        )
    except ImportError:  # pragma: no cover
        from status_page.local_currency import (  # type: ignore
            FALLBACK_CURRENCY,
            PRICE_MONTHLY_GBP,
            PRICE_YEARLY_GBP,
            convert_gbp_to_currency,
            stripe_presentment_or_usd,
        )

    presentment = (
        stripe_presentment_or_usd(currency) if (currency or "").strip() else ""
    )
    iv = (interval or BILLING_INTERVAL_MONTH).strip().lower()
    if iv in ("year", "yearly", "annual", "annually"):
        iv = BILLING_INTERVAL_YEAR
        gbp_amt = PRICE_YEARLY_GBP
    else:
        iv = BILLING_INTERVAL_MONTH
        gbp_amt = PRICE_MONTHLY_GBP

    if presentment == FALLBACK_CURRENCY:
        body = build_checkout_form_body_usd(
            creq, amount_gbp=gbp_amt, interval=iv
        )
        charge_currency = "usd"
        unit_amount = int(
            round(convert_gbp_to_currency(gbp_amt, FALLBACK_CURRENCY) * 100)
        )
    else:
        body = build_checkout_form_body(creq)
        charge_currency = PRICE_CURRENCY
        unit_amount = PRICE_PENCE

    post = http_post or _default_http_post
    status, raw = post(
        "https://api.stripe.com/v1/checkout/sessions",
        {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body,
    )
    if status >= 400:
        raise ValueError(f"stripe checkout create failed HTTP {status}: {raw[:300]!r}")
    data = json.loads(raw.decode("utf-8"))
    url = data.get("url")
    sid = data.get("id")
    if not url or not sid:
        raise ValueError("stripe response missing url/id")
    return {
        "id": sid,
        "url": url,
        "platform": platform,
        "filename": filename,
        "amount_pence": unit_amount if charge_currency == "gbp" else PRICE_PENCE,
        "amount_cents": unit_amount if charge_currency == "usd" else None,
        "currency": charge_currency,
        "billing_interval": iv,
        "presentment": presentment or charge_currency,
    }


def resolve_usd_pay_redirect_url(
    platform: str,
    *,
    interval: str = BILLING_INTERVAL_MONTH,
    base_url: str | None = None,
    http_post: HttpPostFn | None = None,
) -> str:
    """Absolute URL for USD presentment pay: USD Payment Link or Checkout Session.

    Prefer operator ``STRIPE_PAYMENT_PAGE_URL_USD`` (yearly variant for year).
    Else create a Stripe Checkout Session charged in **usd** (relative to GBP
    anchors). Raises ValueError if neither path is available.
    """
    plat = (platform or "").strip().lower() or "windows"
    usd_base = stripe_payment_page_url_usd_for_interval(interval)
    if usd_base:
        params = {
            "client_reference_id": encode_client_reference_id(
                plat, interval=interval
            ),
            "locale": "en",
        }
        q = urllib.parse.urlencode(params)
        sep = "&" if "?" in usd_base else "?"
        return f"{usd_base}{sep}{q}"
    session = create_checkout_session(
        plat,
        base_url=base_url,
        http_post=http_post,
        currency="USD",
        interval=interval,
    )
    return str(session["url"])


# --- Webhook signature + grant ---------------------------------------------------


def verify_stripe_signature(
    payload: bytes,
    sig_header: str,
    secret: str,
    *,
    tolerance_sec: int = 300,
    now: float | None = None,
) -> bool:
    """Verify Stripe-Signature header (t=…,v1=…)."""
    if not secret or not sig_header:
        return False
    parts: dict[str, list[str]] = {}
    for item in sig_header.split(","):
        item = item.strip()
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        parts.setdefault(k.strip(), []).append(v.strip())
    if "t" not in parts or "v1" not in parts:
        return False
    try:
        ts = int(parts["t"][0])
    except ValueError:
        return False
    tnow = now if now is not None else time.time()
    if abs(tnow - ts) > tolerance_sec:
        return False
    signed = f"{ts}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    for cand in parts["v1"]:
        if hmac.compare_digest(expected, cand):
            return True
    return False


def process_checkout_completed_event(
    event: dict[str, Any],
    *,
    email_transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    now: float | None = None,
) -> str | None:
    """On checkout.session.completed, mint a download token. Returns token or None.

    Supports **subscription** Payment Link checkouts (catalog: £2.45/month or
    £27.93/year) and legacy full-price paid sessions.

    Platform comes from ``client_reference_id`` (BUY tile) or ``metadata.platform``.

    **Only if paid / subscription:** ``payment_status`` must be ``paid`` or
    ``no_payment_required``.
    **Full product price:** amount must equal ``PRICE_PENCE`` (245), **or** a
    subscription session with a ``subscription`` id (including legacy zero-amount
    trial checkouts that still carry a subscription id). Underpay without a
    subscription never mints a grant.

    Stores ``subscription_id`` on the Connect entitlement when present. Mints a
    unique **keygen** and attempts fulfilment email (best-effort SMTP).

    **Licence period:** always sets ``valid_until`` to Stripe
    ``current_period_end`` when present, else **one calendar month** (monthly
    plan) or **one calendar year** (yearly plan) from *now* — never unlimited
    for paid catalog grants.
    """
    if event.get("type") != "checkout.session.completed":
        return None
    obj = event.get("data", {}).get("object") or {}
    # Require an explicit paid status (blank/missing is not enough).
    payment_status = str(obj.get("payment_status") or "").strip().lower()
    if payment_status not in ("paid", "no_payment_required"):
        return None
    meta = obj.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    platform = platform_from_stripe_checkout_session(obj)
    billing_interval = billing_interval_from_stripe_checkout_session(obj)
    t_now = float(now if now is not None else time.time())
    # Always mint the **current** catalog package for the platform (pay-time truth).
    filename = resolve_paid_grant_filename(
        platform, metadata_filename=str(meta.get("filename") or "")
    ) or ""
    if not platform or not filename:
        return None
    if filename not in catalog_filenames():
        return None
    # Resolve paid amount in pence; never invent PRICE_PENCE when zero/missing.
    amount: int | None = None
    try:
        if meta.get("amount_pence") is not None and str(meta.get("amount_pence")).strip() != "":
            amount = int(meta.get("amount_pence"))
        elif obj.get("amount_total") is not None and str(obj.get("amount_total")).strip() != "":
            amount = int(obj.get("amount_total"))
    except (TypeError, ValueError):
        return None
    session_id = str(obj.get("id") or "")
    payment_intent_id = _payment_intent_id_from_stripe_object(obj)
    sub_raw = obj.get("subscription")
    if isinstance(sub_raw, dict):
        subscription_id = str(sub_raw.get("id") or "")
    else:
        subscription_id = str(sub_raw or "").strip()
    # Full price (245 GBP pence) always OK. Yearly catalog amount (2940) with
    # subscription id is OK. Paid monthly/yearly subscriptions mint without a
    # free-trial window. Legacy £0 / no_payment_required still allowed only with
    # a subscription id so underpay one-time never mints.
    # USD one-time: relative cents from GBP anchors (local_currency FX table).
    currency = str(meta.get("currency") or obj.get("currency") or PRICE_CURRENCY).strip().lower()
    amount_ok = amount is not None and amount == PRICE_PENCE and currency in ("", PRICE_CURRENCY, "gbp")
    yearly_amount_ok = (
        amount is not None
        and amount == PRICE_YEARLY_PENCE
        and currency in ("", PRICE_CURRENCY, "gbp")
        and bool(subscription_id)
    )
    usd_ok = False
    if currency == "usd" and amount is not None and amount > 0:
        try:
            from local_currency import (
                PRICE_MONTHLY_GBP,
                PRICE_YEARLY_GBP,
                convert_gbp_to_currency,
            )
        except ImportError:  # pragma: no cover
            from status_page.local_currency import (  # type: ignore
                PRICE_MONTHLY_GBP,
                PRICE_YEARLY_GBP,
                convert_gbp_to_currency,
            )
        expect_m = int(round(convert_gbp_to_currency(PRICE_MONTHLY_GBP, "USD") * 100))
        expect_y = int(round(convert_gbp_to_currency(PRICE_YEARLY_GBP, "USD") * 100))
        # Allow small rounding slack (±2 cents)
        usd_ok = abs(int(amount) - expect_m) <= 2 or abs(int(amount) - expect_y) <= 2
    yearly_sub_ok = bool(subscription_id) and billing_interval == BILLING_INTERVAL_YEAR and (
        amount is None or amount >= 0
    )
    # Legacy name: subscription session with zero/no_payment_required still mints
    # (no free-trial product path required; paid monthly/yearly use amount_ok paths).
    trial_ok = bool(subscription_id) and (
        payment_status == "no_payment_required"
        or amount == 0
        or amount is None
    )
    if not amount_ok and not yearly_amount_ok and not trial_ok and not yearly_sub_ok and not usd_ok:
        return None
    # Paid catalog: always set a finite period end (month or year).
    stripe_pe = stripe_period_end_from_checkout_object(obj)
    valid_until = valid_until_for_paid_interval(
        billing_interval,
        now=t_now,
        stripe_period_end=stripe_pe,
    )
    if yearly_amount_ok:
        grant_pence = PRICE_YEARLY_PENCE
    elif amount_ok or trial_ok:
        grant_pence = PRICE_PENCE
    elif usd_ok and amount is not None:
        grant_pence = int(amount)
    elif amount is not None and amount > 0:
        grant_pence = int(amount)
    else:
        grant_pence = PRICE_PENCE
    token = mint_download_token(
        filename=filename,
        platform=platform,
        session_id=session_id,
        amount_pence=grant_pence,
        currency=PRICE_CURRENCY,
    )
    # Successful paid/trial session → Connect entitlement active + unique keygen
    keygen = ""
    cust_email = customer_email_from_checkout_object(obj)
    if session_id:
        keygen = activate_connect_entitlement(
            session_id,
            platform=platform,
            payment_intent_id=payment_intent_id,
            subscription_id=subscription_id,
            valid_until=valid_until,
            customer_email=cust_email,
            billing_interval=billing_interval,
            now=t_now,
        ) or ""
    # Apply purchase-flow auto-renew choice on the Subscription (cancel_at_period_end)
    if subscription_id:
        try:
            renew_pref = auto_renew_from_checkout_object(obj)
            apply_subscription_auto_renew_preference(
                subscription_id, auto_renew=renew_pref
            )
        except Exception as exc:  # noqa: BLE001
            print(
                f"auto_renew_apply_failed session={session_id!r} sub={subscription_id!r} "
                f"err={exc!r}",
                flush=True,
            )
    # Customer fulfilment email: KEYGEN + PPI + 1-hour download URL
    try:
        if token and cust_email:
            # Ensure keygen exists before email even if activate returned empty
            if not keygen and session_id:
                keygen = assign_keygen_for_session(session_id) or keygen
            mail = fulfil_checkout_with_email(
                token=token,
                session_id=session_id,
                platform=platform,
                filename=filename,
                customer_email=cust_email,
                keygen=keygen,
                transport=email_transport,
            )
            send = (mail or {}).get("send") or {}
            mail_kg = str((mail or {}).get("keygen") or "")
            mail_dl = str((mail or {}).get("download_url") or "")
            if not send.get("sent"):
                # Best-effort diagnostics (no secrets) — Render logs
                print(
                    "fulfilment_email_not_sent "
                    f"session={session_id!r} "
                    f"skipped={send.get('skipped')} "
                    f"error={send.get('error')!r} "
                    f"has_keygen={bool(mail_kg)} "
                    f"has_download={bool(mail_dl and '/download?token=' in mail_dl)} "
                    f"smtp={assess_fulfilment_smtp_readiness().get('status')!r}",
                    flush=True,
                )
            else:
                print(
                    f"fulfilment_email_sent session={session_id!r} to_domain="
                    f"{cust_email.split('@')[-1]!r} "
                    f"has_keygen={bool(mail_kg)} "
                    f"has_download={bool(mail_dl and '/download?token=' in mail_dl)}",
                    flush=True,
                )
        elif token and not cust_email:
            print(
                "fulfilment_email_skipped_no_customer_email "
                f"session={session_id!r} keygen_minted={bool(keygen)} "
                f"customer_field={type(obj.get('customer')).__name__}",
                flush=True,
            )
    except Exception as exc:  # noqa: BLE001
        # Never block grant mint on email failure
        print(f"fulfilment_email_exception session={session_id!r} err={exc!r}", flush=True)
    return token


def admin_resend_fulfilment_email(
    *,
    to_email: str,
    session_id: str = "",
    purchase_id: str = "",
    platform: str = "",
    transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Operator recovery: re-send keygen + download fulfilment email.

    Looks up keygen from session entitlement and mints a fresh download token
    when *purchase_id* or *session_id* maps to a paid grant / platform.
    Uses the real :func:`send_fulfilment_email` path (or injected *transport*).
    """
    to_addr = (to_email or "").strip()
    if not to_addr or "@" not in to_addr:
        return {"ok": False, "sent": False, "error": "missing_to_email"}
    sid = (session_id or "").strip()
    pid = normalize_purchase_id(purchase_id) or (purchase_id or "").strip()
    plat = (platform or "").strip().lower()
    keygen = ""
    filename = ""
    token = ""
    if sid:
        ent = get_connect_entitlement(sid)
        if ent:
            keygen = str(ent.get("keygen") or "")
            if not plat:
                plat = str(ent.get("platform") or "").strip().lower()
    if pid:
        reissued = reissue_download_for_purchase_id(pid, base_url=base_url)
        if reissued:
            token = str(reissued.get("token") or "")
            filename = str(reissued.get("filename") or "")
            plat = plat or str(reissued.get("platform") or "")
            sid = sid or str(reissued.get("session_id") or "")
            pid = str(reissued.get("purchase_id") or pid)
    if not token and plat:
        fname = platform_filename(plat)
        if fname:
            filename = fname
            token = mint_download_token(
                filename=fname,
                platform=plat,
                session_id=sid or f"admin_resend_{secrets.token_hex(6)}",
                amount_pence=PRICE_PENCE,
                currency=PRICE_CURRENCY,
            )
    if not keygen and sid:
        keygen = activate_connect_entitlement(sid, platform=plat) or ""
    if not keygen:
        keygen = generate_keygen()
    if not token:
        return {
            "ok": False,
            "sent": False,
            "error": "no_download_token",
            "detail": "Provide purchase_id or platform so a download link can be minted",
        }
    mail = fulfil_checkout_with_email(
        token=token,
        session_id=sid or f"admin_resend_{secrets.token_hex(4)}",
        platform=plat or "windows",
        filename=filename or platform_filename(plat or "windows") or "",
        customer_email=to_addr,
        keygen=keygen,
        purchase_id=pid,
        base_url=base_url,
        transport=transport,
    )
    send = (mail or {}).get("send") or {}
    return {
        "ok": bool(send.get("ok", True)),
        "sent": bool(send.get("sent")),
        "skipped": bool(send.get("skipped")),
        "error": send.get("error"),
        "to_domain": to_addr.split("@")[-1],
        "keygen_prefix": (str(mail.get("keygen") or "")[:12]),
        "has_download_url": bool(mail.get("download_url")),
        "smtp_status": assess_fulfilment_smtp_readiness().get("status"),
        "admin_resend": True,
    }


def handle_stripe_webhook(
    payload: bytes,
    sig_header: str,
    *,
    secret: str | None = None,
    now: float | None = None,
    email_transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Verify signature; grant token on paid checkout; revoke on payment failure.

    Returns {ok, granted, token?, keygen?, revoked?, session_id?, error?}.
    """
    wh_secret = (secret if secret is not None else stripe_webhook_secret()).strip()
    if not verify_stripe_signature(payload, sig_header, wh_secret, now=now):
        return {"ok": False, "granted": False, "error": "invalid_signature"}
    try:
        event = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"ok": False, "granted": False, "error": "bad_json"}
    token = process_checkout_completed_event(event, email_transport=email_transport)
    if token:
        sid = ""
        kg = ""
        try:
            obj = (event.get("data") or {}).get("object") or {}
            if isinstance(obj, dict):
                sid = str(obj.get("id") or "")
            if sid:
                ent = get_connect_entitlement(sid)
                if ent:
                    kg = str(ent.get("keygen") or "")
        except Exception:  # noqa: BLE001
            pass
        return {
            "ok": True,
            "granted": True,
            "token": token,
            "revoked": False,
            "session_id": sid,
            "keygen": kg,
        }
    # Subscription cancel / renew / period end
    sub_result = process_subscription_lifecycle_event(event, now=now)
    if sub_result:
        return {
            "ok": True,
            "granted": False,
            "revoked": sub_result.get("action") == "revoked",
            "subscription": sub_result,
            "session_id": sub_result.get("session_id"),
            "event_type": str(event.get("type") or ""),
        }
    # Observe failure protocols → cancel Connect entitlement
    revoked_sid = process_payment_failure_event(event)
    if revoked_sid:
        return {
            "ok": True,
            "granted": False,
            "revoked": True,
            "session_id": revoked_sid,
            "event_type": str(event.get("type") or ""),
        }
    # Unpaid checkout.session.completed must not leave an active entitlement
    if event.get("type") == "checkout.session.completed":
        obj = (event.get("data") or {}).get("object") or {}
        if isinstance(obj, dict):
            ps = str(obj.get("payment_status") or "").strip().lower()
            sid = str(obj.get("id") or "")
            if sid and ps and ps not in ("paid", "no_payment_required"):
                revoke_connect_entitlement(sid, reason=f"unpaid:{ps}")
                return {
                    "ok": True,
                    "granted": False,
                    "revoked": True,
                    "session_id": sid,
                    "event_type": "checkout.session.completed",
                }
    return {"ok": True, "granted": False, "revoked": False}


def checkout_amount_fields_for_tests() -> dict[str, Any]:
    """Expose pricing constants for unit tests (real shipped values)."""
    return {
        "amount_pence": PRICE_PENCE,
        "currency": PRICE_CURRENCY,
        "label": PRICE_LABEL,
    }
