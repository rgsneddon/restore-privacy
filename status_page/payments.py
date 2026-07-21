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


def stripe_secret_key() -> str:
    return os.environ.get("STRIPE_SECRET_KEY", "").strip()


def stripe_webhook_secret() -> str:
    return os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()


def stripe_price_id() -> str:
    """Optional **one-time** Price id for package Checkout only.

    Prefer ``STRIPE_CHECKOUT_PRICE_ID`` / ``STRIPE_ONE_TIME_PRICE_ID``.

    Legacy ``STRIPE_PRICE_ID`` is **ignored by default** for Checkout because operators
    often paste a Payment Link **recurring** price here, which Stripe rejects with
    mode=payment. Set ``STRIPE_ALLOW_LEGACY_PRICE_ID=1`` to use ``STRIPE_PRICE_ID``
    only when that price is known one-time.
    """
    for key in ("STRIPE_CHECKOUT_PRICE_ID", "STRIPE_ONE_TIME_PRICE_ID"):
        raw = os.environ.get(key, "").strip()
        if raw:
            return raw
    if os.environ.get("STRIPE_ALLOW_LEGACY_PRICE_ID", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return os.environ.get("STRIPE_PRICE_ID", "").strip()
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
    "customer.subscription.deleted",
)


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
    """
    base = production_public_base_url().rstrip("/")
    return f"{base}{DEFAULT_SUCCESS_PATH}?session_id={{CHECKOUT_SESSION_ID}}"


def stripe_webhook_operator_guidance() -> dict[str, object]:
    """Non-secret fields for admin/docs: endpoint URL + required events."""
    return {
        "endpoint_url": stripe_webhook_endpoint_url(production=True),
        "path": STRIPE_WEBHOOK_PATH,
        "events": list(STRIPE_WEBHOOK_EVENTS),
        "primary_event": STRIPE_WEBHOOK_EVENTS[0],
        "method": "POST",
        "note": (
            "Add this URL in Stripe Dashboard → Developers → Webhooks "
            "(event: checkout.session.completed). Copy the signing secret into "
            "STRIPE_WEBHOOK_SECRET (Render env). Set Payment Link after_completion "
            "redirect to production_success_return_url(). Never commit the secret."
        ),
        "success_return_url": production_success_return_url(),
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


def open_release_asset(
    filename: str,
    *,
    urlopen: Callable[..., Any] | None = None,
) -> dict[str, Any] | None:
    """Open installer bytes for a **paid** redeem (proxy/stream, not free public redirect).

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
    if filename not in catalog_filenames():
        return None
    open_url = urlopen or urllib.request.urlopen

    # 1) Local disk (status assets, monorepo releases, VPS paid_assets when co-located)
    for base in asset_search_dirs():
        path = base / filename
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
) -> str:
    """Thank-you page body: auto-start one-time download + run-as-administrator copy.

    **Exactly one** auto-start mechanism: a hidden iframe whose ``src`` is the paid
    ``/download?token=…`` path. The visible fallback anchor is **manual only** (no
    script click / meta-refresh) so if the browser blocks the iframe the grant is
    still unused and the user can click once to download.
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
    ent_block = ""
    if sid:
        ent_block = f"""
  <p class="msg entitlement-note" id="connect-entitlement-note">
    <strong>Connect entitlement:</strong> payment session
    <code id="connect-session-id">{sid_esc}</code> is active.
    If payment fails or is refunded later, Connect is cancelled for this install.
  </p>
  <p class="msg" id="entitlement-import-hint">
    In the app, save this session id under product data as payment entitlement
    (or re-download after a new successful payment).
  </p>"""
    # Emphasize Windows admin wording for .exe; still show admin phrase for all.
    admin_lead = "Please run the file as administrator."
    btn = f"Download {plat_label} package"
    return f"""
<section id="post-pay-thankyou" class="thankyou" aria-labelledby="thank-you-heading">
  <h1 id="thank-you-heading">Thank you</h1>
  <p class="msg" id="pay-success">Payment confirmed. Your <strong id="paid-platform-label">{_escape_html_text(plat_label)}</strong> installer is ready:</p>
  <p class="pkg" id="paid-package-name"><strong>{fname_esc}</strong></p>
  {ent_block}
  <p class="msg admin-run" id="run-as-admin-instruction">
    <strong>{_escape_html_text(admin_lead)}</strong>
    {admin}
  </p>
  <p class="msg" id="auto-download-note">Your download should start automatically…</p>
  <!-- Sole auto-start: one iframe request to the single-use grant path. -->
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
            """
        )
    finally:
        conn.close()


# --- Connect entitlement (payment success → may Connect; failure → block) -----

ENTITLEMENT_ACTIVE = "active"
ENTITLEMENT_FAILED = "failed"
ENTITLEMENT_REVOKED = "revoked"


def activate_connect_entitlement(
    session_id: str,
    *,
    platform: str = "",
    now: float | None = None,
) -> None:
    """Mark Checkout session as paid/active for Connect entitlement."""
    sid = (session_id or "").strip()
    if not sid:
        return
    init_db()
    t = now if now is not None else time.time()
    plat = (platform or "").strip().lower()
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT platform FROM connect_entitlements WHERE session_id = ?",
            (sid,),
        )
        row = cur.fetchone()
        if row:
            keep_plat = plat or (row["platform"] or "")
            conn.execute(
                """
                UPDATE connect_entitlements
                SET status = ?, platform = ?, reason = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (ENTITLEMENT_ACTIVE, keep_plat, "payment_succeeded", t, sid),
            )
        else:
            conn.execute(
                """
                INSERT INTO connect_entitlements(
                    session_id, status, platform, reason, created_at, updated_at
                ) VALUES (?,?,?,?,?,?)
                """,
                (sid, ENTITLEMENT_ACTIVE, plat, "payment_succeeded", t, t),
            )
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
    finally:
        conn.close()
    return True


def get_connect_entitlement(session_id: str) -> dict[str, Any] | None:
    """Return entitlement row for session_id, or None if unknown."""
    sid = (session_id or "").strip()
    if not sid:
        return None
    init_db()
    conn = _connect()
    try:
        cur = conn.execute(
            """
            SELECT session_id, status, platform, reason, created_at, updated_at
            FROM connect_entitlements WHERE session_id = ?
            """,
            (sid,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "session_id": row["session_id"],
            "status": row["status"],
            "platform": row["platform"] or "",
            "reason": row["reason"] or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "connect_allowed": row["status"] == ENTITLEMENT_ACTIVE,
        }
    finally:
        conn.close()


def connect_entitlement_allows(session_id: str) -> bool:
    ent = get_connect_entitlement(session_id)
    if not ent:
        return False
    return bool(ent.get("connect_allowed"))


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
    # charge.payment_intent is pi_…; look up grants by payment metadata later
    for key in ("checkout_session", "session"):
        nested = obj.get(key)
        if isinstance(nested, str) and nested.startswith("cs_"):
            return nested
        if isinstance(nested, dict):
            nid = str(nested.get("id") or "")
            if nid.startswith("cs_"):
                return nid
    return oid if oid.startswith("cs_") else ""


def process_payment_failure_event(event: dict[str, Any]) -> str | None:
    """On failure/refund/dispute webhooks, revoke Connect entitlement.

    Returns session_id when revoked, else None.
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
        "customer.subscription.deleted",
    }
    if etype not in fail_types:
        return None
    obj = event.get("data", {}).get("object") or {}
    if not isinstance(obj, dict):
        return None
    session_id = _session_id_from_stripe_object(obj)
    # Also try payment_status on session objects
    if not session_id and etype.startswith("checkout.session"):
        session_id = str(obj.get("id") or "")
    if not session_id:
        # Fallback: revoke by matching grants payment intent metadata unavailable
        return None
    # Unpaid completed sessions should not stay active
    if etype == "checkout.session.completed":
        return None
    reason = etype
    if etype == "charge.refunded":
        status = ENTITLEMENT_REVOKED
    else:
        status = ENTITLEMENT_FAILED
    revoke_connect_entitlement(session_id, reason=reason, status=status)
    return session_id


def mint_download_token(
    *,
    filename: str,
    platform: str,
    session_id: str | None,
    amount_pence: int = PRICE_PENCE,
    currency: str = PRICE_CURRENCY,
    ttl_sec: int = TOKEN_TTL_SEC,
    now: float | None = None,
) -> str:
    """Create a single-use expiring download token bound to a **current catalog** asset.

    Re-resolves the platform to the live catalog filename so callers cannot mint
    a stale version string. Raises ``ValueError`` if the platform is unknown.
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
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO grants(
                token, filename, platform, session_id, amount_pence, currency,
                created_at, expires_at, used_at, status
            ) VALUES (?,?,?,?,?,?,?,?,NULL,'granted')
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
            ),
        )
    finally:
        conn.close()
    return token


def _grant_dict_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "token": row["token"],
        "filename": row["filename"],
        "platform": row["platform"],
        "session_id": row["session_id"],
        "amount_pence": row["amount_pence"],
        "currency": row["currency"],
        "url": asset_download_url(row["filename"]),
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


def check_fulfilment_ready() -> dict[str, Any]:
    """Probe that at least one catalog installer is openable (local or API).

    Closes the body immediately — used for production readiness evidence.
    Includes non-secret flags so operators can confirm VPS token match without
    printing the secret (``vps_token_configured``).
    """
    vps_tok = bool(vps_asset_fetch_token())
    vps_base = vps_asset_base_url()
    meta: dict[str, Any] = {
        "vps_token_configured": vps_tok,
        "vps_asset_base": vps_base,
    }
    for asset in available_downloads():
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
            "or set RPT_GITHUB_TOKEN"
        ),
    }
    out.update(meta)
    return out


def list_recent_grants(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT token, filename, platform, session_id, amount_pence, currency,
                   created_at, expires_at, used_at, status
            FROM grants ORDER BY created_at DESC LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        out = []
        for r in rows:
            out.append({k: r[k] for k in r.keys()})
        return out
    finally:
        conn.close()


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
                   created_at, expires_at, used_at, status
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
        return {
            "token": row["token"],
            "filename": row["filename"],
            "platform": row["platform"],
            "session_id": row["session_id"],
            "amount_pence": row["amount_pence"],
            "currency": row["currency"],
            "status": row["status"],
            "used_at": row["used_at"],
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


def process_checkout_completed_event(event: dict[str, Any]) -> str | None:
    """On checkout.session.completed, mint a download token. Returns token or None.

    Supports server Checkout (metadata platform/filename/amount) and Payment Link
    pays that set ``client_reference_id`` to the requested platform via the
    download-button URL query.

    **Only if paid:** ``payment_status`` must be ``paid`` or ``no_payment_required``.
    **Full product price:** resolved amount must equal ``PRICE_PENCE`` (245) — underpay
    / zero / missing amount never mint a grant.
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
    if amount is None or amount != PRICE_PENCE:
        return None
    currency = str(meta.get("currency") or obj.get("currency") or "").strip().lower()
    if currency != PRICE_CURRENCY:
        return None
    session_id = str(obj.get("id") or "")
    token = mint_download_token(
        filename=filename,
        platform=platform,
        session_id=session_id,
        amount_pence=PRICE_PENCE,
        currency=PRICE_CURRENCY,
    )
    # Successful paid session → Connect entitlement active
    if session_id:
        activate_connect_entitlement(session_id, platform=platform)
    return token


def handle_stripe_webhook(
    payload: bytes,
    sig_header: str,
    *,
    secret: str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Verify signature; grant token on paid checkout; revoke on payment failure.

    Returns {ok, granted, token?, revoked?, session_id?, error?}.
    """
    wh_secret = (secret if secret is not None else stripe_webhook_secret()).strip()
    if not verify_stripe_signature(payload, sig_header, wh_secret, now=now):
        return {"ok": False, "granted": False, "error": "invalid_signature"}
    try:
        event = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"ok": False, "granted": False, "error": "bad_json"}
    token = process_checkout_completed_event(event)
    if token:
        return {"ok": True, "granted": True, "token": token, "revoked": False}
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
