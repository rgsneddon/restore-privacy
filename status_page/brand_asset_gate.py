"""Compulsory KEYGEN trial/entitlement gate for public brand-package delivery.

Brand installers (Suite platforms, Rx/browser assets under ``/assets/…``, map
links) are **not** anonymous freebies. Delivery requires one of:

- active Connect entitlement (Stripe subscription with 3-day trial started or
  paid period OK) via ``session_id``
- fulfilment KEYGEN bound to an active entitlement
- valid paid/minted download grant ``token``

Without credentials the gate returns deny + redirect to ``/pay`` (catalog
KEYGEN trial checkout). Operator admin mint/token paths still work via grant
tokens.

Pure decision helpers take pre-resolved entitlement/grant state so unit tests
do not need a live HTTP stack; :func:`evaluate_brand_package_request` is the
handler entry that looks up real payment store rows.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

# Catalog KEYGEN / trial checkout (monthly + yearly; 3-day trial on session).
DEFAULT_KEYGEN_PAY_PATH = "/pay"
DEFAULT_DENY_REASON = "keygen_trial_required"
DEFAULT_ALLOW_REASONS = frozenset(
    {
        "download_token",
        "session_entitlement",
        "keygen_entitlement",
        "operator_grant",
    }
)


def keygen_pay_redirect_url(
    *,
    next_path: str = "",
    pay_path: str = DEFAULT_KEYGEN_PAY_PATH,
    platform: str = "",
    product: str = "suite",
) -> str:
    """Build ``/pay`` (or custom) URL with optional return path after trial start."""
    base = (pay_path or DEFAULT_KEYGEN_PAY_PATH).strip() or DEFAULT_KEYGEN_PAY_PATH
    if not base.startswith("/"):
        base = "/" + base
    q: dict[str, str] = {}
    nxt = (next_path or "").strip()
    if nxt and nxt.startswith("/") and not nxt.startswith("//"):
        q["next"] = nxt
    plat = (platform or "").strip().lower()
    if plat:
        q["platform"] = plat
    pl = (product or "").strip().lower()
    if pl:
        q["product"] = pl
    if not q:
        return base
    return f"{base}?{urllib.parse.urlencode(q)}"


def brand_package_access_decision(
    *,
    has_valid_download_token: bool = False,
    session_entitlement_allows: bool = False,
    keygen_entitlement_allows: bool = False,
    next_path: str = "",
    platform: str = "",
    pay_path: str = DEFAULT_KEYGEN_PAY_PATH,
) -> dict[str, Any]:
    """Pure gate: allow brand package delivery only with KEYGEN trial/pay proof.

    Returns::
      {
        "allow": bool,
        "reason": str,
        "redirect": str | None,   # set when deny
        "http_status": int,       # 302 when redirecting unpaid; 200 when allow
      }
    """
    if has_valid_download_token:
        return {
            "allow": True,
            "reason": "download_token",
            "redirect": None,
            "http_status": 200,
        }
    if session_entitlement_allows:
        return {
            "allow": True,
            "reason": "session_entitlement",
            "redirect": None,
            "http_status": 200,
        }
    if keygen_entitlement_allows:
        return {
            "allow": True,
            "reason": "keygen_entitlement",
            "redirect": None,
            "http_status": 200,
        }
    redir = keygen_pay_redirect_url(
        next_path=next_path,
        pay_path=pay_path,
        platform=platform,
        product="suite",
    )
    return {
        "allow": False,
        "reason": DEFAULT_DENY_REASON,
        "redirect": redir,
        "http_status": 302,
    }


def _entitlement_connect_allowed(ent: dict[str, Any] | None) -> bool:
    if not ent:
        return False
    return bool(ent.get("connect_allowed"))


def evaluate_brand_package_request(
    *,
    session_id: str = "",
    keygen: str = "",
    token: str = "",
    next_path: str = "",
    platform: str = "",
    pay_path: str = DEFAULT_KEYGEN_PAY_PATH,
    now: float | None = None,
) -> dict[str, Any]:
    """Handler entry: resolve payment-store proof, then pure decision.

    Looks up download grant + connect entitlements from the live payments module.
    """
    has_token = False
    sess_ok = False
    kg_ok = False
    tok = (token or "").strip()
    sid = (session_id or "").strip()
    kg = (keygen or "").strip().upper().replace(" ", "")

    try:
        from payments import (
            connect_entitlement_allows,
            get_connect_entitlement_by_keygen,
            lookup_download_token,
        )
    except ImportError:  # pragma: no cover
        from status_page.payments import (  # type: ignore
            connect_entitlement_allows,
            get_connect_entitlement_by_keygen,
            lookup_download_token,
        )

    if tok:
        grant = lookup_download_token(tok, now=now)
        has_token = grant is not None
    if sid:
        sess_ok = bool(connect_entitlement_allows(sid, now=now))
    if kg:
        ent = get_connect_entitlement_by_keygen(kg, now=now)
        kg_ok = _entitlement_connect_allowed(ent)

    decision = brand_package_access_decision(
        has_valid_download_token=has_token,
        session_entitlement_allows=sess_ok,
        keygen_entitlement_allows=kg_ok,
        next_path=next_path,
        platform=platform,
        pay_path=pay_path,
    )
    decision["session_id"] = sid
    decision["has_token"] = has_token
    decision["keygen_provided"] = bool(kg)
    return decision


def is_brand_asset_delivery_path(path: str) -> bool:
    """True for public paths that stream brand installers (Suite + /assets)."""
    p = (path or "").split("?", 1)[0].rstrip("/") or "/"
    if p == "/suite/download":
        return True
    if p.startswith("/assets/"):
        return True
    return False


# ---------------------------------------------------------------------------
# Business-Class £3000 commercial deposit (pure guards)
# ---------------------------------------------------------------------------

try:
    from payments import (
        COMMERCIAL_SUITE_NODE_PRICE_PENCE,
        COMMERCIAL_SUITE_PRODUCT_KEY,
        COMMERCIAL_SUITE_PRODUCT_LINE,
    )
except ImportError:  # pragma: no cover
    try:
        from status_page.payments import (  # type: ignore
            COMMERCIAL_SUITE_NODE_PRICE_PENCE,
            COMMERCIAL_SUITE_PRODUCT_KEY,
            COMMERCIAL_SUITE_PRODUCT_LINE,
        )
    except ImportError:  # pragma: no cover
        COMMERCIAL_SUITE_NODE_PRICE_PENCE = 300_000
        COMMERCIAL_SUITE_PRODUCT_KEY = "commercial_suite_node"
        COMMERCIAL_SUITE_PRODUCT_LINE = "commercial_suite"

REQUIRED_BUSINESS_DEPOSIT_PENCE = int(COMMERCIAL_SUITE_NODE_PRICE_PENCE)
REQUIRED_BUSINESS_DEPOSIT_LABEL = "£3000"


def commercial_deposit_amount_ok(amount_pence: Any) -> bool:
    """True only when amount is exactly the compulsory £3000 deposit (300_000 p)."""
    try:
        return int(amount_pence) == int(REQUIRED_BUSINESS_DEPOSIT_PENCE)
    except (TypeError, ValueError):
        return False


def commercial_deposit_product_ok(
    product: str = "",
    product_line: str = "",
) -> bool:
    """True when product identifiers match the commercial Suite deposit product."""
    pk = (product or "").strip().lower()
    pl = (product_line or "").strip().lower()
    if pk and pk not in (
        str(COMMERCIAL_SUITE_PRODUCT_KEY).lower(),
        "commercial_suite",
        "business_class",
        "full_business_package",
    ):
        # Accept exact product key; reject KEYGEN/catalog products
        if pk in ("vpn", "suite", "keygen", "monthly", "yearly"):
            return False
        if pk != str(COMMERCIAL_SUITE_PRODUCT_KEY).lower():
            return False
    if pl and pl not in (
        str(COMMERCIAL_SUITE_PRODUCT_LINE).lower(),
        "commercial_suite",
    ):
        return False
    if not pk and not pl:
        return False
    # At least one side matches commercial
    ok_key = (not pk) or pk in (
        str(COMMERCIAL_SUITE_PRODUCT_KEY).lower(),
        "commercial_suite",
        "business_class",
        "full_business_package",
    )
    ok_line = (not pl) or pl in (
        str(COMMERCIAL_SUITE_PRODUCT_LINE).lower(),
        "commercial_suite",
    )
    return bool(ok_key and ok_line)


def commercial_deposit_gate(
    *,
    amount_pence: Any = None,
    product: str = "",
    product_line: str = "",
    mode: str = "payment",
    billing: str = "one_time",
) -> dict[str, Any]:
    """Pure Business-Class fulfilment/checkout guard.

    Compulsory: one-time payment mode + exactly £3000 (300_000 pence) +
    commercial product identity. KEYGEN subscription sessions never pass.
    """
    mode_s = (mode or "").strip().lower()
    billing_s = (billing or "").strip().lower()
    amount_ok = commercial_deposit_amount_ok(amount_pence)
    product_ok = commercial_deposit_product_ok(product, product_line)
    mode_ok = mode_s in ("payment", "one_time", "onetime", "")
    # Reject subscription / KEYGEN modes explicitly
    if mode_s in ("subscription", "recurring", "keygen"):
        mode_ok = False
    if billing_s in ("month", "monthly", "year", "yearly", "subscription"):
        mode_ok = False
    allow = bool(amount_ok and product_ok and mode_ok)
    reason = "commercial_deposit_ok"
    if not amount_ok:
        reason = "deposit_amount_required_3000_gbp"
    elif not product_ok:
        reason = "commercial_product_required"
    elif not mode_ok:
        reason = "one_time_payment_required"
    return {
        "allow": allow,
        "reason": reason,
        "required_pence": int(REQUIRED_BUSINESS_DEPOSIT_PENCE),
        "required_label": REQUIRED_BUSINESS_DEPOSIT_LABEL,
        "amount_ok": amount_ok,
        "product_ok": product_ok,
        "mode_ok": mode_ok,
    }


def commercial_checkout_session_allowed(session: dict[str, Any] | None) -> dict[str, Any]:
    """Validate a create_commercial_suite_checkout_session-shaped result (or Stripe-ish)."""
    s = session or {}
    amount = s.get("amount_pence")
    if amount is None:
        # Stripe session shape: amount_total
        amount = s.get("amount_total")
    meta = s.get("metadata") if isinstance(s.get("metadata"), dict) else {}
    product = str(
        s.get("product")
        or s.get("client_reference_id")
        or meta.get("product")
        or ""
    )
    product_line = str(
        s.get("product_line") or meta.get("product_line") or ""
    )
    mode = str(s.get("mode") or meta.get("billing") or "payment")
    billing = str(s.get("billing") or meta.get("billing") or "one_time")
    return commercial_deposit_gate(
        amount_pence=amount,
        product=product,
        product_line=product_line or COMMERCIAL_SUITE_PRODUCT_LINE,
        mode=mode,
        billing=billing,
    )
