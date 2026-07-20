"""Shared product copy: anonymous registration vs OS residual privilege.

Anonymous device admission uses a local per-device key with **no** admin/operator
verification, email, phone, or captcha. Residual full tunnel still needs OS
Administrator/root on Windows/Linux — that is privilege, not registration.
"""

from __future__ import annotations

ANON_REGISTRATION_TITLE = "Anonymous device registration"
ANON_REGISTRATION_SUMMARY = (
    "This app creates a unique device key on first Connect — anonymous free-product "
    "admission with no email, phone, or captcha, and no admin/operator verification."
)

# Explicit split: registration ≠ residual elevation
OS_PRIVILEGE_HONESTY = (
    "Residual public-IP capture on Windows/Linux still needs Administrator or root "
    "for the system tunnel (Wintun / TUN + dual /1 routes). That is OS privilege for "
    "routing — not operator approval of your registration."
)

SEAMLESS_TAGLINE = "Private VPN · one tap Connect · local-only prefs"
SEAMLESS_HINT = (
    "Accept the licence once, then Connect. Anonymous device key — no admin "
    "verification to register. Residual tunnel may still request OS elevation."
)

# Greppable markers for structural tests
ANON_REGISTRATION_MARKERS: tuple[str, ...] = (
    "no admin/operator verification",
    "anonymous",
    "device key",
)
NO_ADMIN_VERIFICATION_MARKER = "no admin/operator verification"


def registration_requires_admin_verification() -> bool:
    """Product free path: False — device bootstrap needs no operator approval."""
    return False


def registration_requires_email_or_phone() -> bool:
    return False
