"""Paid download fulfilment: Stripe Checkout (£2.45 GBP) + single-use tokens.

Stripe is the paid-download gateway (settles to the operator Stripe account when
live keys are set). Buy Me a Coffee is tip/support only — see coffee_link.py and
docs/PAID_DOWNLOADS_HOWTO.md.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from downloads import RELEASE_ASSETS, available_downloads

# £2.45 per selected package download
PRICE_PENCE = 245
PRICE_CURRENCY = "gbp"
PRICE_LABEL = "£2.45"

DEFAULT_SUCCESS_PATH = "/download/success"
DEFAULT_CANCEL_PATH = "/download/cancel"
TOKEN_TTL_SEC = int(os.environ.get("RPT_DOWNLOAD_TOKEN_TTL_SEC", "3600"))


def _data_dir() -> Path:
    raw = os.environ.get("RPT_PAYMENT_DATA_DIR", "").strip()
    if raw:
        p = Path(raw)
    else:
        p = Path(__file__).resolve().parent / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return _data_dir() / "paid_downloads.sqlite3"


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


# Public Stripe Payment Link / Donate page (not a secret — operator-provided).
# Does **not** enable Checkout token fulfilment by itself.
DEFAULT_STRIPE_PAYMENT_PAGE_URL = (
    "https://donate.stripe.com/cNi7sM4uOeWQ9TBe0q7kc00"
)
# Dashboard Payment Link object id (plink_…) for the same public page.
DEFAULT_STRIPE_PAYMENT_LINK_ID = "plink_1TvTu6JDavQ2TJW6FeL0dIh9"
# Line item price on that Payment Link (recurring / donate) — not for payment-mode Checkout.
DEFAULT_STRIPE_PAYMENT_LINK_PRICE_ID = "price_1TvTsaJDavQ2TJW6HZVIG7hg"


def stripe_payment_page_url() -> str:
    """Operator Stripe payment page (Payment Link / Donate). Public, non-secret.

    Override with ``STRIPE_PAYMENT_PAGE_URL`` or ``RPT_STRIPE_PAYMENT_PAGE_URL``.
    """
    for key in ("STRIPE_PAYMENT_PAGE_URL", "RPT_STRIPE_PAYMENT_PAGE_URL"):
        raw = os.environ.get(key, "").strip()
        if raw:
            return raw.rstrip("/")
    return DEFAULT_STRIPE_PAYMENT_PAGE_URL


def stripe_payment_page_href_for_platform(platform: str) -> str:
    """Payment page URL with product identity for webhook fulfilment.

    Stripe Payment Links accept ``client_reference_id`` on the URL; the webhook
    reads it as the requested package platform and mints a one-time download token.
    """
    plat = (platform or "").strip().lower()
    base = stripe_payment_page_url()
    if not plat:
        return base
    q = urllib.parse.urlencode({"client_reference_id": plat})
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

    Prefers ``client_reference_id`` (Payment Link BUY tile), then
    ``metadata.platform`` (server Checkout). Only returns known catalog keys.
    """
    if not isinstance(sess, dict):
        return ""
    ref = str(sess.get("client_reference_id") or "").strip().lower()
    if platform_filename(ref):
        return ref
    meta = sess.get("metadata") if isinstance(sess.get("metadata"), dict) else {}
    meta_plat = str(meta.get("platform") or "").strip().lower()
    if platform_filename(meta_plat):
        return meta_plat
    return ""


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


# Iceland product VPS (same host as RPT node) — paid installer store.
DEFAULT_VPS_ASSET_HOST = "82.221.101.241"
DEFAULT_VPS_ASSET_PORT = 8081
DEFAULT_VPS_ASSET_REMOTE_ROOT = "/opt/restore-privacy/paid_assets"
# HTTP path prefix on the VPS paid-asset server.
VPS_ASSET_HTTP_PREFIX = "/paid-assets"


def vps_asset_fetch_token() -> str:
    """Shared secret for status host → Iceland VPS asset fetch (never browser-facing).

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
    """Base URL for Iceland-hosted paid installers (no trailing slash).

    Override with ``RPT_VPS_ASSET_BASE`` e.g.
    ``http://82.221.101.241:8081/paid-assets``.
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
    host = os.environ.get("RPT_VPS_ASSET_HOST", DEFAULT_VPS_ASSET_HOST).strip()
    port = os.environ.get("RPT_VPS_ASSET_PORT", str(DEFAULT_VPS_ASSET_PORT)).strip()
    return f"http://{host}:{port}{VPS_ASSET_HTTP_PREFIX}"


def vps_asset_url(filename: str, *, version: str | None = None) -> str:
    """Full URL for one catalog installer on the Iceland VPS paid-asset store."""
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
    Also includes the Iceland VPS on-disk layout when status runs on that host
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
    # Iceland VPS layout (when paid fulfilment runs co-located with the node)
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
      2. Iceland VPS paid-asset HTTP store (:func:`vps_asset_url` + fetch token)
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

    # 2) Iceland VPS HTTP store (status on Render → fetch from product host)
    vps_token = vps_asset_fetch_token()
    if vps_token:
        try:
            vps_url = vps_asset_url(filename)
            headers = {
                "User-Agent": "restore-privacy-status-fulfilment",
                "X-RPT-Asset-Token": vps_token,
            }
            req = urllib.request.Request(vps_url, headers=headers)
            resp = open_url(req, timeout=120)
            length = resp.headers.get("Content-Length")
            return {
                "filename": filename,
                "content_type": content_type_for_filename(filename),
                "content_length": int(length) if length and length.isdigit() else None,
                "body": resp,
                "source": "vps",
            }
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
    """Thank-you page body: auto-start one-time download + run-as-administrator copy.

    **Exactly one** auto-start mechanism: a hidden iframe whose ``src`` is the paid
    ``/download?token=…`` path. The visible fallback anchor is **manual only** (no
    script click / meta-refresh) so if the browser blocks the iframe the grant is
    still unused and the user can click once to download.

    *purchase_id* is the durable product purchase identifier (distinct from the
    single-use download token). Buyers are **strongly advised** to note it so the
    operator can re-issue a secondary download link after software loss.

    *keygen* is the subscription unlock code (also emailed). Clients require
    licence accept then keygen entry for Connect.
    """
    link = (download_path or "").strip()
    if not link.startswith("/download"):
        raise ValueError("download_path must be a paid /download?token= path")
    if "github.com" in link.lower() or link.startswith("http"):
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
      It is <strong>not</strong> your one-time download link. If you lose the
      installer later, contact the operator with this identifier so a
      <strong>secondary download link</strong> can be recreated for you.
      Without this identifier, re-fulfilment may not be possible.
    </p>
  </div>"""
    keygen_block = ""
    if kg:
        keygen_block = f"""
  <div class="msg keygen-box" id="keygen-box" role="region"
       aria-labelledby="keygen-heading">
    <p id="keygen-heading"><strong>{_escape_html_text(KEYGEN_UNLOCK_INSTRUCTION)}</strong></p>
    <p class="keygen-value"><code id="product-keygen">{kg_esc}</code></p>
    <p class="keygen-advice" id="keygen-advice">
      Install → accept licence terms → enter this keygen in the app to unlock.
      Your monthly subscription (£2.45 per month) begins after your 7 day trial.
      If payment fails later, this keygen becomes useless and Connect locks until
      an active subscription is restored.
    </p>
  </div>"""
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
  <script>
  (function () {{
    var delayMs = 1800;
    var ent = document.getElementById("auto-entitlement-frame");
    if (!ent) return;
    var src = ent.getAttribute("data-src") || "";
    if (!src) return;
    // Defer entitlement auto-fetch so the installer iframe gets first byte first.
    setTimeout(function () {{ ent.setAttribute("src", src); }}, delayMs);
  }})();
  </script>"""
    # Emphasize Windows admin wording for .exe; still show admin phrase for all.
    admin_lead = "Please run the file as administrator."
    btn = f"Download {plat_label} package"
    return f"""
<section id="post-pay-thankyou" class="thankyou" aria-labelledby="thank-you-heading">
  <h1 id="thank-you-heading">Thank you</h1>
  <p class="msg" id="pay-success">Payment confirmed. Your <strong id="paid-platform-label">{_escape_html_text(plat_label)}</strong> installer is ready:</p>
  <p class="pkg" id="paid-package-name"><strong>{fname_esc}</strong></p>
  {purchase_block}
  {keygen_block}
  {ent_block}
  <p class="msg admin-run" id="run-as-admin-instruction">
    <strong>{_escape_html_text(admin_lead)}</strong>
    {admin}
  </p>
  <p class="msg" id="auto-download-note">please wait for your download.. packaging...</p>
  <!-- Installer first (single-use grant). Entitlement file is deferred only when
       session_id is present (script inside ent_block). No script click on package. -->
  <iframe id="auto-download-frame" src="{link_esc}" style="width:0;height:0;border:0;position:absolute"
    title="Automatic product download" aria-hidden="true"></iframe>
  <p>
    <a class="dl" id="success-download-link" href="{link_esc}"
       data-manual-download="1" data-platform="{_escape_html_text(plat)}"
       data-filename="{fname_esc}">
      { _escape_html_text(btn) } (if it did not start)
    </a>
  </p>
  <p class="msg muted">This link is one-time and expires. It only unlocks the package you paid for.
    Tip optional: <a href="https://buymeacoffee.com/rgsneddon">buymeacoffee.com/rgsneddon</a></p>
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
    single-use download tokens for the same paid purchase.
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
    "USE THIS KEYGEN TO UNLOCK YOUR RESTORE PRIVACY TRIAL"
)

# Distinct from PPI (RPT-XXXX-…) so buyers do not confuse purchase id with unlock.
KEYGEN_PREFIX = "RPT-KEY-"


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
    now: float | None = None,
) -> str:
    """Mark Checkout session as paid/active for Connect entitlement.

    *valid_until* is a unix timestamp after which Connect is no longer allowed
    (subscription period end). ``None`` means no time limit (one-time pay until
    refund/revoke).

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
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT platform, payment_intent_id, subscription_id, valid_until, keygen "
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
            conn.execute(
                """
                UPDATE connect_entitlements
                SET status = ?, platform = ?, reason = ?, updated_at = ?,
                    payment_intent_id = ?, subscription_id = ?, valid_until = ?,
                    keygen = ?
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
                    sid,
                ),
            )
        else:
            keep_keygen = normalize_keygen(keygen) if keygen else _mint_unique_keygen(conn)
            conn.execute(
                """
                INSERT INTO connect_entitlements(
                    session_id, status, platform, reason, created_at, updated_at,
                    payment_intent_id, subscription_id, valid_until, keygen
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
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
                   payment_intent_id, subscription_id, valid_until, keygen
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
        return {
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
            "connect_allowed": _entitlement_connect_allowed(status, vu_f, now=t)
            if status == ENTITLEMENT_ACTIVE
            else False,
        }
    finally:
        conn.close()


def get_connect_entitlement_by_keygen(
    keygen: str, *, now: float | None = None
) -> dict[str, Any] | None:
    """Lookup entitlement by customer keygen (subscription unlock path).

    Returns the same shape as :func:`get_connect_entitlement`. When the bound
    subscription/payment is failed/revoked or period ended, ``connect_allowed``
    is False — the keygen is useless until a new active entitlement exists.
    """
    kg = normalize_keygen(keygen)
    if not kg or not kg.startswith("RPT-KEY-"):
        return None
    init_db()
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
    return get_connect_entitlement(sid, now=now)


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


def customer_email_from_checkout_object(obj: dict[str, Any]) -> str:
    """Extract customer email from a Stripe Checkout Session object."""
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
    cust = obj.get("customer_details") or obj.get("customer")
    if isinstance(cust, dict):
        em = str(cust.get("email") or "").strip()
        if em and "@" in em:
            return em
    return ""


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
    Body always includes :data:`KEYGEN_UNLOCK_INSTRUCTION`.
    """
    to_addr = (to_email or "").strip()
    kg = normalize_keygen(keygen)
    pid = normalize_purchase_id(purchase_id) or (purchase_id or "").strip().upper()
    dl = (download_url or "").strip()
    plat = (platform or "").strip().lower()
    sid = (session_id or "").strip()
    fname = (filename or "").strip()
    subject = "Your Restore Privacy download and unlock keygen"
    body_lines = [
        "Thank you for purchasing Restore Privacy.",
        "",
        KEYGEN_UNLOCK_INSTRUCTION,
        "",
        f"Keygen: {kg}",
        f"Product purchase identifier (PPI): {pid}",
        f"Download link (one-time): {dl}",
        "",
        "Install flow: Install → accept licence terms and conditions → enter keygen → unlock.",
        "Your monthly subscription (£2.45 per month) begins after your 7 day trial.",
        "The keygen only unlocks Connect while your subscription/payment is active.",
        "If payment fails later (failed charge, refund, dispute, or subscription ends),",
        "this keygen becomes useless and the app locks until payment is active again.",
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
            "Save this email. The download link expires; the keygen stays bound to your entitlement.",
            "— Restore Privacy",
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
    """Read optional SMTP env for transactional fulfilment email."""
    host = os.environ.get("RPT_FULFILMENT_SMTP_HOST", "").strip()
    port_raw = os.environ.get("RPT_FULFILMENT_SMTP_PORT", "587").strip() or "587"
    try:
        port = int(port_raw)
    except ValueError:
        port = 587
    user = os.environ.get("RPT_FULFILMENT_SMTP_USER", "").strip()
    password = os.environ.get("RPT_FULFILMENT_SMTP_PASSWORD", "").strip()
    from_addr = os.environ.get(
        "RPT_FULFILMENT_FROM_EMAIL",
        os.environ.get("RPT_FULFILMENT_SMTP_FROM", "noreply@restoreprivacy.online"),
    ).strip()
    use_tls = os.environ.get("RPT_FULFILMENT_SMTP_TLS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
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
    """Target Stripe Payment Link / price shape for homepage trial messaging.

    Pure helper for deploy scripts + unit tests (no network). Live update uses
    Stripe API when ``STRIPE_SECRET_KEY`` is set.
    """
    return {
        "payment_link_id": DEFAULT_STRIPE_PAYMENT_LINK_ID,
        "payment_page_url": DEFAULT_STRIPE_PAYMENT_PAGE_URL,
        "price_id": DEFAULT_STRIPE_PAYMENT_LINK_PRICE_ID,
        "currency": PRICE_CURRENCY,
        "unit_amount_pence": PRICE_PENCE,
        "recurring_interval": "month",
        "trial_period_days": 7,
        "mode": "subscription",
        "homepage_trial_sentence": (
            "Your monthly subscription (£2.45 per month) begins after your 7 day trial"
        ),
    }


def payment_link_matches_trial_subscription(price_obj: dict[str, Any]) -> dict[str, Any]:
    """Check a Stripe Price object against desired £2.45/mo + trial fields.

    *price_obj* is a Stripe API Price dict (or redacted summary). Returns
    ``{ok, mismatches[], observed}`` without inventing success.
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
    trial = recurring.get("trial_period_days")
    if trial is None:
        trial = price_obj.get("trial_period_days")
    try:
        trial_i = int(trial) if trial is not None else None
    except (TypeError, ValueError):
        trial_i = None
    # Some Dashboard prices put trial on the Payment Link / subscription_data
    # rather than the Price; callers may pass trial_period_days at top level.
    if currency != want["currency"]:
        mismatches.append(f"currency:{currency!r}!={want['currency']!r}")
    if amount_i != want["unit_amount_pence"]:
        mismatches.append(f"unit_amount:{amount_i!r}!={want['unit_amount_pence']}")
    if interval != want["recurring_interval"]:
        mismatches.append(f"interval:{interval!r}!={want['recurring_interval']!r}")
    # trial may live on Subscription Data of the Payment Link
    link_trial = price_obj.get("payment_link_trial_period_days")
    try:
        link_trial_i = int(link_trial) if link_trial is not None else None
    except (TypeError, ValueError):
        link_trial_i = None
    effective_trial = trial_i if trial_i is not None else link_trial_i
    if effective_trial != want["trial_period_days"]:
        mismatches.append(
            f"trial_period_days:{effective_trial!r}!={want['trial_period_days']}"
        )
    observed = {
        "currency": currency,
        "unit_amount": amount_i,
        "interval": interval,
        "trial_period_days": effective_trial,
        "price_id": str(price_obj.get("id") or ""),
        "type": str(price_obj.get("type") or ""),
    }
    return {"ok": len(mismatches) == 0, "mismatches": mismatches, "observed": observed}


def send_fulfilment_email(
    payload: dict[str, Any],
    *,
    transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Send fulfilment email via SMTP (or injected *transport* for tests).

    Returns ``{ok, sent, error?, skipped?}``. Without SMTP host configured and
    without a transport, returns ok with ``skipped=True`` (payload still built
    by caller) so checkout fulfilment never fails on missing mail credentials.
    """
    if not isinstance(payload, dict):
        return {"ok": False, "sent": False, "error": "bad_payload"}
    to_addr = str(payload.get("to") or "").strip()
    if not to_addr or "@" not in to_addr:
        return {"ok": False, "sent": False, "error": "missing_to_email"}
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
        msg["Subject"] = str(payload.get("subject") or "Your Restore Privacy download")
        msg["From"] = str(cfg["from_addr"])
        msg["To"] = to_addr
        msg.set_content(str(payload.get("body") or ""))
        with smtplib.SMTP(str(cfg["host"]), int(cfg["port"]), timeout=30) as smtp:
            if cfg.get("use_tls"):
                smtp.starttls()
            user = str(cfg.get("user") or "")
            password = str(cfg.get("password") or "")
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        return {"ok": True, "sent": True, "skipped": False}
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
    """After paid grant: ensure keygen, build email payload, attempt send.

    Returns dict with keygen, purchase_id, download_url, email payload, send result.
    """
    sid = (session_id or "").strip()
    kg = normalize_keygen(keygen) if keygen else ""
    if sid and not kg:
        kg = assign_keygen_for_session(sid)
    pid = normalize_purchase_id(purchase_id) if purchase_id else ""
    if not pid and token:
        pid = purchase_id_for_token(token) or ""
    base = (base_url if base_url is not None else public_base_url()).rstrip("/")
    path = f"/download?token={token}" if token else ""
    download_url = f"{base}{path}" if path else ""
    email_payload = build_fulfilment_email_payload(
        to_email=customer_email,
        keygen=kg,
        purchase_id=pid or "",
        download_url=download_url,
        platform=platform,
        session_id=sid,
        filename=filename,
    )
    send_result = send_fulfilment_email(email_payload, transport=transport)
    return {
        "keygen": kg,
        "purchase_id": pid or email_payload.get("purchase_id") or "",
        "download_url": download_url,
        "download_path": path,
        "email": email_payload,
        "send": send_result,
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
        activate_connect_entitlement(
            sid,
            subscription_id=sub_id,
            valid_until=pe,
            now=t,
        )
        if pe is not None:
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
    """Create a single-use expiring download token bound to a **current catalog** asset.

    Re-resolves the platform to the live catalog filename so callers cannot mint
    a stale version string. Raises ``ValueError`` if the platform is unknown.

    Assigns a durable :func:`generate_purchase_id` when *purchase_id* is omitted
    (new paid purchase). Pass an existing id when re-issuing a secondary download
    for the same paid purchase.
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


def admin_mint_download_for_platform(
    platform: str,
    *,
    now: float | None = None,
    base_url: str | None = None,
    ttl_sec: int = TOKEN_TTL_SEC,
) -> dict[str, Any]:
    """Admin failsafe: mint a live single-use download for a catalog platform.

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


def seed_test_purchase_enabled() -> bool:
    """True only when operator explicitly opts into local/staging seed tools.

    Requires ``RPT_ADMIN_SEED_PURCHASE=1`` (or ``true``/``yes``/``on``).
    Never on by default — production must set the env deliberately.
    Seeded grants still require a single-use ``/download?token=`` (no free unlock).
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

    Creates a durable product purchase identifier + single-use download token for
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
    """Mint a **new** single-use download token for a paid purchase_id.

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
    return {
        "token": row["token"],
        "filename": row["filename"],
        "platform": row["platform"],
        "session_id": row["session_id"],
        "amount_pence": row["amount_pence"],
        "currency": row["currency"],
        "url": asset_download_url(row["filename"]),
        "purchase_id": pid,
        "download_path": f"/download?token={row['token']}",
    }


def lookup_download_token(
    token: str, *, now: float | None = None
) -> dict[str, Any] | None:
    """Return grant if valid, unused, and non-expired — **does not** mark used.

    Use before opening the installer so a failed proxy does not burn the grant.
    Call :func:`consume_download_token` only after the asset is opened successfully.
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
        if row["status"] != "granted" or row["used_at"] is not None:
            return None
        if float(row["expires_at"]) < t:
            return None
        return _grant_dict_from_row(row)
    finally:
        conn.close()


def consume_download_token(token: str, *, now: float | None = None) -> bool:
    """Mark a still-valid grant as used. Returns True if this call consumed it."""
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
        if row["status"] != "granted" or row["used_at"] is not None:
            return False
        if float(row["expires_at"]) < t:
            return False
        cur = conn.execute(
            "UPDATE grants SET used_at = ?, status = 'used' "
            "WHERE token = ? AND status = 'granted' AND used_at IS NULL",
            (t, tok),
        )
        return cur.rowcount == 1
    finally:
        conn.close()


def redeem_download_token(
    token: str, *, now: float | None = None
) -> dict[str, Any] | None:
    """Lookup + consume in one step (legacy helpers / tests).

    HTTP /download should use :func:`lookup_download_token` then
    :func:`consume_download_token` only after :func:`open_release_asset` succeeds.
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


def check_fulfilment_ready(*, platform: str | None = None) -> dict[str, Any]:
    """Probe that at least one catalog installer is openable (local or API).

    Closes the body immediately — used for production readiness evidence.
    Includes non-secret flags so operators can confirm VPS token match without
    printing the secret (``vps_token_configured``).

    When *platform* is set (e.g. ``macos``), only that catalog package is probed
    so live-test evidence can pin the paid macOS zip.
    """
    vps_tok = bool(vps_asset_fetch_token())
    vps_base = vps_asset_base_url()
    meta: dict[str, Any] = {
        "vps_token_configured": vps_tok,
        "vps_asset_base": vps_base,
        "github_token_configured": bool(github_auth_token()),
    }
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
            "Set RPT_ASSET_FETCH_TOKEN + host installers on Iceland VPS "
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
    """
    init_db()
    conn = _connect()
    try:
        sql = """
            SELECT token, filename, platform, session_id, amount_pence, currency,
                   created_at, expires_at, used_at, status, purchase_id
            FROM grants ORDER BY created_at DESC
        """
        if limit is None:
            rows = conn.execute(sql).fetchall()
        else:
            lim = max(0, int(limit))
            rows = conn.execute(sql + " LIMIT ?", (lim,)).fetchall()
        out = []
        for r in rows:
            d = {k: r[k] for k in r.keys()}
            if d.get("purchase_id"):
                d["purchase_id"] = (
                    normalize_purchase_id(str(d["purchase_id"])) or d["purchase_id"]
                )
            out.append(d)
        return out
    finally:
        conn.close()


def list_all_grants() -> list[dict[str, Any]]:
    """Full grant history for operator admin (no silent row drop-off)."""
    return list_recent_grants(limit=None)


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


def create_checkout_session(
    platform: str,
    *,
    base_url: str | None = None,
    http_post: HttpPostFn | None = None,
) -> dict[str, Any]:
    """Create a Stripe Checkout Session for one package at £2.45 GBP.

    Returns dict with keys: id, url (Stripe-hosted), platform, filename, amount_pence.
    Raises ValueError on bad platform or missing Stripe config / API failure.
    """
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
    cancel = f"{base}{DEFAULT_CANCEL_PATH}?platform={urllib.parse.quote(platform)}"
    creq = CheckoutRequest(
        platform=platform,
        filename=filename,
        success_url=success,
        cancel_url=cancel,
    )
    body = build_checkout_form_body(creq)

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
        "amount_pence": PRICE_PENCE,
        "currency": PRICE_CURRENCY,
    }


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
) -> str | None:
    """On checkout.session.completed, mint a download token. Returns token or None.

    Supports server Checkout (metadata platform/filename/amount) and Payment Link
    pays that set ``client_reference_id`` to the requested platform via the
    download-button URL query.

    **Only if paid:** ``payment_status`` must be ``paid`` or ``no_payment_required``.
    **Full product price:** resolved amount must equal ``PRICE_PENCE`` (245) — underpay
    / zero / missing amount never mint a grant.

    Also mints a unique **keygen** bound to the connect entitlement and attempts
    the customer fulfilment email (keygen + PPI + download link). Email send is
    best-effort (SMTP optional); grant + keygen still succeed without mail.
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
    platform = str(
        meta.get("platform") or obj.get("client_reference_id") or ""
    ).strip().lower()
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
    # Full price (245) always OK. £0 / no_payment_required allowed only with a
    # subscription id (7-day trial then monthly) so underpay one-time never mints.
    amount_ok = amount is not None and amount == PRICE_PENCE
    trial_ok = bool(subscription_id) and (
        payment_status == "no_payment_required"
        or amount == 0
        or amount is None
    )
    if not amount_ok and not trial_ok:
        return None
    currency = str(meta.get("currency") or obj.get("currency") or PRICE_CURRENCY).strip().lower()
    if currency and currency != PRICE_CURRENCY:
        return None
    # Subscription checkout: usable through first period end when provided
    valid_until = None
    if subscription_id:
        # session object may not include period; leave open until subscription.updated
        valid_until = None
    token = mint_download_token(
        filename=filename,
        platform=platform,
        session_id=session_id,
        amount_pence=PRICE_PENCE,
        currency=PRICE_CURRENCY,
    )
    # Successful paid session → Connect entitlement active + unique keygen
    keygen = ""
    if session_id:
        keygen = activate_connect_entitlement(
            session_id,
            platform=platform,
            payment_intent_id=payment_intent_id,
            subscription_id=subscription_id,
            valid_until=valid_until,
        ) or ""
    # Customer fulfilment email: keygen + PPI + one-time download URL
    try:
        cust_email = customer_email_from_checkout_object(obj)
        if token and (cust_email or keygen):
            fulfil_checkout_with_email(
                token=token,
                session_id=session_id,
                platform=platform,
                filename=filename,
                customer_email=cust_email,
                keygen=keygen,
                transport=email_transport,
            )
    except Exception:  # noqa: BLE001
        # Never block grant mint on email failure
        pass
    return token


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
