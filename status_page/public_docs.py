"""Public documents and how-to-buy pages served by the Render status host.

Stable same-origin paths (no GitHub dependency for public readers):

| Path | Document |
|------|----------|
| ``/how-to-buy`` | How to pay and get a one-time download |
| ``/README.md`` | Product README |
| ``/LICENSE`` | End-user licence (MIT) |
| ``/PRIVACY_POLICY.md`` | Privacy policy |
| ``/AUDIT.md`` | Security audit |
| ``/CREDITS.md`` | Credits / third-party components |
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STATUS_DIR = Path(__file__).resolve().parent
REPO_ROOT = STATUS_DIR.parent
PUBLIC_DIR = STATUS_DIR / "public"

# Production status origin (override with RPT_PUBLIC_BASE_URL when not localhost).
DEFAULT_STATUS_ORIGIN = "https://restore-privacy-status.onrender.com"

HOW_TO_BUY_PATH = "/how-to-buy"
README_PATH = "/README.md"
LICENSE_PATH = "/LICENSE"
PRIVACY_PATH = "/PRIVACY_POLICY.md"
AUDIT_PATH = "/AUDIT.md"
CREDITS_PATH = "/CREDITS.md"


@dataclass(frozen=True)
class PublicDoc:
    """One public document served by the status page."""

    id: str
    path: str
    title: str
    filename: str
    content_type: str = "text/markdown; charset=utf-8"
    aliases: tuple[str, ...] = ()


PUBLIC_DOCS: tuple[PublicDoc, ...] = (
    PublicDoc(
        id="readme",
        path=README_PATH,
        title="README — Restore Privacy",
        filename="README.md",
        aliases=("/readme.md", "/docs/README.md"),
    ),
    PublicDoc(
        id="licence",
        path=LICENSE_PATH,
        title="Licence — Restore Privacy",
        filename="LICENSE",
        content_type="text/plain; charset=utf-8",
        aliases=("/licence", "/LICENSE.txt", "/docs/LICENSE"),
    ),
    PublicDoc(
        id="privacy",
        path=PRIVACY_PATH,
        title="Privacy policy — Restore Privacy",
        filename="PRIVACY_POLICY.md",
        aliases=("/privacy", "/privacy-policy", "/docs/PRIVACY_POLICY.md"),
    ),
    PublicDoc(
        id="audit",
        path=AUDIT_PATH,
        title="Security audit — Restore Privacy",
        filename="AUDIT.md",
        aliases=("/audit.md", "/docs/AUDIT.md", "/docs/audit.md"),
    ),
    PublicDoc(
        id="credits",
        path=CREDITS_PATH,
        title="Credits — Restore Privacy",
        filename="CREDITS.md",
        aliases=("/credits", "/docs/CREDITS.md"),
    ),
)


def production_status_origin() -> str:
    """Public base URL for absolute status-origin document links."""
    raw = os.environ.get("RPT_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if raw and not raw.startswith("http://127.0.0.1") and not raw.startswith(
        "http://localhost"
    ):
        return raw
    return DEFAULT_STATUS_ORIGIN


def public_doc_by_path(url_path: str) -> PublicDoc | None:
    """Resolve a request path to a PublicDoc (exact path or alias)."""
    p = (url_path or "").split("?", 1)[0].rstrip("/") or "/"
    # normalize: keep leading slash; LICENSE has no extension
    if not p.startswith("/"):
        p = "/" + p
    for doc in PUBLIC_DOCS:
        candidates = {doc.path.rstrip("/"), *(a.rstrip("/") for a in doc.aliases)}
        # Also accept path without leading issues
        if p in candidates or p.lower() in {c.lower() for c in candidates}:
            return doc
    return None


def public_doc_absolute_url(doc_or_path: PublicDoc | str) -> str:
    """Absolute URL on the status host for a document path."""
    if isinstance(doc_or_path, PublicDoc):
        path = doc_or_path.path
    else:
        path = str(doc_or_path)
    if not path.startswith("/"):
        path = "/" + path
    return production_status_origin().rstrip("/") + path


def public_docs_catalog() -> list[dict[str, str]]:
    """Operator/public catalog of document URLs (pure, no secrets)."""
    out: list[dict[str, str]] = []
    for doc in PUBLIC_DOCS:
        out.append(
            {
                "id": doc.id,
                "path": doc.path,
                "title": doc.title,
                "url": public_doc_absolute_url(doc),
            }
        )
    out.append(
        {
            "id": "how-to-buy",
            "path": HOW_TO_BUY_PATH,
            "title": "How to buy",
            "url": public_doc_absolute_url(HOW_TO_BUY_PATH),
        }
    )
    return out


def _candidate_paths(filename: str) -> list[Path]:
    install = Path(os.environ.get("RPT_INSTALL_ROOT", "/opt/restore-privacy"))
    return [
        PUBLIC_DIR / filename,
        STATUS_DIR / filename,
        REPO_ROOT / filename,
        install / filename,
    ]


def load_public_document_bytes(filename: str, *, min_size: int = 20) -> bytes | None:
    """Load a public document from status_page/public, status_page, or repo root."""
    for path in _candidate_paths(filename):
        try:
            if path.is_file() and path.stat().st_size >= min_size:
                return path.read_bytes()
        except OSError:
            continue
    return None


def document_bytes_for_path(url_path: str) -> tuple[bytes, str, str] | None:
    """Return (body, content_type, title) for a public doc path, or None."""
    doc = public_doc_by_path(url_path)
    if doc is None:
        return None
    data = load_public_document_bytes(doc.filename)
    if data is None:
        return None
    return data, doc.content_type, doc.title


def render_how_to_buy_html() -> bytes:
    """Public how-to-buy page HTML (no admin, no secrets)."""
    # Local imports avoid cycles with payments ↔ downloads.
    from payments import (
        PRICE_LABEL,
        PRICE_PENCE,
        stripe_payment_page_url,
        stripe_webhook_endpoint_url,
    )

    pay = stripe_payment_page_url()
    claim = public_doc_absolute_url("/download/success")
    home = production_status_origin()
    webhook = stripe_webhook_endpoint_url(production=True)
    docs = public_docs_catalog()
    doc_lis = "\n".join(
        f'    <li><a href="{d["path"]}">{_escape(d["title"])}</a> '
        f'(<code>{_escape(d["url"])}</code>)</li>'
        for d in docs
        if d["id"] != "how-to-buy"
    )
    body = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>How to buy — Restore Privacy</title>
<style>
body{{margin:0;padding:1.5rem;font-family:system-ui,sans-serif;background:#0b0f14;color:#e8eef5;
max-width:42rem;margin-inline:auto;line-height:1.5}}
a{{color:#93c5fd}} h1{{font-size:1.35rem}} h2{{font-size:1.05rem;margin-top:1.5rem}}
code{{font-size:0.88rem;word-break:break-all;background:#111827;padding:0.1rem 0.35rem;border-radius:4px}}
ol{{padding-left:1.25rem}} .card{{background:#111827;border-radius:12px;padding:1rem 1.15rem;margin:1rem 0}}
.muted{{opacity:0.8;font-size:0.95rem}}
</style></head><body>
<p><a href="/">← Status &amp; downloads</a></p>
<h1 id="how-to-buy-heading">How to buy Restore Privacy</h1>
<p class="muted">Paid package download ({_escape(PRICE_LABEL)} / {PRICE_PENCE} pence GBP).
No free permanent installer buttons on the status page.</p>

<div class="card" id="how-to-buy-steps">
<h2>Steps</h2>
<ol>
  <li>Open the status page: <a href="{_escape(home)}">{_escape(home)}</a></li>
  <li>Choose your platform under <strong>Download client</strong>.
      Each button opens the Stripe payment page with your package identity
      (<code>client_reference_id</code>).</li>
  <li>Pay on Stripe: <a id="how-to-buy-payment-page" href="{_escape(pay)}"
      rel="noopener noreferrer" target="_blank">{_escape(pay)}</a></li>
  <li>After payment succeeds, open the one-time download from the success page
      (<code>{_escape(claim)}?session_id=…</code>) or contact support with your
      Checkout session id. The link works <strong>once</strong> and expires.</li>
</ol>
<p class="muted">Webhook fulfilment uses
<code>{_escape(webhook)}</code> with event <code>checkout.session.completed</code>
(already configured on the status host).</p>
</div>

<div class="card" id="how-to-buy-public-docs">
<h2>Public documents on this site</h2>
<ul id="public-docs-list">
{doc_lis}
</ul>
</div>

<p class="muted"><a href="{HOW_TO_BUY_PATH}">How to buy</a> ·
<a href="{LICENSE_PATH}">Licence</a> ·
<a href="{PRIVACY_PATH}">Privacy</a> ·
<a href="{AUDIT_PATH}">Security audit</a> ·
<a href="{README_PATH}">README</a></p>
</body></html>
"""
    return body.encode("utf-8")


def render_public_nav_links_html() -> str:
    """Nav fragment: licence · privacy · audit · readme · how-to-buy (same-origin)."""
    items = (
        ("LICENCE", LICENSE_PATH, "licence-link"),
        ("PRIVACY POLICY", PRIVACY_PATH, "privacy-link"),
        ("SECURITY AUDIT", AUDIT_PATH, "audit-link"),
        ("README", README_PATH, "readme-link"),
        ("HOW TO BUY", HOW_TO_BUY_PATH, "how-to-buy-link"),
    )
    anchors = []
    for label, path, el_id in items:
        anchors.append(
            f'<a class="doc-link" id="{el_id}" href="{path}">{label}</a>'
        )
    joined = '<span class="doc-sep" aria-hidden="true"> · </span>'.join(anchors)
    return (
        f'  <nav class="doc-links" id="doc-links" aria-label="Legal and product documents">'
        f"{joined}</nav>"
    )


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
