"""Public documents and how-to-buy pages served by the public status host (restoreprivacy.online).

Stable same-origin paths (no GitHub dependency for public readers):

| Path | Document |
|------|----------|
| ``/how-to-buy`` | How to pay and get a one-time download |
| ``/README.md`` | Product README |
| ``/LICENSE`` | End-user licence (proprietary full copyright) |
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
    """One public document served by the VPN APP Shop."""

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


# Package RAG + section B State solid-colour cells — emoji or PASS/SKIP/FAIL words
_RAG_SWATCH_MAP: dict[str, tuple[str, str]] = {
    "🟩": ("rag-green", "Green"),
    "🟧": ("rag-amber", "Amber"),
    "🟥": ("rag-red", "Red"),
}
# Word states (section B Privacy probes + package legend text fallbacks)
_RAG_WORD_SWATCH_MAP: dict[str, tuple[str, str]] = {
    "PASS": ("rag-green", "PASS"),
    "SKIP": ("rag-amber", "SKIP"),
    "FAIL": ("rag-red", "FAIL"),
    "GREEN": ("rag-green", "Green"),
    "AMBER": ("rag-amber", "Amber"),
    "RED": ("rag-red", "Red"),
}


def rag_swatch_html(emoji_or_state: str) -> str | None:
    """Safe solid colour box HTML for a RAG/section-B state, or None.

    Accepts package emoji (🟩/🟧/🟥) and word states (PASS/SKIP/FAIL), including
    markdown-bold forms such as ``**PASS**``.
    """
    key = (emoji_or_state or "").strip()
    if not key:
        return None
    if key in _RAG_SWATCH_MAP:
        css, label = _RAG_SWATCH_MAP[key]
        return (
            f'<span class="rag-swatch {css}" title="{label}" '
            f'role="img" aria-label="{label}"></span>'
        )
    # Strip markdown bold / surrounding asterisks and case-fold
    word = key.replace("*", "").strip().upper()
    if word in _RAG_WORD_SWATCH_MAP:
        css, label = _RAG_WORD_SWATCH_MAP[word]
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
    table_is_section_b = False

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    def close_table() -> None:
        nonlocal in_table, table_is_pkg_rag, table_is_section_b
        if in_table:
            out.append("</tbody></table>")
            in_table = False
            table_is_pkg_rag = False
            table_is_section_b = False

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
                # Installer package table: Platform | Package | STATE | Notes
                # Section B privacy probes: Probe | State | Notes
                header_join = " ".join(cells).lower()
                table_is_pkg_rag = (
                    "package" in header_join
                    and "platform" in header_join
                    and ("state" in header_join or "audit state" in header_join)
                )
                table_is_section_b = (
                    not table_is_pkg_rag
                    and "probe" in header_join
                    and "state" in header_join
                )
                if table_is_pkg_rag:
                    tclass = "doc-table pkg-rag"
                elif table_is_section_b:
                    tclass = "doc-table section-b-probes"
                else:
                    tclass = "doc-table"
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
            # Package AUDIT STATE: scroll lengthy Package (col 2) / Notes (col 4) in-cell
            # Section B: scroll lengthy Notes (col 3) only — Probe col stays identity
            scroll_cols: set[int] = set()
            if table_is_pkg_rag:
                scroll_cols = {1, 3}
            elif table_is_section_b:
                scroll_cols = {2}  # Notes only; not Probe (0) or State (1)
            cell_parts: list[str] = []
            for col_i, c in enumerate(cells):
                inner = _format_table_cell(c, header=(tag == "th"))
                if col_i in scroll_cols and tag == "td":
                    cell_parts.append(
                        f'<{tag} class="pkg-cell-scroll">'
                        f'<div class="cell-scroll">{inner}</div></{tag}>'
                    )
                elif col_i in scroll_cols and tag == "th":
                    cell_parts.append(
                        f'<{tag} class="pkg-cell-scroll">{inner}</{tag}>'
                    )
                else:
                    cell_parts.append(f"<{tag}>{inner}</{tag}>")
            cells_html = "".join(cell_parts)
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
/*
 * Package AUDIT STATE (pkg-rag): fit content column; lengthy Package/Notes
 * scroll *inside the cell* — do not force full-page horizontal widen via max-content.
 */
table.doc-table.pkg-rag {
  display: table;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  table-layout: fixed;
  overflow: visible;
}
table.doc-table.pkg-rag th:nth-child(1),
table.doc-table.pkg-rag td:nth-child(1) {
  width: 18%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
table.doc-table.pkg-rag th:nth-child(2),
table.doc-table.pkg-rag td:nth-child(2),
table.doc-table.pkg-rag th.pkg-cell-scroll,
table.doc-table.pkg-rag td.pkg-cell-scroll {
  width: 34%;
  max-width: 0; /* with table-layout:fixed, enable overflow scroll */
  overflow: hidden;
  vertical-align: middle;
}
table.doc-table.pkg-rag th:nth-child(3),
table.doc-table.pkg-rag td:nth-child(3) {
  width: 12%;
  white-space: nowrap;
  text-align: center;
  vertical-align: middle;
  overflow: visible;
}
table.doc-table.pkg-rag th:nth-child(4),
table.doc-table.pkg-rag td:nth-child(4) {
  width: 36%;
  max-width: 0;
  overflow: hidden;
  vertical-align: middle;
}
/* In-cell horizontal scroll for long basenames / notes (not page scroll) */
table.doc-table.pkg-rag .cell-scroll {
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  white-space: nowrap;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
}
table.doc-table.pkg-rag td.pkg-cell-scroll .cell-scroll code,
table.doc-table.pkg-rag .cell-scroll code {
  white-space: nowrap;
  word-break: keep-all;
  overflow-wrap: normal;
  display: inline-block;
  font-size: 0.82rem;
}
table.doc-table.pkg-rag .plat-icon { margin-right: 0.35rem; font-size: 1.15rem; }
/*
 * Privacy probes section B (Probe | State | Notes): State solid colour boxes;
 * lengthy Notes scroll in-cell; Probe column stays fixed identity (no scroll).
 */
table.doc-table.section-b-probes {
  display: table;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  table-layout: fixed;
  overflow: visible;
}
table.doc-table.section-b-probes th:nth-child(1),
table.doc-table.section-b-probes td:nth-child(1) {
  width: 28%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
}
table.doc-table.section-b-probes th:nth-child(2),
table.doc-table.section-b-probes td:nth-child(2) {
  width: 12%;
  white-space: nowrap;
  text-align: center;
  vertical-align: middle;
  overflow: visible;
}
table.doc-table.section-b-probes th:nth-child(3),
table.doc-table.section-b-probes td:nth-child(3),
table.doc-table.section-b-probes th.pkg-cell-scroll,
table.doc-table.section-b-probes td.pkg-cell-scroll {
  width: 60%;
  max-width: 0;
  overflow: hidden;
  vertical-align: middle;
}
table.doc-table.section-b-probes .cell-scroll {
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  white-space: nowrap;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
}
table.doc-table.section-b-probes td.pkg-cell-scroll .cell-scroll code,
table.doc-table.section-b-probes .cell-scroll code {
  white-space: nowrap;
  word-break: keep-all;
  overflow-wrap: normal;
  display: inline-block;
  font-size: 0.82rem;
}
/* Package AUDIT STATE + section B State solid colour cells */
.rag-cell { display: flex; align-items: center; justify-content: center; min-height: 1.5rem; min-width: 2.5rem; }
.rag-swatch {
  display: inline-block; width: 1.35rem; height: 1.35rem; border-radius: 4px;
  border: 1px solid rgba(255,255,255,0.12); vertical-align: middle;
}
.rag-swatch.rag-green { background: #22c55e; }
.rag-swatch.rag-amber { background: #f59e0b; }
.rag-swatch.rag-red { background: #ef4444; }
/* Audit page: countdown under H1 + current-run RAG colour */
.audit-page-ticker {
  margin: 0.85rem 0 1.35rem; padding: 0.85rem 1rem;
  background: #111827; border: 1px solid #1f2937; border-radius: 10px;
  max-width: 36rem;
}
.audit-page-countdown-row {
  display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; align-items: baseline;
  margin-bottom: 0.55rem;
}
.audit-page-countdown-label {
  color: #9ca3af; font-size: 0.9rem; text-transform: lowercase; letter-spacing: 0.02em;
}
.audit-page-countdown-value {
  font-variant-numeric: tabular-nums; font-weight: 700; font-size: 1.35rem;
  color: #6ee7b7; letter-spacing: 0.04em;
}
.audit-page-current-run {
  display: flex; align-items: center; gap: 0.55rem; flex-wrap: wrap;
  margin: 0.35rem 0 0.25rem; font-size: 0.95rem;
}
.audit-page-current-run .rag-swatch {
  width: 1.15rem; height: 1.15rem; flex-shrink: 0;
}
.audit-page-current-run-text { color: #e8eef5; line-height: 1.4; }
.audit-page-current-run-text strong { font-weight: 700; }
.audit-page-current-run[data-rag-colour="green"] .audit-page-current-run-text strong { color: #22c55e; }
.audit-page-current-run[data-rag-colour="amber"] .audit-page-current-run-text strong { color: #f59e0b; }
.audit-page-current-run[data-rag-colour="red"] .audit-page-current-run-text strong { color: #ef4444; }
.audit-page-current-run-unavailable .audit-page-current-run-text { color: #9ca3af; }
.audit-page-ticker-blurb {
  margin: 0.45rem 0 0; font-size: 0.78rem; line-height: 1.4; color: #9ca3af;
}
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


def _is_audit_document(*, title: str, text: str) -> bool:
    """True when this shell is the public Code & Policy Audit document."""
    t = (title or "").lower()
    body = (text or "").lower()
    if "code & policy audit" in body or "code and policy audit" in body:
        return True
    if "security audit" in t and "restore privacy" in t:
        return True
    if "code & policy audit" in t:
        return True
    return False


def render_document_html(
    *,
    title: str,
    raw: bytes,
    plain: bool = False,
    include_audit_ticker: bool | None = None,
) -> bytes:
    """Wrap product doc bytes in a readable dark HTML shell for browsers.

    When the document is the public audit (or *include_audit_ticker* is True),
    injects a live countdown + current-run Green/Amber/Red banner immediately
    under the first ``h1`` (``Restore Privacy — Code & Policy Audit``).
    """
    text = raw.decode("utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    if plain:
        body_inner = f'<pre class="doc-plain">{_escape(text)}</pre>'
    else:
        body_inner = markdownish_to_html(text)
    want_ticker = (
        include_audit_ticker
        if include_audit_ticker is not None
        else _is_audit_document(title=title, text=text)
    )
    if want_ticker and not plain and "</h1>" in body_inner:
        try:
            from audit_countdown import render_audit_page_ticker_html
        except ImportError:  # pragma: no cover
            from status_page.audit_countdown import (  # type: ignore
                render_audit_page_ticker_html,
            )
        ticker = render_audit_page_ticker_html()
        body_inner = body_inner.replace("</h1>", "</h1>\n" + ticker, 1)
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
    is_audit = doc.filename.upper() in ("AUDIT.MD", "AUDIT") or doc.id == "audit"
    html = render_document_html(
        title=doc.title,
        raw=data,
        plain=doc.plain,
        include_audit_ticker=is_audit or None,
    )
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
No free permanent installer buttons on the VPN APP Shop.</p>

<div class="card" id="how-to-buy-steps">
<h2>Steps</h2>
<ol>
  <li>Open the VPN APP Shop: <a href="{_escape(home)}">{_escape(home)}</a></li>
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
