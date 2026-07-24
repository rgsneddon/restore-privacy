"""First-run product surface sequencing (licence → keygen → settings → main).

Pure decision helpers used by the Windows (and optionally other) product entry.
No Tk here — callers present the surface named by :func:`first_run_next_surface`.

Does **not** bypass keygen: unlock-absent installs always report ``keygen``
after licence acceptance (and never ``main`` until keygen unlock + settings OK).
"""

from __future__ import annotations

from typing import Any, Literal, Optional

FirstRunSurface = Literal["licence", "renew", "keygen", "settings", "main"]

# settings.json key — set only when user explicitly OK/binds first-run settings
KEY_FIRST_RUN_SETTINGS_COMPLETED = "first_run_settings_completed"

# Geometry hints for first-run settings (large enough for primary controls)
FIRST_RUN_SETTINGS_GEOMETRY = "640x920"
FIRST_RUN_SETTINGS_MINSIZE = (560, 720)
MAIN_CONNECT_GEOMETRY = "560x620"


def needs_first_run_settings(
    *,
    settings: Any | None = None,
    path: Optional[Any] = None,
) -> bool:
    """True until the user has OK'd first-run settings after keygen unlock.

    When keygen unlock is still required, this returns False (keygen first).
    """
    from client.licence_gate import has_accepted_licence, needs_keygen_unlock
    from client.licence_gate import needs_licence_renewal

    if not has_accepted_licence():
        return False
    if needs_licence_renewal():
        return False
    if needs_keygen_unlock():
        return False
    if settings is not None:
        return not bool(getattr(settings, "first_run_settings_completed", False))
    try:
        from client.windows.settings_store import load_settings

        s = load_settings(path=path) if path is not None else load_settings()
        return not bool(getattr(s, "first_run_settings_completed", False))
    except Exception:
        return True


def first_run_next_surface(
    *,
    licence_path: Optional[Any] = None,
    settings: Any | None = None,
    settings_path: Optional[Any] = None,
) -> FirstRunSurface:
    """Which surface cold-start / post-step UI must present.

    Order (product first-run):
    1. ``licence`` — accept end-user licence
    2. ``renew`` — expired / blocking payment (not keygen)
    3. ``keygen`` — enter fulfilment RPT-KEY-… to unlock install
    4. ``settings`` — first-run settings (OK binds + dismisses)
    5. ``main`` — main Connect shell
    """
    from client.licence_gate import (
        has_accepted_licence,
        needs_keygen_unlock,
        needs_licence_renewal,
    )

    if not has_accepted_licence(licence_path):
        return "licence"
    if needs_licence_renewal(licence_path):
        return "renew"
    if needs_keygen_unlock(licence_path):
        return "keygen"
    if needs_first_run_settings(settings=settings, path=settings_path):
        return "settings"
    return "main"


def first_run_demands_keygen(
    *,
    licence_path: Optional[Any] = None,
) -> bool:
    """True when the product must force the keygen unlock window."""
    return first_run_next_surface(licence_path=licence_path) == "keygen"


def mark_first_run_settings_completed(
    *,
    path: Optional[Any] = None,
    settings: Any | None = None,
) -> Any:
    """Persist first-run settings OK (binds prefs + clears settings surface)."""
    from client.windows.settings_store import (
        ProductSettings,
        load_settings,
        save_settings,
    )

    s = settings if settings is not None else load_settings(path=path)
    if not isinstance(s, ProductSettings):
        s = load_settings(path=path)
    s.first_run_settings_completed = True
    save_settings(s, path=path)
    return s


def post_keygen_next_surface(
    *,
    licence_path: Optional[Any] = None,
    settings: Any | None = None,
    settings_path: Optional[Any] = None,
) -> FirstRunSurface:
    """Surface after a successful keygen unlock (never keygen if unlock present)."""
    surface = first_run_next_surface(
        licence_path=licence_path,
        settings=settings,
        settings_path=settings_path,
    )
    if surface == "keygen":
        # Unlock just succeeded but gate still sees keygen — treat as settings
        # so UI can still present first-run settings rather than stalling.
        return "settings"
    return surface
