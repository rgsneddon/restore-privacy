"""Public documents and how-to-buy pages served by the public status host (restoreprivacy.online).

Stable same-origin paths (no GitHub dependency for public readers):

| Path | Document |
|------|----------|
| ``/how-to-buy`` | How to pay and get a time-limited download link |
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


def _redact_public_doc_text(text: str) -> str:
    """Strip residual monopin IPv4s from public markdown (AUDIT/CREDITS/etc.)."""
    try:
        # Prefer monorepo client helper when available on the status host
        import sys

        root = str(REPO_ROOT)
        if root not in sys.path:
            sys.path.insert(0, root)
        from client.residual_public import redact_residual_hosts_in_text

        return redact_residual_hosts_in_text(text)
    except Exception:  # noqa: BLE001
        # Fail closed: still blank known monopin IPs without client package
        for host, label in (
            ("82.221.101.241", "Iceland (IS)"),
            ("185.146.232.107", "Romania (RO)"),
            ("5.161.242.85", "United States (US)"),
            ("167.233.224.5", "VPN node"),
        ):
            text = text.replace(host, label)
        return text


def load_public_document_bytes(filename: str, *, min_size: int = 20) -> bytes | None:
    """Load a public document from status_page/public, status_page, or repo root.

    User-facing public docs are redacted of residual monopin IPv4s before serve.
    """
    for path in _candidate_paths(filename):
        try:
            if path.is_file() and path.stat().st_size >= min_size:
                raw = path.read_bytes()
                name = path.name.upper()
                # Redact residual hosts from public-facing text docs
                if name.endswith(".MD") or name in ("LICENSE", "CREDITS.MD", "AUDIT.MD"):
                    try:
                        text = raw.decode("utf-8")
                        text = _redact_public_doc_text(text)
                        return text.encode("utf-8")
                    except UnicodeDecodeError:
                        return raw
                return raw
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

# Product RAG squares + platform column icons that may appear in AUDIT tables.
_AUDIT_EMOJI_CANONICAL: tuple[str, ...] = (
    "🟩",
    "🟧",
    "🟥",
    "🪟",
    "🐧",
    "🍎",
    "📱",
    "🤖",
    "📦",
)


def _mojibake_pairs_for_emoji(emoji: str) -> list[tuple[str, str]]:
    """Return (corrupted, good) pairs for common UTF-8 mis-decodes of *emoji*."""
    pairs: list[tuple[str, str]] = []
    raw = emoji.encode("utf-8")
    # UTF-8 bytes misread as Windows-1252 (typical editor/console mojibake)
    try:
        bad_cp = raw.decode("cp1252")
        if bad_cp != emoji and "\ufffd" not in bad_cp:
            pairs.append((bad_cp, emoji))
    except UnicodeDecodeError:
        pass
    # UTF-8 bytes misread as latin-1 / ISO-8859-1
    bad_l1 = raw.decode("latin-1")
    if bad_l1 != emoji:
        pairs.append((bad_l1, emoji))
    return pairs


def _build_audit_emoji_repairs() -> list[tuple[str, str]]:
    """All (bad, good) replacements for AUDIT RAG/platform emoji recovery."""
    pairs: list[tuple[str, str]] = []
    for good in _AUDIT_EMOJI_CANONICAL:
        pairs.extend(_mojibake_pairs_for_emoji(good))
    # Observed mixed corruption in shipped AUDIT.md (macOS / Linux platform cells):
    # partial cp1252 + residual C1 bytes that neither pure cp1252 nor latin-1 alone match.
    pairs.extend(
        (
            ("\u00f0\u0178\u008d\u017d", "🍎"),  # macOS 🍎
            ("\u00f0\u0178\u0090\u00a7", "🐧"),  # Linux 🐧
        )
    )
    # Longest first so multi-byte sequences win over prefixes
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    # Dedup while preserving order
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for bad, good in pairs:
        if not bad or bad == good or bad in seen:
            continue
        seen.add(bad)
        out.append((bad, good))
    return out


_AUDIT_EMOJI_REPAIRS: list[tuple[str, str]] = _build_audit_emoji_repairs()


def repair_audit_emoji_mojibake(text: str) -> str:
    """Repair UTF-8 emoji that were mojibaked (e.g. 🟩 → ``ðŸŸ©``).

    Shipped AUDIT package/UK-RAG tables sometimes store Windows-1252 mis-decodes
    of solid colour squares and platform icons. Those fail ``rag_swatch_html``
    and surface as wonky characters on the public audit page.
    """
    if not text:
        return text
    # Fast path: no high-bit mojibake lead-ins commonly used for these glyphs
    if "\u00f0" not in text and "ð" not in text:
        return text
    out = text
    for bad, good in _AUDIT_EMOJI_REPAIRS:
        if bad in out:
            out = out.replace(bad, good)
    return out


def rag_swatch_html(emoji_or_state: str) -> str | None:
    """Safe solid colour box HTML for a RAG/section-B state, or None.

    Accepts package emoji (🟩/🟧/🟥) and word states (PASS/SKIP/FAIL), including
    markdown-bold forms such as ``**PASS**``. Also accepts common mojibake
    forms of the colour squares (repaired before lookup).
    """
    key = repair_audit_emoji_mojibake((emoji_or_state or "").strip())
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

    s = repair_audit_emoji_mojibake(escaped_line)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_sub, s)
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
    stripped = repair_audit_emoji_mojibake((raw_cell or "").strip())
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
    return _inline_format(_escape(raw_cell if raw_cell is not None else ""))


def markdownish_to_html(text: str) -> str:
    """Conservative markdown → HTML for product docs (escape-first, no script)."""
    import re

    text = repair_audit_emoji_mojibake(
        text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    )
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
                # UK ping + RAG: Shape | … | AVG | RAG | Notes
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
                table_is_uk_ping = (
                    not table_is_pkg_rag
                    and not table_is_section_b
                    and "notes" in header_join
                    and (
                        "avg" in header_join
                        or ("shape" in header_join and "multi" in header_join)
                    )
                )
                # Any other Notes-last audit matrix (balanced cols + scroll Notes)
                table_is_notes_matrix = (
                    not table_is_pkg_rag
                    and not table_is_section_b
                    and not table_is_uk_ping
                    and "notes" in header_join
                    and len(cells) >= 3
                )
                if table_is_pkg_rag:
                    tclass = "doc-table pkg-rag"
                elif table_is_section_b:
                    tclass = "doc-table section-b-probes"
                elif table_is_uk_ping:
                    tclass = "doc-table uk-ping-rag"
                elif table_is_notes_matrix:
                    tclass = "doc-table notes-matrix"
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
            # UK ping / notes matrix: last Notes column scrolls (vertical + horizontal)
            scroll_cols: set[int] = set()
            notes_scroll_cols: set[int] = set()
            if table_is_pkg_rag:
                scroll_cols = {1, 3}
                notes_scroll_cols = {3}
            elif table_is_section_b:
                scroll_cols = {2}  # Notes only; not Probe (0) or State (1)
                notes_scroll_cols = {2}
            elif table_is_uk_ping or table_is_notes_matrix:
                # Notes is last column
                notes_i = len(cells) - 1
                if tag == "th":
                    for hi, hc in enumerate(cells):
                        if "note" in hc.lower():
                            notes_i = hi
                            break
                scroll_cols = {notes_i}
                notes_scroll_cols = {notes_i}
            cell_parts: list[str] = []
            for col_i, c in enumerate(cells):
                inner = _format_table_cell(c, header=(tag == "th"))
                if col_i in scroll_cols and tag == "td":
                    scroll_cls = (
                        "cell-scroll cell-scroll-notes"
                        if col_i in notes_scroll_cols
                        else "cell-scroll"
                    )
                    cell_parts.append(
                        f'<{tag} class="pkg-cell-scroll notes-cell">'
                        f'<div class="{scroll_cls}">{inner}</div></{tag}>'
                    )
                elif col_i in scroll_cols and tag == "th":
                    cell_parts.append(
                        f'<{tag} class="pkg-cell-scroll notes-cell">{inner}</{tag}>'
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
/* Doc-body typography + tables (theme tokens from public_chrome) */
.doc-body { line-height: 1.6; font-size: 1.02rem; color: var(--rb-doc-fg, var(--rb-cream)); }
.doc-body h1, .doc-body h2, .doc-body h3, .doc-body h4 {
  line-height: 1.25; color: var(--rb-cream); font-weight: 650;
}
.doc-body h1 { font-size: 1.55rem; margin: 0 0 1rem; }
.doc-body h2 { font-size: 1.2rem; margin: 1.75rem 0 0.65rem; }
.doc-body h3 { font-size: 1.05rem; margin: 1.35rem 0 0.5rem; }
.doc-body h4 { font-size: 1rem; margin: 1.15rem 0 0.4rem; }
.doc-body p { margin: 0.65rem 0; }
.doc-body a { color: var(--rb-link); }
.doc-body ul, .doc-body ol { padding-left: 1.35rem; margin: 0.5rem 0 0.85rem; }
.doc-body li { margin: 0.25rem 0; }
.doc-body hr { border: 0; border-top: 1px solid var(--rb-card-border); margin: 1.5rem 0; }
.doc-body code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.9em; background: var(--rb-code-bg); padding: 0.12rem 0.35rem; border-radius: 0;
}
pre.doc-code, pre.doc-plain {
  background: var(--rb-pre-bg); border: 1px solid var(--rb-pre-border); border-radius: 0;
  padding: 0.9rem 1rem; overflow-x: auto; font-size: 0.88rem; line-height: 1.45;
  color: var(--rb-doc-fg);
}
pre.doc-code code { background: transparent; padding: 0; }
table.doc-table {
  width: 100%; border-collapse: collapse; margin: 0.85rem 0 1.1rem;
  font-size: 0.88rem; display: block; overflow-x: auto;
  border-radius: 0;
}
table.doc-table th, table.doc-table td {
  border: 1px solid var(--rb-card-border); padding: 0.4rem 0.5rem; text-align: left; vertical-align: top;
}
table.doc-table th {
  background: var(--rb-code-bg); color: var(--rb-accent-sky, var(--rb-link)); font-weight: 650;
  font-size: 0.78rem; letter-spacing: 0.03em; text-transform: uppercase;
}
table.doc-table tr:nth-child(even) td {
  background: color-mix(in srgb, var(--rb-code-bg) 55%, transparent);
}
/* Shared Notes-cell scroll (vertical wrap + thin scrollbar) */
table.doc-table .cell-scroll-notes {
  max-width: 100%;
  max-height: 5.25rem;
  overflow-x: auto;
  overflow-y: auto;
  white-space: normal;
  word-break: break-word;
  line-height: 1.35;
  font-size: 0.8rem;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
}
table.doc-table td.notes-cell,
table.doc-table th.notes-cell {
  max-width: 0;
  overflow: hidden;
  vertical-align: top;
}
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
table.doc-table.pkg-rag .cell-scroll-notes {
  white-space: normal;
  overflow-y: auto;
  max-height: 5.25rem;
  word-break: break-word;
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
table.doc-table.section-b-probes .cell-scroll-notes {
  white-space: normal;
  overflow-y: auto;
  max-height: 5.25rem;
}
table.doc-table.section-b-probes td.pkg-cell-scroll .cell-scroll code,
table.doc-table.section-b-probes .cell-scroll code {
  white-space: nowrap;
  word-break: keep-all;
  overflow-wrap: normal;
  display: inline-block;
  font-size: 0.82rem;
}
/*
 * Privacy-scale UK ping + RAG:
 * compact control columns; entry/exit readable; Notes scrolls in-cell.
 * Shape | Outer obfs | Multi-hop | Entry | Exit | AVG | RAG | Notes
 */
table.doc-table.uk-ping-rag {
  display: table;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  table-layout: fixed;
  overflow: visible;
  font-size: 0.82rem;
}
table.doc-table.uk-ping-rag th:nth-child(1),
table.doc-table.uk-ping-rag td:nth-child(1) { width: 6.5%; text-align: center; white-space: nowrap; }
table.doc-table.uk-ping-rag th:nth-child(2),
table.doc-table.uk-ping-rag td:nth-child(2) { width: 8%; text-align: center; white-space: nowrap; }
table.doc-table.uk-ping-rag th:nth-child(3),
table.doc-table.uk-ping-rag td:nth-child(3) { width: 8%; text-align: center; white-space: nowrap; }
table.doc-table.uk-ping-rag th:nth-child(4),
table.doc-table.uk-ping-rag td:nth-child(4) { width: 14%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
table.doc-table.uk-ping-rag th:nth-child(5),
table.doc-table.uk-ping-rag td:nth-child(5) { width: 14%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
table.doc-table.uk-ping-rag th:nth-child(6),
table.doc-table.uk-ping-rag td:nth-child(6) { width: 7.5%; text-align: center; white-space: nowrap; font-variant-numeric: tabular-nums; font-weight: 700; }
table.doc-table.uk-ping-rag th:nth-child(7),
table.doc-table.uk-ping-rag td:nth-child(7) { width: 6%; text-align: center; white-space: nowrap; vertical-align: middle; }
table.doc-table.uk-ping-rag th:nth-child(8),
table.doc-table.uk-ping-rag td:nth-child(8),
table.doc-table.uk-ping-rag th.notes-cell,
table.doc-table.uk-ping-rag td.notes-cell {
  width: 36%;
  max-width: 0;
  overflow: hidden;
  vertical-align: top;
}
table.doc-table.uk-ping-rag .cell-scroll-notes {
  max-height: 4.75rem;
  font-size: 0.76rem;
  color: var(--rb-doc-muted, var(--rb-muted));
}
/* Generic Notes-last matrices (multihop etc.) */
table.doc-table.notes-matrix {
  display: table;
  width: 100%;
  max-width: 100%;
  table-layout: fixed;
  overflow: visible;
}
table.doc-table.notes-matrix th:last-child,
table.doc-table.notes-matrix td:last-child,
table.doc-table.notes-matrix th.notes-cell,
table.doc-table.notes-matrix td.notes-cell {
  width: 42%;
  max-width: 0;
  overflow: hidden;
}
/* Package AUDIT STATE + section B State solid colour cells */
.rag-cell { display: flex; align-items: center; justify-content: center; min-height: 1.5rem; min-width: 2.5rem; }
.rag-swatch {
  display: inline-block; width: 1.25rem; height: 1.25rem; border-radius: 0;
  border: 1px solid rgba(255,255,255,0.12); vertical-align: middle;
}
.rag-swatch.rag-green { background: #22c55e; }
.rag-swatch.rag-amber { background: #f59e0b; }
.rag-swatch.rag-red { background: #ef4444; }
/* Audit page: countdown under H1 + current-run RAG colour */
.audit-page-ticker {
  margin: 0.85rem 0 1.35rem; padding: 0.85rem 1rem;
  background: var(--rb-code-bg); border: 1px solid var(--rb-card-border); border-radius: 0;
  max-width: 36rem;
}
.audit-page-countdown-row {
  display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; align-items: baseline;
  margin-bottom: 0.55rem;
}
.audit-page-countdown-label {
  color: var(--rb-muted); font-size: 0.9rem; text-transform: lowercase; letter-spacing: 0.02em;
}
.audit-page-countdown-value {
  font-variant-numeric: tabular-nums; font-weight: 700; font-size: 1.35rem;
  color: var(--rb-accent-sky, #6ee7b7); letter-spacing: 0.04em;
}
.audit-page-current-run {
  display: flex; align-items: center; gap: 0.55rem; flex-wrap: wrap;
  margin: 0.35rem 0 0.25rem; font-size: 0.95rem;
}
.audit-page-current-run .rag-swatch {
  width: 1.15rem; height: 1.15rem; flex-shrink: 0;
}
.audit-page-current-run-text { color: var(--rb-doc-fg); line-height: 1.4; }
.audit-page-current-run-text strong { font-weight: 700; }
.audit-page-current-run[data-rag-colour="green"] .audit-page-current-run-text strong { color: #22c55e; }
.audit-page-current-run[data-rag-colour="amber"] .audit-page-current-run-text strong { color: #f59e0b; }
.audit-page-current-run[data-rag-colour="red"] .audit-page-current-run-text strong { color: #ef4444; }
.audit-page-current-run-unavailable .audit-page-current-run-text { color: var(--rb-muted); }
.audit-page-ticker-blurb {
  margin: 0.45rem 0 0; font-size: 0.78rem; line-height: 1.4; color: var(--rb-muted);
}
.muted { color: var(--rb-muted); font-size: 0.92rem; }
article.doc-body { word-wrap: break-word; overflow-wrap: anywhere; }
@media (max-width: 560px) {
  .doc-body h1 { font-size: 1.35rem; }
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


def _active_nav_for_title(title: str, *, plain: bool = False) -> str | None:
    """Map document title → shared public nav *active* key.

    Order is intentional: product titles often end with ``— Restore Privacy``,
    so a bare ``\"privacy\" in title`` would steal Audit/README highlights.
    Match specific docs first; Privacy Policy only via policy phrasing.
    """
    t = (title or "").lower().strip()
    if plain or "licence" in t or "license" in t:
        return "licence"
    # Security audit (before privacy — product name contains "privacy")
    if "audit" in t or "code & policy" in t or "code and policy" in t:
        return "audit"
    # README / credits
    if "readme" in t or t.startswith("read me") or "credit" in t:
        return "readme"
    # Privacy Policy only — not every string with the product name
    if "privacy policy" in t or "privacy_policy" in t or t.endswith("privacy policy"):
        return "privacy"
    if "privacy" in t and "policy" in t:
        return "privacy"
    return None


def render_document_html(
    *,
    title: str,
    raw: bytes,
    plain: bool = False,
    include_audit_ticker: bool | None = None,
) -> bytes:
    """Wrap product doc bytes in the shared public box-style shell.

    Licence (``plain=True``) keeps typeform/preformatted body. When the document
    is the public audit (or *include_audit_ticker* is True), injects the live
    countdown ticker under the first ``h1``.
    """
    try:
        from public_chrome import (
            public_brand_header_html,
            public_head_open,
            public_page_close,
        )
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import (  # type: ignore
            public_brand_header_html,
            public_head_open,
            public_page_close,
        )

    text = raw.decode("utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    if plain:
        body_inner = f'<pre class="doc-plain" id="licence-typeform">{_escape(text)}</pre>'
    else:
        body_inner = markdownish_to_html(text)
    want_ticker = (
        include_audit_ticker
        if include_audit_ticker is not None
        else _is_audit_document(title=title, text=text)
    )
    if want_ticker and not plain and "</h1>" in body_inner:
        try:
            from audit_countdown import (
                overlay_audit_generated_in_markdown_html,
                render_audit_page_ticker_html,
            )
        except ImportError:  # pragma: no cover
            from status_page.audit_countdown import (  # type: ignore
                overlay_audit_generated_in_markdown_html,
                render_audit_page_ticker_html,
            )
        # Prefer live JSON generated_at over stale AUDIT.md table cells
        body_inner = overlay_audit_generated_in_markdown_html(body_inner)
        ticker = render_audit_page_ticker_html()
        body_inner = body_inner.replace("</h1>", "</h1>\n" + ticker, 1)

    active = _active_nav_for_title(title, plain=plain)
    # Doc-specific table/RAG helpers still useful alongside shared chrome
    extra = DOC_SHELL_CSS + """
.doc-body-panel h1:first-child { margin-top: 0; }
.rag-swatch {
  display: inline-block; width: 1.1rem; height: 1.1rem; border-radius: 0;
  vertical-align: middle;
}
.rag-green { background: #22c55e; }
.rag-amber { background: #f59e0b; }
.rag-red { background: #ef4444; }
.pkg-cell-scroll .cell-scroll { max-height: 6.5rem; overflow: auto; }
.pkg-cell-scroll .cell-scroll-notes { max-height: 5.25rem; overflow: auto; white-space: normal; }
"""
    try:
        from public_chrome import PUBLIC_BRAND_TITLE
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import PUBLIC_BRAND_TITLE  # type: ignore

    header = public_brand_header_html(
        title=PUBLIC_BRAND_TITLE,
        active=active,
        logo_size=112,
    )
    page = f"""{public_head_open(title=title, extra_css=extra)}
  <div class="page-shell" id="doc-page-shell" data-page="doc" data-chrome="pro">
{header}
    <section class="panel-card doc-body-panel" id="doc-content-panel" aria-label="Document" data-chrome="pro">
      <article class="doc-body" id="doc-body">
{body_inner}
      </article>
    </section>
    <footer class="panel-card doc-foot" id="doc-foot" data-chrome="pro">
      <p class="muted">Restore Privacy public documents on this status host
      (source repository is private). Paid installers:
      <a href="/#downloads">downloads</a>.</p>
      <p>
        <a href="{PRIVACY_PATH}">Privacy</a>
        <a href="{LICENSE_PATH}">Licence</a>
        <a href="{AUDIT_PATH}">Audit</a>
        <a href="{CREDITS_PATH}">Credits</a>
        <a href="{README_PATH}">README</a>
        <a href="/support">Support</a>
      </p>
    </footer>
  </div>
{public_page_close()}"""
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
        PRICE_YEARLY_LABEL,
        SITE_PAY_PLAN_PATH,
        stripe_webhook_endpoint_url,
    )

    try:
        from public_chrome import (
            public_brand_header_html,
            public_head_open,
            public_page_close,
        )
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import (  # type: ignore
            public_brand_header_html,
            public_head_open,
            public_page_close,
        )

    pay = public_doc_absolute_url(SITE_PAY_PLAN_PATH)
    claim = public_doc_absolute_url("/download/success")
    home = production_status_origin()
    webhook = stripe_webhook_endpoint_url(production=True)
    docs = public_docs_catalog()
    doc_lis = "\n".join(
        f'    <li><a href="{d["path"]}">{_escape(d["title"])}</a> '
        f'(<code>{_escape(d["url"])}</code>)</li>'
        for d in docs
    )
    try:
        from public_chrome import PUBLIC_BRAND_TITLE
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import PUBLIC_BRAND_TITLE  # type: ignore

    header = public_brand_header_html(
        title=PUBLIC_BRAND_TITLE,
        active="home",
        logo_size=112,
    )
    body = f"""{public_head_open(title="How to buy — Restore Privacy", extra_css='''
.card{{background:var(--rb-card);border-radius:12px;padding:1rem 1.15rem;margin:1rem 0;border:1px solid var(--rb-card-border)}}
ol{{padding-left:1.25rem;color:var(--rb-muted)}}
''')}
  <div class="page-shell" id="how-to-buy-shell">
{header}
<section class="panel-card doc-body-panel" id="how-to-buy-panel">
<h1 id="how-to-buy-heading">How to buy Restore Privacy</h1>
<p class="muted">Paid subscription only: <strong>Monthly VPN plan</strong>
({_escape(PRICE_LABEL)} / month GBP) or <strong>Yearly VPN plan</strong>
({_escape(PRICE_YEARLY_LABEL)} / year — 5% off vs paying monthly).
There are no free permanent installer buttons on this shop.</p>

<div class="card" id="how-to-buy-steps">
<h2>Select your plan</h2>
<ol>
  <li>Open the shop: <a href="{_escape(home)}">{_escape(home)}</a></li>
  <li>Under <strong>Download client</strong>, choose your device and plan
      (Monthly VPN plan or Yearly VPN plan). You can also open the plan page at
      <code>{_escape(SITE_PAY_PLAN_PATH)}</code> (<code>/pay</code>).</li>
  <li>Continue to Stripe Checkout
      ({_escape(PRICE_LABEL)}/month or {_escape(PRICE_YEARLY_LABEL)}/year):
      <a id="how-to-buy-payment-page" href="{_escape(pay)}"
      rel="noopener noreferrer">{_escape(pay)}</a></li>
  <li>After payment, use the download on the success page
      (<code>{_escape(claim)}?session_id=…</code>). The link is valid for
      <strong>1 hour</strong> and can be used again if the connection drops
      mid-download (not single-use). Your keygen arrives in email
      separately (USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY).</li>
</ol>
<p class="muted">Fulfilment listens for Stripe
<code>checkout.session.completed</code> on
<code>{_escape(webhook)}</code>. Connect stays active through the paid
period; refunds and subscription end revoke access.</p>
</div>

<div class="card" id="how-to-buy-public-docs">
<h2>Documents on this site</h2>
<ul id="public-docs-list">
{doc_lis}
</ul>
</div>

</section>
<footer class="panel-card doc-foot">
<p class="muted">
<a href="{LICENSE_PATH}">Licence</a>
<a href="{PRIVACY_PATH}">Privacy</a>
<a href="{AUDIT_PATH}">Security audit</a>
<a href="{README_PATH}">README</a>
<a href="{CREDITS_PATH}">Credits</a></p>
</footer>
</div>
{public_page_close()}
"""
    return body.encode("utf-8")


def render_public_nav_links_html(*, active: str | None = None) -> str:
    """Shared public nav: Home before Licence, button-style (logo palette).

    Delegates to :mod:`public_chrome` so homepage and docs cannot drift.
    """
    try:
        from public_chrome import public_nav_links_html
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import public_nav_links_html  # type: ignore

    return public_nav_links_html(active=active)
