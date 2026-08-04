"""First-run product surface sequencing (licence → trial/KEYGEN → main).

Pure decision helpers used by the Windows (and optionally other) product entry.
No Tk here — callers present the surface named by :func:`first_run_next_surface`.

Order:
1. ``licence`` — accept end-user licence (once; durable)
2. ``renew`` — expired / blocking payment (not keygen)
3. ``keygen`` — step 2: continue free 72h trial **or** enter KEYGEN + buy link
4. ``main`` — connection screen

After a successful KEYGEN unlock, cold start skips licence and step 2 and
opens **main** (first-run Settings is no longer a blocking gate).
While trial is active / not started and no KEYGEN, cold start still lands on
step 2 so the user sees remaining trial time (Continue trial → main).
"""

from __future__ import annotations

from typing import Any, Literal, Optional

FirstRunSurface = Literal["licence", "renew", "keygen", "settings", "main"]

# settings.json key — set only when user explicitly OK/binds first-run settings
# (optional; not required for main after KEYGEN under current product policy).
KEY_FIRST_RUN_SETTINGS_COMPLETED = "first_run_settings_completed"

# Geometry hints for first-run settings (large enough for primary controls).
# Kept in sync with client.windows.ui_chrome.SURFACE_SIZES (settings_first_run / main).
FIRST_RUN_SETTINGS_GEOMETRY = "700x920"
FIRST_RUN_SETTINGS_MINSIZE = (620, 780)
MAIN_CONNECT_GEOMETRY = "600x680"


def needs_first_run_settings(
    *,
    settings: Any | None = None,
    path: Optional[Any] = None,
) -> bool:
    """Historical first-run Settings OK gate.

    Product policy for lean residual: **False** once licence + KEYGEN (or active
    trial entry) allow main — Settings is available from the main shell, not a
    blocking cold-start step after KEYGEN.
    """
    _ = settings, path
    return False


def needs_step2_trial_keygen_surface(
    *,
    licence_path: Optional[Any] = None,
) -> bool:
    """True when step 2 (trial time-left + KEYGEN entry) must be shown.

    Licence accepted, not on renew path, and no durable RPT-KEY unlock yet.
    Shown even while free trial is still available so the user sees remaining
    time on every cold start until they unlock with KEYGEN.
    """
    from client.licence_gate import has_accepted_licence, needs_licence_renewal
    from client.payment_entitlement import has_keygen_unlock

    if not has_accepted_licence(licence_path):
        return False
    if needs_licence_renewal(licence_path):
        return False
    if has_keygen_unlock():
        return False
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
    3. ``keygen`` — step 2 trial remaining + KEYGEN / buy link
    4. ``main`` — main Connect shell (after KEYGEN, or after Continue trial)
    """
    _ = settings, settings_path
    from client.licence_gate import (
        has_accepted_licence,
        needs_licence_renewal,
    )

    if not has_accepted_licence(licence_path):
        return "licence"
    if needs_licence_renewal(licence_path):
        return "renew"
    if needs_step2_trial_keygen_surface(licence_path=licence_path):
        return "keygen"
    return "main"


def first_run_demands_keygen(
    *,
    licence_path: Optional[Any] = None,
) -> bool:
    """True when cold-start must present the trial/KEYGEN step (step 2)."""
    return first_run_next_surface(licence_path=licence_path) == "keygen"


def mark_first_run_settings_completed(
    *,
    path: Optional[Any] = None,
    settings: Any | None = None,
) -> Any:
    """Persist first-run settings OK (optional; not required for main)."""
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
    """Surface after a successful keygen unlock — always main when unlocked."""
    surface = first_run_next_surface(
        licence_path=licence_path,
        settings=settings,
        settings_path=settings_path,
    )
    if surface == "keygen":
        # Unlock just succeeded but gate still sees step 2 — open main Connect.
        return "main"
    return surface
