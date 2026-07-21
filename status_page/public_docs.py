"""Public documents and how-to-buy pages served by the public status host (restoreprivacy.online).

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
DEFAULT_STATUS_ORIGIN = "https://restoreprivacy.online"

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
    # Browser responses are HTML shells; raw source remains on disk as md/plain.
    content_type: str = "text/html; charset=utf-8"
    plain: bool = False  # True for LICENSE-style plain text (preformatted)
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
        plain=True,
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
    # How-to-buy page may still exist at HOW_TO_BUY_PATH; it is not listed in
    # public chrome / catalog link surfaces.
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


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# Package RAG solid-colour cells (AUDIT STATE column) — upgrade emoji to CSS boxes
_RAG_SWATCH_MAP: dict[str, tuple[str, str]] = {
    "🟩": ("rag-green", "Green"),
    "🟧": ("rag-amber", "Amber"),
    "🟥": ("rag-red", "Red"),
}


def rag_swatch_html(emoji_or_state: str) -> str | None:
    """Safe solid colour box HTML for a package RAG state emoji, or None."""
    key = (emoji_or_state or "").strip()
    if key in _RAG_SWATCH_MAP:
        css, label = _RAG_SWATCH_MAP[key]
        return (
            f'<span class="rag-swatch {css}" title="{label}" '
            f'role="img" aria-label="{label}"></span>'
        )
    return None


def _inline_format(escaped_line: str) -> str:
    """Limited inline markdown on already-escaped text (safe: no raw HTML)."""
    import re

    # Links: [label](url) — only http(s) and relative paths
    def link_sub(m: re.Match[str]) -> str:
        label, url = m.group(1), m.group(2)
        if url.startswith(("http://", "https://", "/")):
            return f'<a href="{url}">{label}</a>'
        return m.group(0)

    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_sub, escaped_line)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    # Standalone RAG emoji → solid colour box (after escape; emoji unchanged)
    for emoji, (css, label) in _RAG_SWATCH_MAP.items():
        if emoji in s:
            box = (
                f'<span class="rag-swatch {css}" title="{label}" '
                f'role="img" aria-label="{label}"></span>'
            )
            s = s.replace(emoji, box)
    return s


def _format_table_cell(raw_cell: str, *, header: bool = False) -> str:
    """Format one table cell; pure RAG swatch cells get centered solid fill."""
    stripped = (raw_cell or "").strip()
    box = rag_swatch_html(stripped)
    if box is not None and not header:
        return f'<div class="rag-cell">{box}</div>'
    # Platform icon + label (emoji + optional markdown bold name)
    import re

    plat = re.match(
        r"^(🪟|🐧|🍎|📱|🤖|📦)\s+(\*\*)?(.+?)(\*\*)?$",
        stripped,
    )
    if plat and not header:
        icon, _, name, _ = plat.group(1), plat.group(2), plat.group(3), plat.group(4)
        return (
            f'<span class="plat-icon" aria-hidden="true">{icon}</span>'
            f"<strong>{_escape(name.strip())}</strong>"
        )
    return _inline_format(_escape(raw_cell))


def markdownish_to_html(text: str) -> str:
    """Conservative markdown → HTML for product docs (escape-first, no script)."""
    import re

    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    in_ul = False
    in_ol = False
    in_table = False
    table_is_pkg_rag = False

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    def close_table() -> None:
        nonlocal in_table, table_is_pkg_rag
        if in_table:
            out.append("</tbody></table>")
            in_table = False
            table_is_pkg_rag = False

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        # fenced code
        if stripped.startswith("```"):
            close_lists()
            close_table()
            i += 1
            code_lines: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            out.append(
                "<pre class=\"doc-code\"><code>"
                + _escape("\n".join(code_lines))
                + "</code></pre>"
            )
            continue

        if not stripped:
            close_lists()
            close_table()
            i += 1
            continue

        # horizontal rule
        if re.fullmatch(r"-{3,}|_{3,}|\*{3,}", stripped):
            close_lists()
            close_table()
            out.append("<hr/>")
            i += 1
            continue

        # headings
        hm = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if hm:
            close_lists()
            close_table()
            level = len(hm.group(1))
            out.append(
                f"<h{level}>{_inline_format(_escape(hm.group(2)))}</h{level}>"
            )
            i += 1
            continue

        # table row
        if stripped.startswith("|") and stripped.endswith("|"):
            close_lists()
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            # separator row |---|---|
            if all(re.fullmatch(r":?-+:?", c.replace(" ", "")) for c in cells if c):
                i += 1
                continue
            if not in_table:
                # Installer package AUDIT STATE table: wide Package/State + platform icons
                header_join = " ".join(cells).lower()
                table_is_pkg_rag = (
                    "audit state" in header_join and "package" in header_join
                )
                tclass = "doc-table pkg-rag" if table_is_pkg_rag else "doc-table"
                out.append(f'<table class="{tclass}"><tbody>')
                in_table = True
                # first row as header when next is separator
                next_is_sep = False
                if i + 1 < len(lines):
                    nxt = lines[i + 1].strip()
                    if nxt.startswith("|") and nxt.endswith("|"):
                        ncells = [c.strip() for c in nxt.strip("|").split("|")]
                        next_is_sep = all(
                            re.fullmatch(r":?-+:?", c.replace(" ", ""))
                            for c in ncells
                            if c
                        )
                tag = "th" if next_is_sep else "td"
            else:
                tag = "td"
            cells_html = "".join(
                f"<{tag}>{_format_table_cell(c, header=(tag == 'th'))}</{tag}>"
                for c in cells
            )
            out.append(f"<tr>{cells_html}</tr>")
            i += 1
            continue
        else:
            close_table()

        # unordered list
        um = re.match(r"^[-*+]\s+(.*)$", stripped)
        if um:
            close_table()
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{_inline_format(_escape(um.group(1)))}</li>")
            i += 1
            continue

        # ordered list
        om = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if om:
            close_table()
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{_inline_format(_escape(om.group(2)))}</li>")
            i += 1
            continue

        close_lists()
        # paragraph (merge consecutive non-empty non-special lines)
        para = [stripped]
        i += 1
        while i < len(lines):
            s2 = lines[i].strip()
            if not s2 or s2.startswith("#") or s2.startswith("|") or s2.startswith("```"):
                break
            if re.match(r"^[-*+]\s+", s2) or re.match(r"^\d+\.\s+", s2):
                break
            if re.fullmatch(r"-{3,}|_{3,}|\*{3,}", s2):
                break
            para.append(s2)
            i += 1
        joined = " ".join(para)
        out.append(f"<p>{_inline_format(_escape(joined))}</p>")

    close_lists()
    close_table()
    return "\n".join(out)


DOC_SHELL_CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, Ubuntu, sans-serif;
  background: #0b0f14; color: #e8eef5;
  line-height: 1.6; font-size: 1.02rem;
}
.wrap { max-width: 48rem; margin: 0 auto; padding: 1.25rem 1.35rem 3rem; }
header.doc-top {
  display: flex; flex-wrap: wrap; gap: 0.65rem 1rem; align-items: center;
  justify-content: space-between; margin-bottom: 1.25rem;
  padding-bottom: 0.85rem; border-bottom: 1px solid #1f2937;
}
header.doc-top a { color: #93c5fd; text-decoration: none; font-weight: 600; font-size: 0.95rem; }
header.doc-top a:hover { text-decoration: underline; }
h1,h2,h3,h4 { line-height: 1.25; color: #f8fafc; font-weight: 650; }
h1 { font-size: 1.55rem; margin: 0 0 1rem; }
h2 { font-size: 1.2rem; margin: 1.75rem 0 0.65rem; }
h3 { font-size: 1.05rem; margin: 1.35rem 0 0.5rem; }
h4 { font-size: 1rem; margin: 1.15rem 0 0.4rem; }
p { margin: 0.65rem 0; }
a { color: #93c5fd; }
ul, ol { padding-left: 1.35rem; margin: 0.5rem 0 0.85rem; }
li { margin: 0.25rem 0; }
hr { border: 0; border-top: 1px solid #374151; margin: 1.5rem 0; }
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.9em; background: #111827; padding: 0.12rem 0.35rem; border-radius: 4px;
}
pre.doc-code, pre.doc-plain {
  background: #111827; border: 1px solid #1f2937; border-radius: 10px;
  padding: 0.9rem 1rem; overflow-x: auto; font-size: 0.88rem; line-height: 1.45;
}
pre.doc-code code { background: transparent; padding: 0; }
table.doc-table {
  width: 100%; border-collapse: collapse; margin: 0.85rem 0 1.1rem;
  font-size: 0.95rem; display: block; overflow-x: auto;
}
table.doc-table th, table.doc-table td {
  border: 1px solid #374151; padding: 0.45rem 0.6rem; text-align: left; vertical-align: top;
}
table.doc-table th { background: #111827; color: #fde68a; font-weight: 600; }
table.doc-table tr:nth-child(even) td { background: #0f141c; }
/* Package AUDIT STATE: single-line Package + State; room for long basenames */
table.doc-table.pkg-rag {
  min-width: 56rem; width: max-content; max-width: none;
}
table.doc-table.pkg-rag th:nth-child(1),
table.doc-table.pkg-rag td:nth-child(1) {
  white-space: nowrap; min-width: 8.5rem;
}
table.doc-table.pkg-rag th:nth-child(2),
table.doc-table.pkg-rag td:nth-child(2) {
  white-space: nowrap; min-width: 28rem; max-width: none;
}
table.doc-table.pkg-rag th:nth-child(3),
table.doc-table.pkg-rag td:nth-child(3) {
  white-space: nowrap; min-width: 7.5rem; text-align: center; vertical-align: middle;
}
table.doc-table.pkg-rag td:nth-child(2) code {
  white-space: nowrap; word-break: keep-all; overflow-wrap: normal;
  display: inline-block; font-size: 0.82rem;
}
table.doc-table.pkg-rag .plat-icon { margin-right: 0.35rem; font-size: 1.15rem; }
/* Package AUDIT STATE solid colour cells */
.rag-cell { display: flex; align-items: center; justify-content: center; min-height: 1.5rem; min-width: 2.5rem; }
.rag-swatch {
  display: inline-block; width: 1.35rem; height: 1.35rem; border-radius: 4px;
  border: 1px solid rgba(255,255,255,0.12); vertical-align: middle;
}
.rag-swatch.rag-green { background: #22c55e; }
.rag-swatch.rag-amber { background: #f59e0b; }
.rag-swatch.rag-red { background: #ef4444; }
.muted { opacity: 0.78; font-size: 0.92rem; }
footer.doc-foot {
  margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid #1f2937;
  font-size: 0.9rem; opacity: 0.85;
}
footer.doc-foot a { margin-right: 0.65rem; }
article.doc-body { word-wrap: break-word; overflow-wrap: anywhere; }
@media (max-width: 560px) {
  .wrap { padding: 1rem 0.9rem 2.5rem; }
  h1 { font-size: 1.35rem; }
}
"""


def render_document_html(
    *,
    title: str,
    raw: bytes,
    plain: bool = False,
) -> bytes:
    """Wrap product doc bytes in a readable dark HTML shell for browsers."""
    text = raw.decode("utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    if plain:
        body_inner = f'<pre class="doc-plain">{_escape(text)}</pre>'
    else:
        body_inner = markdownish_to_html(text)
    # Ensure a leading h1 when markdown starts with # Title
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="color-scheme" content="dark"/>
<title>{_escape(title)}</title>
<style>{DOC_SHELL_CSS}</style>
</head>
<body>
<div class="wrap">
<header class="doc-top">
  <a href="/" id="doc-back-home">← Status &amp; downloads</a>
  <nav class="doc-mini" aria-label="Documents">
    <a href="{PRIVACY_PATH}">Privacy</a>
    <a href="{LICENSE_PATH}">Licence</a>
    <a href="{AUDIT_PATH}">Audit</a>
    <a href="{README_PATH}">README</a>
  </nav>
</header>
<article class="doc-body" id="doc-body">
{body_inner}
</article>
<footer class="doc-foot">
  <p class="muted">Restore Privacy public documents on this status host
  (source repository is private). Paid installers: <a href="/#downloads">downloads</a>.</p>
  <p>
    <a href="{PRIVACY_PATH}">Privacy</a>
    <a href="{LICENSE_PATH}">Licence</a>
    <a href="{AUDIT_PATH}">Audit</a>
    <a href="{CREDITS_PATH}">Credits</a>
    <a href="{README_PATH}">README</a>
  </p>
</footer>
</div>
</body>
</html>
"""
    return page.encode("utf-8")


def document_bytes_for_path(url_path: str) -> tuple[bytes, str, str] | None:
    """Return (body, content_type, title) for a public doc path, or None.

    Bodies are **readable HTML** shells (not raw markdown dumps) so in-app
    Settings links open user-friendly pages on the Render status host.
    """
    doc = public_doc_by_path(url_path)
    if doc is None:
        return None
    data = load_public_document_bytes(doc.filename)
    if data is None:
        return None
    html = render_document_html(title=doc.title, raw=data, plain=doc.plain)
    return html, "text/html; charset=utf-8", doc.title


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
    )
    body = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>How to buy — Restore Privacy</title>
<style>
{DOC_SHELL_CSS}
.card{{background:#111827;border-radius:12px;padding:1rem 1.15rem;margin:1rem 0;border:1px solid #1f2937}}
ol{{padding-left:1.25rem}}
</style></head><body>
<div class="wrap">
<header class="doc-top">
  <a href="/">← Status &amp; downloads</a>
  <nav aria-label="Documents">
    <a href="{PRIVACY_PATH}">Privacy</a>
    <a href="{LICENSE_PATH}">Licence</a>
    <a href="{AUDIT_PATH}">Audit</a>
    <a href="{README_PATH}">README</a>
  </nav>
</header>
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

<footer class="doc-foot">
<p class="muted">
<a href="{LICENSE_PATH}">Licence</a>
<a href="{PRIVACY_PATH}">Privacy</a>
<a href="{AUDIT_PATH}">Security audit</a>
<a href="{README_PATH}">README</a>
<a href="{CREDITS_PATH}">Credits</a></p>
</footer>
</div>
</body></html>
"""
    return body.encode("utf-8")


def render_public_nav_links_html() -> str:
    """Nav fragment: licence · privacy · audit · readme (same-origin; no How-to-buy)."""
    items = (
        ("LICENCE", LICENSE_PATH, "licence-link"),
        ("PRIVACY POLICY", PRIVACY_PATH, "privacy-link"),
        ("SECURITY AUDIT", AUDIT_PATH, "audit-link"),
        ("README", README_PATH, "readme-link"),
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
