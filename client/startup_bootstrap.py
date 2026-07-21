"""First-launch helpers: entitlement auto-provision for fastest Connect path.

Call once on product UI start so post-pay ``payment_entitlement.json`` (Downloads
or install dir) is imported and the device is bound before the user taps Connect.
Does not bypass licence or payment gates.
"""

from __future__ import annotations

from typing import Any, Optional


def bootstrap_payment_entitlement(
    *,
    bind_device: bool = True,
    base_url: Optional[str] = None,
) -> Any:
    """Discover/import entitlement + optional remote bind. Never raises."""
    try:
        from client.payment_entitlement import ensure_entitlement_for_connect

        return ensure_entitlement_for_connect(
            bind_device=bind_device, base_url=base_url
        )
    except Exception:  # noqa: BLE001
        return None


def ready_for_fast_connect() -> tuple[bool, str]:
    """True when licence + payment already allow Connect (no Settings tour)."""
    try:
        from client.licence_gate import assert_may_connect

        return assert_may_connect()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
