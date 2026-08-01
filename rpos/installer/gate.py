"""Confirmation gate — wrong phrase must not start wipe/install pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .advisories import RESTORE_CONFIRM_PHRASE, advisory_text_blob


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    reason: str
    advisories_shown: bool


def evaluate_confirmation(
    user_input: str | None,
    *,
    advisories_acknowledged: bool = True,
) -> GateResult:
    """Return whether RESTORE pipeline may proceed.

    Requires advisories_acknowledged and exact confirmation phrase.
    """
    if not advisories_acknowledged:
        return GateResult(
            allowed=False,
            reason="advisories_not_acknowledged",
            advisories_shown=False,
        )
    phrase = (user_input or "").strip()
    if phrase != RESTORE_CONFIRM_PHRASE:
        return GateResult(
            allowed=False,
            reason="confirmation_rejected",
            advisories_shown=True,
        )
    return GateResult(
        allowed=True,
        reason="confirmation_accepted",
        advisories_shown=True,
    )


def require_restore_confirmation(user_input: str | None, **kwargs: Any) -> None:
    """Raise PermissionError if gate fails."""
    r = evaluate_confirmation(user_input, **kwargs)
    if not r.allowed:
        raise PermissionError(r.reason)


def gate_preview() -> dict[str, Any]:
    """Structured preview for smoke / UI (does not wipe)."""
    return {
        "confirm_phrase": RESTORE_CONFIRM_PHRASE,
        "advisories": advisory_text_blob(),
        "gate": "evaluate_confirmation",
    }
