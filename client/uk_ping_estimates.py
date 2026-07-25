"""UK-user ping matrix for AUDIT + operator honesty.

When live probes succeed (device/host → product entry/exit via
:mod:`client.node_ping`), table cells use **measured** RTT. On probe failure
the section fails soft to documented approximate bands — never invents a live
ms figure.

Method honesty always states whether figures are live (this probe host) or
approximate UK estimates. Not a contractual SLA.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from client.endpoint import PRODUCT_NODE_HOST, PRODUCT_NODE_PORT
from client.multihop import PRODUCT_EXIT_HOST, PRODUCT_EXIT_PORT
from client.product_policy import PrivacyScalePrefs

# Approximate base RTT (ms) typical UK → monopin hosts (operator estimate band).
# Used only when live probe is unavailable.
UK_TO_ENTRY_MS_LOW = 38
UK_TO_ENTRY_MS_HIGH = 58
UK_TO_EXIT_MS_LOW = 32
UK_TO_EXIT_MS_HIGH = 52

# Extra latency *feel* when traffic shaping is on (jitter/cover — not pure RTT).
SHAPE_OVERHEAD_MS = 5
# Multi-hop residual-via-exit: residual path is exit; entry ping still listed.
MULTIHOP_NOTE = "residual dials exit when multi-hop on"

# Injectable probe callables: () -> PingResult-like with .ok and .rtt_ms
ProbeFn = Callable[[], object]


@dataclass(frozen=True)
class LiveRttBase:
    """Shared live base RTT from one probe pass (entry always; exit optional)."""

    entry_ms: float | None
    exit_ms: float | None
    entry_method: str = ""
    exit_method: str = ""
    entry_error: str = ""
    exit_error: str = ""

    @property
    def entry_live(self) -> bool:
        return self.entry_ms is not None and self.entry_ms >= 0

    @property
    def exit_live(self) -> bool:
        return self.exit_ms is not None and self.exit_ms >= 0


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
    entry_live: bool = False
    exit_live: bool = False

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
        if self.entry_live and self.entry_ms_low == self.entry_ms_high:
            return f"{self.entry_ms_low} ms (live)"
        if self.entry_live:
            # Live base + optional shape feel band
            return (
                f"{self.entry_ms_low}–{self.entry_ms_high} ms "
                f"(live base + shape feel)"
            )
        return f"{self.entry_ms_low}–{self.entry_ms_high} ms"

    def exit_range(self) -> str:
        if self.exit_ms_low is None or self.exit_ms_high is None:
            return "n/a (multi-hop off)"
        if self.exit_live and self.exit_ms_low == self.exit_ms_high:
            return f"{self.exit_ms_low} ms (live)"
        if self.exit_live:
            return (
                f"{self.exit_ms_low}–{self.exit_ms_high} ms "
                f"(live base + shape feel)"
            )
        return f"{self.exit_ms_low}–{self.exit_ms_high} ms"

    def rag_cell(self) -> str:
        if self.rag == "green":
            return "🟩"
        if self.rag == "red":
            return "🟥"
        return "🟧"


def measure_live_rtt_base(
    *,
    probe_entry: ProbeFn | None = None,
    probe_exit: ProbeFn | None = None,
    timeout_s: float = 1.5,
) -> LiveRttBase:
    """Probe entry + exit once. Defaults to :mod:`client.node_ping` helpers."""
    if probe_entry is None or probe_exit is None:
        from client.node_ping import probe_entry_rtt_ms, probe_exit_rtt_ms

        if probe_entry is None:
            probe_entry = lambda: probe_entry_rtt_ms(timeout_s=timeout_s)  # noqa: E731
        if probe_exit is None:
            probe_exit = lambda: probe_exit_rtt_ms(timeout_s=timeout_s)  # noqa: E731

    entry_ms: float | None = None
    exit_ms: float | None = None
    entry_method = ""
    exit_method = ""
    entry_error = ""
    exit_error = ""

    try:
        er = probe_entry()
        if getattr(er, "ok", False) and getattr(er, "rtt_ms", None) is not None:
            entry_ms = float(er.rtt_ms)
            entry_method = str(getattr(er, "method", "") or "probe")
        else:
            entry_error = str(getattr(er, "error", "") or "probe_failed")[:80]
            entry_method = str(getattr(er, "method", "") or "")
    except Exception as exc:  # noqa: BLE001
        entry_error = str(exc)[:80]

    try:
        xr = probe_exit()
        if getattr(xr, "ok", False) and getattr(xr, "rtt_ms", None) is not None:
            exit_ms = float(xr.rtt_ms)
            exit_method = str(getattr(xr, "method", "") or "probe")
        else:
            exit_error = str(getattr(xr, "error", "") or "probe_failed")[:80]
            exit_method = str(getattr(xr, "method", "") or "")
    except Exception as exc:  # noqa: BLE001
        exit_error = str(exc)[:80]

    return LiveRttBase(
        entry_ms=entry_ms,
        exit_ms=exit_ms,
        entry_method=entry_method,
        exit_method=exit_method,
        entry_error=entry_error,
        exit_error=exit_error,
    )


def _estimate_row(
    prefs: PrivacyScalePrefs,
    *,
    live: LiveRttBase | None = None,
) -> UkPingRow:
    live = live or LiveRttBase(entry_ms=None, exit_ms=None)
    entry_live = False
    exit_live = False

    if live.entry_live:
        base = int(round(float(live.entry_ms)))  # type: ignore[arg-type]
        base = max(0, base)
        entry_live = True
        if prefs.traffic_shape:
            entry_lo = base
            entry_hi = base + SHAPE_OVERHEAD_MS
        else:
            entry_lo = entry_hi = base
    else:
        entry_lo = UK_TO_ENTRY_MS_LOW
        entry_hi = UK_TO_ENTRY_MS_HIGH
        if prefs.traffic_shape:
            entry_lo += SHAPE_OVERHEAD_MS
            entry_hi += SHAPE_OVERHEAD_MS

    if prefs.multihop:
        if live.exit_live:
            xbase = int(round(float(live.exit_ms)))  # type: ignore[arg-type]
            xbase = max(0, xbase)
            exit_live = True
            if prefs.traffic_shape:
                exit_lo = xbase
                exit_hi = xbase + SHAPE_OVERHEAD_MS
            else:
                exit_lo = exit_hi = xbase
        else:
            exit_lo = UK_TO_EXIT_MS_LOW
            exit_hi = UK_TO_EXIT_MS_HIGH
            if prefs.traffic_shape:
                exit_lo += SHAPE_OVERHEAD_MS
                exit_hi += SHAPE_OVERHEAD_MS
        notes = MULTIHOP_NOTE + "; " + (
            "shape on adds modest jitter/cover feel"
            if prefs.traffic_shape
            else "shape off leaner"
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

    if entry_live:
        notes += "; entry RTT live probe this host"
    else:
        notes += "; entry RTT approximate UK band"
    if prefs.multihop:
        if exit_live:
            notes += "; exit RTT live probe this host"
        else:
            notes += "; exit RTT approximate UK band"

    # Green when entry (and exit if multihop) is live; else amber approx
    if entry_live and (not prefs.multihop or exit_live):
        rag = "green"
    elif entry_live:
        rag = "amber"  # partial live (entry only, exit approx)
    else:
        rag = "amber"

    return UkPingRow(
        traffic_shape=prefs.traffic_shape,
        outer_obfuscation=prefs.outer_obfuscation,
        multihop=prefs.multihop,
        entry_ms_low=entry_lo,
        entry_ms_high=entry_hi,
        exit_ms_low=exit_lo,
        exit_ms_high=exit_hi,
        rag=rag,
        notes=notes,
        entry_live=entry_live,
        exit_live=exit_live,
    )


def all_privacy_scale_prefs() -> list[PrivacyScalePrefs]:
    """All 8 combinations of shape × obfs × multihop.

    Order is deterministic for the AUDIT table: **on before off** in each
    column, so the first row is on/on/on and the last is off/off/off
    (shape → outer obfs → multi-hop).
    """
    out: list[PrivacyScalePrefs] = []
    for shape in (True, False):
        for obfs in (True, False):
            for mh in (True, False):
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
    *,
    live: LiveRttBase | None = None,
) -> list[UkPingRow]:
    """Build matrix rows. Pass *live* from :func:`measure_live_rtt_base` or tests."""
    prefs = list(prefs_list) if prefs_list is not None else all_privacy_scale_prefs()
    return [_estimate_row(p, live=live) for p in prefs]


def render_audit_uk_ping_section(
    *,
    live: LiveRttBase | None = None,
    measure: bool = True,
    probe_entry: ProbeFn | None = None,
    probe_exit: ProbeFn | None = None,
    timeout_s: float = 1.5,
) -> str:
    """Markdown section for AUDIT.md — UK ping + RAG by settings.

    When *measure* is True and *live* is None, probes entry/exit once via
    :func:`measure_live_rtt_base` (injectable *probe_entry* / *probe_exit*).
    """
    if live is None and measure:
        live = measure_live_rtt_base(
            probe_entry=probe_entry,
            probe_exit=probe_exit,
            timeout_s=timeout_s,
        )
    elif live is None:
        live = LiveRttBase(entry_ms=None, exit_ms=None)

    rows = uk_ping_matrix_rows(live=live)
    any_entry_live = any(r.entry_live for r in rows)
    any_exit_live = any(r.exit_live for r in rows)

    title = "## Privacy-scale settings — UK ping + RAG"
    lines = [
        title,
        "",
        "Customer **Settings → Browsing speed / privacy scale** can turn optional",
        "residual layers on/off. Residual VPN core (licence/keygen, HELLO crypto,",
        "system capture) stays required. This table helps users set latency expectations.",
        "",
        "### Method (honesty)",
        "",
    ]

    if any_entry_live or any_exit_live:
        lines.extend(
            [
                "- **Live** RTT where probes succeeded from **this audit host** to product",
                f"  **entry** `{PRODUCT_NODE_HOST}:{PRODUCT_NODE_PORT}` (Iceland)",
            ]
        )
        if any_exit_live:
            lines.append(
                f"  and **exit** `{PRODUCT_EXIT_HOST}:{PRODUCT_EXIT_PORT}` (Romania)."
            )
        else:
            lines.append(
                f"  (exit `{PRODUCT_EXIT_HOST}:{PRODUCT_EXIT_PORT}` used approximate UK band "
                "when multi-hop rows need it and exit probe failed)."
            )
        if live.entry_live:
            em = live.entry_method or "probe"
            lines.append(
                f"- Entry probe: **{int(round(live.entry_ms or 0))} ms** "
                f"via `{em}` (shared base across rows)."
            )
        if live.exit_live:
            xm = live.exit_method or "probe"
            lines.append(
                f"- Exit probe: **{int(round(live.exit_ms or 0))} ms** "
                f"via `{xm}` (shared base for multi-hop rows)."
            )
        lines.extend(
            [
                "- Live ms are from **this host's path**, not guaranteed London UK RTT.",
                "- Traffic shaping **feel** may add a small band on top of live base",
                f"  (+0–{SHAPE_OVERHEAD_MS} ms labeled); outer obfs ~0 ms RTT.",
                "- **Not** a contractual SLA. Failed probes fall back to approximate UK bands",
                "  (never invent live ms).",
                "- **RAG:** 🟩 Green = live base RTT available for the row; "
                "🟧 Amber = approximate / partial.",
            ]
        )
    else:
        lines.extend(
            [
                "- **Approximate** RTT bands for a **typical UK** (London metro) user to",
                f"  product **entry** `{PRODUCT_NODE_HOST}:{PRODUCT_NODE_PORT}` (Iceland) and",
                f"  **exit** `{PRODUCT_EXIT_HOST}:{PRODUCT_EXIT_PORT}` (Romania).",
                "- Live probe from this host **failed or unavailable** — using estimate bands only.",
            ]
        )
        if live.entry_error:
            lines.append(f"- Entry probe error: `{live.entry_error[:60]}`.")
        if live.exit_error:
            lines.append(f"- Exit probe error: `{live.exit_error[:60]}`.")
        lines.extend(
            [
                "- **Not** a contractual SLA.",
                "- Traffic shaping adds a small **feel** overhead (bounded jitter/cover);",
                "  outer obfuscation is ~0 ms RTT; multi-hop residual dials **exit**.",
                "- **RAG:** 🟧 Amber = approximate RTT estimate; monopin hosts are product pins.",
                "- Client Settings shows **live probe** ms (device→entry / exit) when measured.",
            ]
        )

    entry_hdr = "UK→entry (live)" if any_entry_live else "UK→entry (approx)"
    exit_hdr = "UK→exit (live)" if any_exit_live else "UK→exit (approx)"
    # Mixed: say live/approx
    if any_entry_live and not any_exit_live:
        exit_hdr = "UK→exit (approx)"
    if any_exit_live and not any_entry_live:
        entry_hdr = "UK→entry (approx)"

    lines.extend(
        [
            "",
            f"| Shape | Outer obfs | Multi-hop | {entry_hdr} | {exit_hdr} | RAG | Notes |",
            "|-------|------------|-----------|-------------------|------------------|-----|-------|",
        ]
    )
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


def replace_audit_uk_ping_section(audit_text: str, section_md: str | None = None) -> str:
    """Replace the UK ping section in an AUDIT.md body (or append if missing)."""
    import re

    section = section_md if section_md is not None else render_audit_uk_ping_section()
    # Match heading variants (approx / live title)
    pattern = re.compile(
        r"## Privacy-scale settings — UK[^\n]*\n"
        r".*?"
        r"(?=\n## |\n# |\Z)",
        re.DOTALL,
    )
    body = section.rstrip() + "\n"
    if pattern.search(audit_text):
        return pattern.sub(body + "\n", audit_text, count=1)
    # Insert before first "## 1." executive summary if present
    m = re.search(r"\n## 1\.\s", audit_text)
    if m:
        return audit_text[: m.start()] + "\n" + body + "\n" + audit_text[m.start() + 1 :]
    return audit_text.rstrip() + "\n\n" + body + "\n"
