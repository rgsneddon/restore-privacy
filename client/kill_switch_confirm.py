"""Kill-switch Settings confirm gate (pure logic, no dialog I/O).

Mirrors ``client_app/lib/kill_switch_confirm.dart`` so Windows (and other
native clients) share the same enable semantics:

- Enable requires exact typed token ``KILLSWITCH`` (outer whitespace trimmed).
- Disable never requires a phrase.
- Cancel / wrong / empty enable leaves kill-switch **OFF**.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Exact token the user must type to enable kill-switch (case-sensitive).
KILL_SWITCH_CONFIRM_TOKEN = "KILLSWITCH"

# Dialog title / lead (all-caps warning).
KILL_SWITCH_CONFIRM_TITLE = "ARE YOU SURE?"

# Risk explanation shown when enabling kill-switch.
KILL_SWITCH_CONFIRM_RISK_BODY = (
    "Turning kill-switch ON can block all non-VPN traffic if residual drops. "
    "That may break captive portals, app/OS updates, local network access, "
    "and other connections until you turn it OFF or reconnect residual. "
    "Default is OFF for a reason. Type KILLSWITCH below to confirm enable."
)

# Confirm / cancel button labels.
KILL_SWITCH_CONFIRM_ACTION_LABEL = "Enable kill switch"
KILL_SWITCH_CONFIRM_CANCEL_LABEL = "Cancel"
KILL_SWITCH_CONFIRM_FIELD_HINT = "Type KILLSWITCH to confirm"

# Settings surface warning chrome (parity with Flutter leak_posture.dart).
KILL_SWITCH_WARNING_TITLE = "WARNING"
KILL_SWITCH_SETTINGS_LABEL = "KILL SWITCH"
KILL_SWITCH_SETTINGS_BODY = (
    "Optional fail-closed firewall when residual is connected. "
    "Default is OFF. Enabling requires typing KILLSWITCH after a clear warning. "
    "If residual drops while kill-switch is ON, non-VPN internet may be blocked "
    "until you turn it OFF or reconnect."
)
KILL_SWITCH_ENABLE_SWITCH_LABEL = "Enable kill switch"


@dataclass(frozen=True)
class KillSwitchConfirmDecision:
    """Result of evaluating whether a kill-switch opt-in change may persist."""

    allow_persist: bool
    next_opt_in: bool
    reason: str = ""


def evaluate_kill_switch_confirm(
    *,
    desired_on: bool,
    confirm_text: Optional[str] = None,
    cancelled: bool = False,
) -> KillSwitchConfirmDecision:
    """Pure gate for kill-switch Settings changes.

    - Turning **OFF** (``desired_on=False``): always allowed, no token needed.
    - Turning **ON** (``desired_on=True``): allowed only when ``confirm_text``
      equals :data:`KILL_SWITCH_CONFIRM_TOKEN` exactly (after outer trim).
    - Empty / wrong / cancelled ON attempts: ``allow_persist`` false, next off.
    """
    if not desired_on:
        return KillSwitchConfirmDecision(
            allow_persist=True,
            next_opt_in=False,
            reason="disable_no_confirm",
        )
    if cancelled:
        return KillSwitchConfirmDecision(
            allow_persist=False,
            next_opt_in=False,
            reason="enable_cancelled",
        )
    typed = (confirm_text or "").strip()
    if typed == KILL_SWITCH_CONFIRM_TOKEN:
        return KillSwitchConfirmDecision(
            allow_persist=True,
            next_opt_in=True,
            reason="enable_token_ok",
        )
    return KillSwitchConfirmDecision(
        allow_persist=False,
        next_opt_in=False,
        reason="enable_empty_token" if not typed else "enable_wrong_token",
    )


def kill_switch_confirm_token_matches(text: Optional[str]) -> bool:
    """True when *text* is the exact enable token (trim outer whitespace)."""
    return (text or "").strip() == KILL_SWITCH_CONFIRM_TOKEN
