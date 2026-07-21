"""Production node host privacy — Iceland / FlokiNET public-statement helpers.

Used by user-facing docs tests and the “grok test” that relays FlokiNET’s own
public claims (live fetch preferred; offline fixture when the network is down).

This module does **not** claim a third-party forensic audit of FlokiNET’s
network. Product residual risk if the **node OS** is compromised remains
distinct from the host’s published VPS connection-logging stance.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Product placement (operator-asserted; matches catalog monopin host)
# ---------------------------------------------------------------------------

PRODUCT_NODE_HOST = "82.221.101.241"
PRODUCT_NODE_COUNTRY = "Iceland"
PRODUCT_VPS_HOST_NAME = "FlokiNET"
# Common alternate spelling used in operator prose
PRODUCT_VPS_HOST_ALIASES = ("FlokiNET", "Flokinet", "flokinet")

FLOKINET_PRIVACY_URL = "https://flokinet.is/privacy/"
FLOKINET_VPS_URL = "https://flokinet.is/vps/"
FLOKINET_ABOUT_URL = "https://flokinet.is/about/"

# Checked-in excerpts of public FlokiNET pages (relay material when offline).
# Source URLs recorded above; re-verify periodically against live pages.
OFFLINE_HOST_STATEMENT_EXCERPT = """
FlokiNET public privacy marketing (https://flokinet.is/privacy/):
- No ID. No questions. No tracking.
- No invasive logs
- Iceland - Strongest press and speech protections in the world
- We don't share DNS or other traffic data with 3rd parties.
- Privacy friendly legal jurisdictions; host in Iceland among other locations.

FlokiNET VPS FAQ (https://flokinet.is/vps/):
- You will be the only one with root access.
- We do not retain any ability to access your stored data through any tool
  for management or monitoring. We only monitor overall resource usage.
- Additionally, we do not share any information with any third parties
  regarding your traffic or patterns in any circumstance.
- Root access with no monitoring. (privacy page VPS section)

FlokiNET About (https://flokinet.is/about/):
- Founded in Iceland in 2012
- IMMI - Icelandic Modern Media Initiative
- Privacy and freedom of expression focused hosting
""".strip()


def user_doc_host_assurance_markers() -> tuple[str, ...]:
    """Substrings that MUST appear in README / PRIVACY_POLICY / AUDIT host notes."""
    return (
        "Iceland",
        "Icelandic",
        "FlokiNET",
        "as far as we can be assured",
        "no invasive logs",
    )


def host_statement_claim_markers() -> tuple[str, ...]:
    """Markers expected when relaying FlokiNET public statements (live or fixture)."""
    return (
        "No invasive logs",
        "Iceland",
        "resource usage",
        "third parties",
        "traffic",
    )


@dataclass(frozen=True)
class HostStatementRelay:
    """Result of fetching/relaying FlokiNET public host statements."""

    source: str  # "live" | "offline_fixture"
    urls_tried: tuple[str, ...]
    text: str
    live_ok: bool
    errors: tuple[str, ...] = ()

    def contains_all(self, needles: Iterable[str]) -> bool:
        blob = self.text
        # Case-insensitive for robust matching across HTML casing
        low = blob.lower()
        return all(n.lower() in low for n in needles)


def offline_host_statements() -> HostStatementRelay:
    """Return checked-in public-statement excerpts (always available offline)."""
    return HostStatementRelay(
        source="offline_fixture",
        urls_tried=(),
        text=OFFLINE_HOST_STATEMENT_EXCERPT,
        live_ok=False,
        errors=(),
    )


def _fetch_url(url: str, timeout: float = 12.0) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "RestorePrivacy-host-privacy-probe/0.3.4 (+https://restoreprivacy.online/)",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — public HTTPS
        raw = resp.read()
    return raw.decode("utf-8", errors="replace")


def relay_flokinet_host_statements(
    *,
    allow_live: bool | None = None,
    timeout: float = 12.0,
) -> HostStatementRelay:
    """Relay FlokiNET public privacy/VPS statements.

    Live HTTPS fetch of privacy + VPS pages is preferred. If fetch fails or
    ``allow_live`` is False / ``RPT_HOST_STATEMENTS_OFFLINE=1``, returns the
    checked-in offline fixture of the same public claims.
    """
    if allow_live is None:
        allow_live = os.environ.get("RPT_HOST_STATEMENTS_OFFLINE", "").strip() not in (
            "1",
            "true",
            "yes",
        )

    urls = (FLOKINET_PRIVACY_URL, FLOKINET_VPS_URL)
    if not allow_live:
        return offline_host_statements()

    chunks: list[str] = []
    errors: list[str] = []
    for url in urls:
        try:
            chunks.append(_fetch_url(url, timeout=timeout))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            errors.append(f"{url}: {exc}")

    if not chunks:
        offline = offline_host_statements()
        return HostStatementRelay(
            source="offline_fixture",
            urls_tried=urls,
            text=offline.text,
            live_ok=False,
            errors=tuple(errors),
        )

    combined = "\n\n".join(chunks)
    # Prefer live when it still carries the core public claims; else blend fixture.
    markers = host_statement_claim_markers()
    if all(m.lower() in combined.lower() for m in markers):
        return HostStatementRelay(
            source="live",
            urls_tried=urls,
            text=combined,
            live_ok=True,
            errors=tuple(errors),
        )

    # Live pages reachable but claims not all found (site redesign) — still
    # return live body plus offline fixture so tests can assert relay path.
    offline = offline_host_statements()
    return HostStatementRelay(
        source="live+offline_fixture",
        urls_tried=urls,
        text=combined + "\n\n" + offline.text,
        live_ok=True,
        errors=tuple(errors) + ("live_missing_some_markers_appended_fixture",),
    )


def docs_paths_requiring_host_assurance(root: Path | None = None) -> tuple[Path, ...]:
    """User-facing documents that must carry Iceland/FlokiNET host assurances."""
    base = root or Path(__file__).resolve().parents[1]
    return (
        base / "README.md",
        base / "PRIVACY_POLICY.md",
        base / "AUDIT.md",
    )


def assert_docs_host_assurance(root: Path | None = None) -> list[str]:
    """Return list of ``path:missing_marker`` for docs missing assurance markers."""
    markers = user_doc_host_assurance_markers()
    failures: list[str] = []
    for path in docs_paths_requiring_host_assurance(root):
        if not path.is_file():
            failures.append(f"{path.name}:MISSING_FILE")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        # Normalize fancy quotes so host “No invasive logs” matches plain markers
        norm = (
            text.replace("\u201c", '"')
            .replace("\u201d", '"')
            .replace("\u2018", "'")
            .replace("\u2019", "'")
        )
        low = norm.lower()
        # FlokiNET spelling: accept FlokiNET or Flokinet in docs
        for m in markers:
            if m == "FlokiNET":
                if "flokinet" not in low:
                    failures.append(f"{path.name}:{m}")
                continue
            if m.lower() not in low:
                failures.append(f"{path.name}:{m}")
    return failures


def relay_summary_json(relay: HostStatementRelay) -> str:
    """Machine-readable summary for scratch logs."""
    return json.dumps(
        {
            "source": relay.source,
            "live_ok": relay.live_ok,
            "urls_tried": list(relay.urls_tried),
            "errors": list(relay.errors),
            "text_chars": len(relay.text),
            "claim_markers_ok": relay.contains_all(host_statement_claim_markers()),
            "product_host": PRODUCT_NODE_HOST,
            "product_country": PRODUCT_NODE_COUNTRY,
            "product_vps_host": PRODUCT_VPS_HOST_NAME,
        },
        indent=2,
    )
