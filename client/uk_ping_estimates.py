"""UK-user approximate ping matrix for AUDIT + operator honesty.

Figures are **approximate** one-way-ish RTT expectations for a typical UK
broadband user (London metro) to product monopin hosts — **not** live
measurements from this CI host and **not** contractual SLAs.

Method:
- Base RTT: public Internet geography to Iceland entry / Romania exit
  (operator-published approximate ranges for FlokiNET-class EU routes).
- Privacy-scale deltas: added **feel** / overhead from traffic shaping
  (jitter ≤40 ms bound, cover frames) and multi-hop residual-via-exit
  (user residual dials exit; entry still used for path honesty).
- Outer obfuscation: negligible RTT (+0–1 ms) — included as 0 for table clarity.
- RAG: GREEN = product monopin + structural confidence high; AMBER = approximate
  RTT (not live UK probe); RED unused for estimates alone.

Regenerate AUDIT section via :func:`render_audit_uk_ping_section`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from client.endpoint import PRODUCT_NODE_HOST, PRODUCT_NODE_PORT
from client.multihop import PRODUCT_EXIT_HOST, PRODUCT_EXIT_PORT
from client.product_policy import PrivacyScalePrefs

# Approximate base RTT (ms) typical UK → monopin hosts (operator estimate band).
UK_TO_ENTRY_MS_LOW = 38
UK_TO_ENTRY_MS_HIGH = 58
UK_TO_EXIT_MS_LOW = 32
UK_TO_EXIT_MS_HIGH = 52

# Extra latency *feel* when traffic shaping is on (jitter/cover — not pure RTT).
SHAPE_OVERHEAD_MS = 5
# Multi-hop residual-via-exit: residual path is exit; entry ping still listed.
MULTIHOP_NOTE = "residual dials exit when multi-hop on"


@dataclass(frozen=True)
class UkPingRow:
    """One privacy-scale configuration row for the AUDIT table."""

    traffic_shape: bool
    outer_obfuscation: bool
    multihop: bool
    entry_ms_low: int
    entry_ms_high: int
    exit_ms_low: int | None
    exit_ms_high: int | None
    rag: str  # "green" | "amber"
    notes: str

    @property
    def shape_label(self) -> str:
        return "on" if self.traffic_shape else "off"

    @property
    def obfs_label(self) -> str:
        return "on" if self.outer_obfuscation else "off"

    @property
    def multihop_label(self) -> str:
        return "on" if self.multihop else "off"

    def entry_range(self) -> str:
        return f"{self.entry_ms_low}–{self.entry_ms_high} ms"

    def exit_range(self) -> str:
        if self.exit_ms_low is None or self.exit_ms_high is None:
            return "n/a (multi-hop off)"
        return f"{self.exit_ms_low}–{self.exit_ms_high} ms"

    def rag_cell(self) -> str:
        if self.rag == "green":
            return "🟩"
        if self.rag == "red":
            return "🟥"
        return "🟧"


def _estimate_row(prefs: PrivacyScalePrefs) -> UkPingRow:
    entry_lo = UK_TO_ENTRY_MS_LOW
    entry_hi = UK_TO_ENTRY_MS_HIGH
    if prefs.traffic_shape:
        entry_lo += SHAPE_OVERHEAD_MS
        entry_hi += SHAPE_OVERHEAD_MS
    # Outer obfs ≈ 0 ms RTT delta
    if prefs.multihop:
        exit_lo = UK_TO_EXIT_MS_LOW
        exit_hi = UK_TO_EXIT_MS_HIGH
        if prefs.traffic_shape:
            exit_lo += SHAPE_OVERHEAD_MS
            exit_hi += SHAPE_OVERHEAD_MS
        notes = MULTIHOP_NOTE + "; " + (
            "shape on adds modest jitter/cover feel" if prefs.traffic_shape else "shape off leaner"
        )
    else:
        exit_lo = exit_hi = None
        notes = "single-hop residual → entry; " + (
            "shape on" if prefs.traffic_shape else "shape off (faster feel)"
        )
    if prefs.outer_obfuscation:
        notes += "; outer obfs on (QUIC-mimic, ~0 ms RTT)"
    else:
        notes += "; outer obfs off (bare RPT, ~0 ms RTT)"
    # Estimates always AMBER (approximate); monopin structure is high confidence
    return UkPingRow(
        traffic_shape=prefs.traffic_shape,
        outer_obfuscation=prefs.outer_obfuscation,
        multihop=prefs.multihop,
        entry_ms_low=entry_lo,
        entry_ms_high=entry_hi,
        exit_ms_low=exit_lo,
        exit_ms_high=exit_hi,
        rag="amber",
        notes=notes,
    )


def all_privacy_scale_prefs() -> list[PrivacyScalePrefs]:
    """All 8 combinations of shape × obfs × multihop."""
    out: list[PrivacyScalePrefs] = []
    for shape in (True, False):
        for obfs in (True, False):
            for mh in (False, True):
                out.append(
                    PrivacyScalePrefs(
                        traffic_shape=shape,
                        outer_obfuscation=obfs,
                        multihop=mh,
                    )
                )
    return out


def uk_ping_matrix_rows(
    prefs_list: Iterable[PrivacyScalePrefs] | None = None,
) -> list[UkPingRow]:
    prefs = list(prefs_list) if prefs_list is not None else all_privacy_scale_prefs()
    return [_estimate_row(p) for p in prefs]


def render_audit_uk_ping_section() -> str:
    """Markdown section for AUDIT.md — UK approximate ping + RAG by settings."""
    rows = uk_ping_matrix_rows()
    lines = [
        "## Privacy-scale settings — UK approximate ping + RAG",
        "",
        "Customer **Settings → Browsing speed / privacy scale** can turn optional",
        "residual layers on/off. Residual VPN core (licence/keygen, HELLO crypto,",
        "system capture) stays required. This table helps UK users set expectations.",
        "",
        "### Method (honesty)",
        "",
        "- **Approximate** RTT bands for a **typical UK** (London metro) user to",
        f"  product **entry** `{PRODUCT_NODE_HOST}:{PRODUCT_NODE_PORT}` (Iceland) and",
        f"  **exit** `{PRODUCT_EXIT_HOST}:{PRODUCT_EXIT_PORT}` (Romania).",
        "- **Not** live measurements from every CI host; **not** a contractual SLA.",
        "- Traffic shaping adds a small **feel** overhead (bounded jitter/cover);",
        "  outer obfuscation is ~0 ms RTT; multi-hop residual dials **exit**.",
        "- **RAG:** 🟧 Amber = approximate RTT estimate; monopin hosts are product pins.",
        "- Client Settings also shows **live probe** ms (device→entry / exit) when measured.",
        "",
        "| Shape | Outer obfs | Multi-hop | UK→entry (approx) | UK→exit (approx) | RAG | Notes |",
        "|-------|------------|-----------|-------------------|------------------|-----|-------|",
    ]
    for r in rows:
        lines.append(
            f"| {r.shape_label} | {r.obfs_label} | {r.multihop_label} | "
            f"{r.entry_range()} | {r.exit_range()} | {r.rag_cell()} | {r.notes} |"
        )
    lines.extend(
        [
            "",
            "**Product defaults:** shape **off**, outer obfs **off**, multi-hop **off**",
            "(lean single-hop entry). Turn shape/obfs **on** for stronger residual defenses;",
            "hot-apply while connected (multi-hop re-establishes residual).",
            "",
        ]
    )
    return "\n".join(lines)
