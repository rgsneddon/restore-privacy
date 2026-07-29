"""HTTP security headers for the status website (probe / scanner recommendations).

Applied on every status-host response. HTML documents get the full six-header
set including framing denial. Same-origin paid ``/download`` (and entitlement
attachment) responses omit framing denial so the thank-you auto-start iframe
can still fetch the package; the thank-you HTML document itself remains DENY.
"""

from __future__ import annotations

# Verbatim probe values (criterion 1).
STRICT_TRANSPORT_SECURITY = "max-age=31536000; includeSubDomains; preload"
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "upgrade-insecure-requests"
)
# Same CSP but same-origin framing allowed (binary download / attachment).
CONTENT_SECURITY_POLICY_FRAMEABLE = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'self'; "
    "form-action 'self'; "
    "upgrade-insecure-requests"
)
X_FRAME_OPTIONS = "DENY"
X_CONTENT_TYPE_OPTIONS = "nosniff"
REFERRER_POLICY = "strict-origin-when-cross-origin"
PERMISSIONS_POLICY = (
    "camera=(), microphone=(), geolocation=(), interest-cohort=()"
)

# Six names always present on HTML/document responses.
SECURITY_HEADER_NAMES = (
    "Strict-Transport-Security",
    "Content-Security-Policy",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
)


def security_headers(*, allow_framing: bool = False) -> list[tuple[str, str]]:
    """Return header name/value pairs for a status-host response.

    *allow_framing*: when True (paid installer / entitlement attachment streams),
    omit ``X-Frame-Options: DENY`` and use ``frame-ancestors 'self'`` so the
    thank-you page's same-origin auto-download iframe works. HTML pages must
    call with the default ``False``.
    """
    csp = (
        CONTENT_SECURITY_POLICY_FRAMEABLE
        if allow_framing
        else CONTENT_SECURITY_POLICY
    )
    out: list[tuple[str, str]] = [
        ("Strict-Transport-Security", STRICT_TRANSPORT_SECURITY),
        ("Content-Security-Policy", csp),
        ("X-Content-Type-Options", X_CONTENT_TYPE_OPTIONS),
        ("Referrer-Policy", REFERRER_POLICY),
        ("Permissions-Policy", PERMISSIONS_POLICY),
    ]
    if not allow_framing:
        # Insert X-Frame-Options after CSP to match common probe ordering.
        out.insert(2, ("X-Frame-Options", X_FRAME_OPTIONS))
    return out


def apply_security_headers(
    handler: object, *, allow_framing: bool = False
) -> None:
    """Call ``handler.send_header`` for each security header."""
    send = getattr(handler, "send_header")
    for name, value in security_headers(allow_framing=allow_framing):
        send(name, value)
