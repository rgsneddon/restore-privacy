"""Privacy-scale ping matrix for AUDIT — DE–SG world-midpoint origin.

The published AUDIT ping **base/origin** is the exact great-circle midpoint
on Earth between the Germany residual node (``PRODUCT_DE_HOST``) and the
Singapore residual node (``PRODUCT_SG_HOST``). Midpoint→DE and midpoint→SG
distances (and therefore modeled base RTT) are equal. Singapore is not
scored as a UK→Singapore path.

Optional ``live=`` injection remains for unit tests of AVG→RAG only. The
audit write path never uses this laptop/UK (or Helsinki) ICMP as the
displayed base — there is no probe host at the geographic midpoint.

**RAG** is driven by each row's numeric **AVG** ms (not live-vs-approx):
  - 🟩 green when AVG &lt; 40
  - 🟧 amber when 40 ≤ AVG ≤ 70
  - 🟥 red when AVG &gt; 70

Not a contractual SLA.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable

from client.multihop import (
    PRODUCT_DE_HOST,
    PRODUCT_DE_PORT,
    PRODUCT_EXIT_HOST,
    PRODUCT_EXIT_PORT,
    PRODUCT_SG_HOST,
    PRODUCT_SG_PORT,
)
from client.product_policy import PrivacyScalePrefs

# Catalog residual node positions (decimal degrees). Hetzner Falkenstein
# campus for 178.105.187.178; Hetzner Cloud Singapore campus for 5.223.48.8.
DE_NODE_LATLON: tuple[float, float] = (50.47785, 12.37139)
SG_NODE_LATLON: tuple[float, float] = (1.32199, 103.69500)

# WGS84 mean Earth radius (km).
EARTH_RADIUS_KM = 6371.0088
# Group velocity in fiber ≈ 2/3 c ≈ 200 km per millisecond.
FIBER_KM_PER_MS = 200.0
# Typical Internet path stretch vs great-circle.
PATH_STRETCH = 1.5
# Symmetric modeled band around the midpoint base RTT (ms).
MIDPOINT_BAND_HALF_MS = 8

# Extra latency *feel* when traffic shaping is on (jitter/cover — not pure RTT).
SHAPE_OVERHEAD_MS = 5
# Multi-hop residual-via-exit: residual path is exit; entry ping still listed.
MULTIHOP_NOTE = "residual dials exit when multi-hop on"

# Latency RAG thresholds (ms) — AVG column drives the colour.
RAG_GREEN_MAX_MS = 40.0  # green when avg < this
RAG_AMBER_MAX_MS = 70.0  # amber when RAG_GREEN_MAX_MS <= avg <= this; else red

# Injectable probe callables: () -> PingResult-like with .ok and .rtt_ms
ProbeFn = Callable[[], object]


def haversine_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Great-circle distance (km) on a sphere of radius :data:`EARTH_RADIUS_KM`."""
    φ1, λ1, φ2, λ2 = (math.radians(lat1), math.radians(lon1), math.radians(lat2), math.radians(lon2))
    dφ = φ2 - φ1
    dλ = λ2 - λ1
    a = math.sin(dφ / 2.0) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def great_circle_midpoint(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> tuple[float, float]:
    """Exact great-circle midpoint (lat, lon degrees) between two positions."""
    φ1, λ1, φ2, λ2 = (math.radians(lat1), math.radians(lon1), math.radians(lat2), math.radians(lon2))
    x1 = math.cos(φ1) * math.cos(λ1)
    y1 = math.cos(φ1) * math.sin(λ1)
    z1 = math.sin(φ1)
    x2 = math.cos(φ2) * math.cos(λ2)
    y2 = math.cos(φ2) * math.sin(λ2)
    z2 = math.sin(φ2)
    x, y, z = x1 + x2, y1 + y2, z1 + z2
    hyp = math.hypot(x, y)
    φm = math.atan2(z, hyp)
    λm = math.atan2(y, x)
    return (math.degrees(φm), math.degrees(λm))


def modeled_base_rtt_ms(distance_km: float) -> float:
    """Modeled RTT (ms) for a great-circle path of *distance_km*.

    Round-trip at fiber group velocity (``FIBER_KM_PER_MS``) times
    ``PATH_STRETCH`` (typical Internet path vs great-circle).
    """
    km = max(0.0, float(distance_km))
    return (2.0 * km / FIBER_KM_PER_MS) * PATH_STRETCH


def format_latlon(lat: float, lon: float) -> str:
    """Human lat/lon for honesty text, e.g. ``32.1234°N, 58.0456°E``."""
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{abs(lat):.4f}°{ns}, {abs(lon):.4f}°{ew}"


@dataclass(frozen=True)
class MidpointOrigin:
    """DE–SG great-circle midpoint used as the AUDIT ping base."""

    lat: float
    lon: float
    km_to_de: float
    km_to_sg: float
    base_rtt_ms: float
    de_host: str
    sg_host: str
    de_latlon: tuple[float, float]
    sg_latlon: tuple[float, float]

    def format_coords(self) -> str:
        return format_latlon(self.lat, self.lon)


def catalog_peer_positions() -> dict[str, tuple[float, float]]:
    """Shipped residual node positions keyed by catalog host."""
    return {
        PRODUCT_DE_HOST: DE_NODE_LATLON,
        PRODUCT_SG_HOST: SG_NODE_LATLON,
    }


def ping_origin_midpoint() -> MidpointOrigin:
    """Great-circle midpoint between the Germany and Singapore residual nodes.

    Midpoint→DE and midpoint→SG haversine distances are equal (half the
    DE↔SG arc). Modeled base RTT to each peer is therefore equal.
    """
    de = DE_NODE_LATLON
    sg = SG_NODE_LATLON
    mid = great_circle_midpoint(de[0], de[1], sg[0], sg[1])
    km_de = haversine_km(mid[0], mid[1], de[0], de[1])
    km_sg = haversine_km(mid[0], mid[1], sg[0], sg[1])
    # Equal distances → equal modeled RTT; use DE leg (same as SG).
    rtt = modeled_base_rtt_ms(km_de)
    return MidpointOrigin(
        lat=mid[0],
        lon=mid[1],
        km_to_de=km_de,
        km_to_sg=km_sg,
        base_rtt_ms=rtt,
        de_host=PRODUCT_DE_HOST,
        sg_host=PRODUCT_SG_HOST,
        de_latlon=de,
        sg_latlon=sg,
    )


def midpoint_peer_band_ms() -> tuple[int, int]:
    """Inclusive lo–hi modeled RTT (ms) from the DE–SG midpoint to either peer."""
    origin = ping_origin_midpoint()
    mid = int(round(origin.base_rtt_ms))
    return max(1, mid - MIDPOINT_BAND_HALF_MS), mid + MIDPOINT_BAND_HALF_MS


def rag_from_avg_ms(avg_ms: float) -> str:
    """Map numeric AVG RTT (ms) → ``green`` | ``amber`` | ``red``.

    Thresholds (inclusive amber band):
      - green: avg < 40
      - amber: 40 ≤ avg ≤ 70
      - red: avg > 70
    """
    try:
        a = float(avg_ms)
    except (TypeError, ValueError):
        return "amber"
    if a < RAG_GREEN_MAX_MS:
        return "green"
    if a <= RAG_AMBER_MAX_MS:
        return "amber"
    return "red"


def row_avg_ms(
    *,
    entry_ms_low: int,
    entry_ms_high: int,
    exit_ms_low: int | None,
    exit_ms_high: int | None,
    multihop: bool,
) -> float:
    """Numeric AVG ms for a privacy-scale row.

    Single-hop: midpoint of the entry lo–hi band (equals live base when lo==hi).
    Multi-hop: mean of entry midpoint and exit midpoint (both legs listed).
    """
    entry_avg = (float(entry_ms_low) + float(entry_ms_high)) / 2.0
    if multihop and exit_ms_low is not None and exit_ms_high is not None:
        exit_avg = (float(exit_ms_low) + float(exit_ms_high)) / 2.0
        return (entry_avg + exit_avg) / 2.0
    return entry_avg


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
    rag: str  # "green" | "amber" | "red" — from AVG thresholds
    notes: str
    entry_live: bool = False
    exit_live: bool = False
    avg_ms: float = 0.0  # numeric AVG used for RAG (ms)

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

    def avg_display(self) -> str:
        """Formatted AVG cell (one decimal when needed)."""
        a = float(self.avg_ms)
        if abs(a - round(a)) < 1e-9:
            return f"{int(round(a))} ms"
        return f"{a:.1f} ms"

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
        entry_lo, entry_hi = midpoint_peer_band_ms()
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
            exit_lo, exit_hi = midpoint_peer_band_ms()
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
        notes += "; DE RTT injected (not UK/laptop origin)"
    else:
        notes += "; DE RTT modeled from DE–SG midpoint"
    if prefs.multihop:
        if exit_live:
            notes += "; SG RTT injected (not UK/laptop origin)"
        else:
            notes += "; SG RTT modeled from DE–SG midpoint"

    avg = row_avg_ms(
        entry_ms_low=entry_lo,
        entry_ms_high=entry_hi,
        exit_ms_low=exit_lo,
        exit_ms_high=exit_hi,
        multihop=prefs.multihop,
    )
    # RAG from AVG only (not live-vs-approx)
    rag = rag_from_avg_ms(avg)
    notes += f"; AVG {avg:.1f} ms → {rag}"

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
        avg_ms=avg,
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
    measure: bool = False,
    probe_entry: ProbeFn | None = None,
    probe_exit: ProbeFn | None = None,
    timeout_s: float = 1.5,
) -> str:
    """Markdown section for AUDIT.md — DE–SG midpoint ping + RAG by settings.

    The displayed origin is always the DE–SG great-circle midpoint unless
    *live* is explicitly passed (unit tests of AVG→RAG). *measure* / host
    probes are **not** the matrix origin — a UK or Helsinki laptop path
    would recreate UK→Singapore scoring.

    *probe_entry* / *probe_exit* / *timeout_s* are retained for API compat
    and only used when *live* is None **and** *measure* is True **and**
    callers pass an explicit *live* overlay; they do not become the base.
    """
    # Host ICMP from a non-midpoint machine is never the displayed origin.
    # Explicit live= still overlays RTTs so RAG unit tests drive the same
    # row builder the audit uses.
    if live is None:
        live = LiveRttBase(entry_ms=None, exit_ms=None)
    _ = (measure, probe_entry, probe_exit, timeout_s)  # API compat; not origin

    origin = ping_origin_midpoint()
    band_lo, band_hi = midpoint_peer_band_ms()
    rows = uk_ping_matrix_rows(live=live)
    any_entry_live = any(r.entry_live for r in rows)
    any_exit_live = any(r.exit_live for r in rows)

    title = "## Privacy-scale settings — DE–SG midpoint ping + RAG"
    de_cell = f"`{PRODUCT_DE_HOST}:{PRODUCT_DE_PORT}`"
    sg_cell = f"`{PRODUCT_SG_HOST}:{PRODUCT_SG_PORT}`"
    lines = [
        title,
        "",
        "Customer **Settings → Browsing speed / privacy scale** can turn optional",
        "residual layers on/off. Residual VPN core (licence/keygen, HELLO crypto,",
        "system capture) stays required. This table helps users set latency expectations.",
        "",
        "### Method (honesty)",
        "",
        "- **Ping base/origin:** exact great-circle midpoint on Earth between the",
        f"  Germany residual {de_cell} and the Singapore residual {sg_cell}",
        "  — halfway between Germany and Singapore.",
        f"- Midpoint coordinates: **{origin.format_coords()}**.",
        f"- Midpoint→DE = **{origin.km_to_de:.1f} km**; Midpoint→SG = **{origin.km_to_sg:.1f} km**",
        "  (equal under the same midpoint function). Modeled base RTT is therefore",
        f"  equal: **{origin.base_rtt_ms:.1f} ms** each (fiber ≈ 2/3 *c* × path stretch",
        f"  {PATH_STRETCH:g}; band {band_lo}–{band_hi} ms).",
        "- Singapore is **not** scored from a United Kingdom origin. This audit",
        "  host's live ICMP (laptop / Helsinki) is **not** the displayed base.",
        f"- Catalog peers: Germany {de_cell}; Singapore {sg_cell}.",
        "  Multi-hop residual still dials the product **exit** "
        f"`{PRODUCT_EXIT_HOST}:{PRODUCT_EXIT_PORT}` (Germany); the SG column is the",
        "  midpoint→Singapore catalog-peer figure (equal modeled RTT).",
    ]

    if any_entry_live or any_exit_live:
        lines.extend(
            [
                "- Optional **injected** RTT overlay is present (tests / explicit",
                "  `live=`); it is **not** a UK/laptop origin and does not rename",
                "  the midpoint columns.",
            ]
        )
        if live.entry_live:
            em = live.entry_method or "injected"
            lines.append(
                f"- DE overlay: **{int(round(live.entry_ms or 0))} ms** via `{em}`."
            )
        if live.exit_live:
            xm = live.exit_method or "injected"
            lines.append(
                f"- SG overlay: **{int(round(live.exit_ms or 0))} ms** via `{xm}`."
            )

    lines.extend(
        [
            "- Traffic shaping adds a small **feel** overhead (bounded jitter/cover);",
            "  outer obfuscation is ~0 ms RTT.",
            "- **Not** a contractual SLA. Midpoint-modeled RTT can still exceed 70 ms",
            "  (RAG may stay red); the objective is a fair halfway origin, not a green SLA.",
            "- **AVG** is the numeric mean used for RAG: single-hop = DE (entry) band",
            "  midpoint; multi-hop = mean of DE and SG band midpoints.",
            "- **RAG (from AVG only):** 🟩 Green = AVG **&lt; 40 ms**; "
            "🟧 Amber = **40–70 ms**; 🟥 Red = AVG **&gt; 70 ms**.",
            "- Client Settings still shows **live device→node** probe ms when measured;",
            "  that Settings surface is not this AUDIT matrix origin.",
        ]
    )

    de_hdr = "Midpoint→DE"
    sg_hdr = "Midpoint→SG"

    lines.extend(
        [
            "",
            f"| Shape | Outer obfs | Multi-hop | {de_hdr} | {sg_hdr} | AVG | RAG | Notes |",
            "|-------|------------|-----------|-------------------|------------------|-----|-----|-------|",
        ]
    )
    for r in rows:
        lines.append(
            f"| {r.shape_label} | {r.obfs_label} | {r.multihop_label} | "
            f"{r.entry_range()} | {r.exit_range()} | {r.avg_display()} | "
            f"{r.rag_cell()} | {r.notes} |"
        )
    lines.extend(
        [
            "",
            f"**Equal modeled base:** midpoint→`{PRODUCT_DE_HOST}` = "
            f"midpoint→`{PRODUCT_SG_HOST}` = **{origin.base_rtt_ms:.1f} ms** "
            f"({origin.km_to_de:.1f} km each).",
            "",
            "**Product defaults:** shape **off**, outer obfs **off**, multi-hop **off**",
            "(lean single-hop entry). Turn shape/obfs **on** for stronger residual defenses;",
            "hot-apply while connected (multi-hop re-establishes residual).",
            "",
        ]
    )
    return "\n".join(lines)


def replace_audit_uk_ping_section(audit_text: str, section_md: str | None = None) -> str:
    """Replace the privacy-scale ping section in an AUDIT.md body (or append)."""
    import re

    section = section_md if section_md is not None else render_audit_uk_ping_section()
    # Old UK heading and new DE–SG midpoint heading.
    pattern = re.compile(
        r"## Privacy-scale settings — (?:UK|DE–SG midpoint)[^\n]*\n"
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
