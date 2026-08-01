"""Multi-layer advisories for single-click RESTORE (mandatory product copy)."""

from __future__ import annotations

# Confirmation phrase the user/operator must type or pass exactly.
RESTORE_CONFIRM_PHRASE = "RESTORE"

ADVISORY_LAYERS: tuple[dict[str, str], ...] = (
    {
        "id": "careful",
        "title": "BE CAREFUL",
        "body": (
            "RESTORE rpOS is a destructive product path. Pause and verify you "
            "selected the correct machine. Back up anything you still need."
        ),
    },
    {
        "id": "irreversible",
        "title": "IRREVERSIBLE",
        "body": (
            "Once confirmed, the product intent is absolute format and removal of "
            "existing files and settings on this device, then install of rpOS from "
            "scratch. This cannot be undone by undoing a single click."
        ),
    },
    {
        "id": "data_loss",
        "title": "DATA LOSS",
        "body": (
            "All personal files, applications, accounts, and system settings on the "
            "target disk are treated as removed under the wipe-intent pipeline. "
            "There is no recovery promise from Restore Privacy after confirmation."
        ),
    },
    {
        "id": "single_click",
        "title": "SINGLE-CLICK CONTROL",
        "body": (
            "The primary RESTORE executable is designed as one control after you "
            "have read these advisories. The control remains gated: wrong "
            "confirmation never proceeds."
        ),
    },
)


def advisory_text_blob() -> str:
    """Full multi-layer advisory text (for CLI / GUI / package banners)."""
    lines: list[str] = [
        "============================================================",
        "  RESTORE rpOS — MANDATORY SAFETY ADVISORIES",
        "  Read every layer before you continue.",
        "============================================================",
        "",
    ]
    for i, layer in enumerate(ADVISORY_LAYERS, start=1):
        lines.append(f"[{i}/{len(ADVISORY_LAYERS)}] {layer['title']}")
        lines.append(layer["body"])
        lines.append("")
    lines.append(
        f'To proceed you must confirm with the exact phrase: {RESTORE_CONFIRM_PHRASE}'
    )
    lines.append("Anything else aborts with no wipe and no install.")
    lines.append("============================================================")
    return "\n".join(lines)


def advisory_ids() -> list[str]:
    return [a["id"] for a in ADVISORY_LAYERS]


def has_required_warning_keywords(text: str) -> bool:
    """Structural check that advisories mention care, irreversible loss, data."""
    low = (text or "").lower()
    return all(
        k in low
        for k in ("careful", "irreversible", "data loss", "restore")
    )
