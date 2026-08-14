"""Set the Windows taskbar / title-bar icon to the Restore Privacy brand logo.

Tk ``iconbitmap`` alone often leaves the default Python/Tk feather on the
Windows taskbar. This module also applies Win32 ``WM_SETICON`` from the shipped
multi-size ``app_icon.ico`` and sets a stable AppUserModelID.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

# Stable id so Windows groups the app under the product brand (not python.exe).
APP_USER_MODEL_ID = "RestorePrivacy.Client.Windows"


def brand_icon_paths() -> tuple[Optional[Path], Optional[Path]]:
    """Return ``(ico_path, png_path)`` preferring shipped brand assets."""
    try:
        from client.windows.tray_win import resolve_tray_icon_path

        brand = resolve_tray_icon_path()
    except Exception:  # noqa: BLE001
        brand = None
    native = Path(__file__).resolve().parent / "native"
    ico = native / "app_icon.ico"
    png = native / "app_icon.png"
    if brand is not None and brand.is_file():
        if brand.suffix.lower() == ".ico":
            ico = brand
        elif brand.suffix.lower() == ".png":
            png = brand
    return (
        ico if ico.is_file() else None,
        png if png.is_file() else None,
    )


def set_process_app_user_model_id(app_id: str = APP_USER_MODEL_ID) -> bool:
    """Call before creating the main window so taskbar uses product identity."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(str(app_id))
        return True
    except Exception:  # noqa: BLE001
        return False


def apply_brand_window_icon(root: Any) -> dict[str, Any]:
    """Apply brand ICO/PNG to a Tk root (iconbitmap, iconphoto, WM_SETICON).

    Returns a small status dict for tests / diagnostics. Keeps PhotoImage refs
    on ``root`` (``_rpt_icon_photo``) so GC does not drop the icon.
    """
    status: dict[str, Any] = {
        "ico": None,
        "png": None,
        "iconbitmap": False,
        "iconphoto": False,
        "wm_seticon": False,
        "hwnd": None,
    }
    ico, png = brand_icon_paths()
    status["ico"] = str(ico) if ico else None
    status["png"] = str(png) if png else None

    if ico is not None:
        try:
            root.iconbitmap(default=str(ico.resolve()))
            status["iconbitmap"] = True
        except Exception:
            try:
                root.iconbitmap(str(ico.resolve()))
                status["iconbitmap"] = True
            except Exception:
                pass

    if png is not None:
        try:
            import tkinter as tk

            img = tk.PhotoImage(file=str(png.resolve()))
            root.iconphoto(True, img)
            # Keep reference
            root._rpt_icon_photo = img  # type: ignore[attr-defined]
            status["iconphoto"] = True
        except Exception:
            pass

    if sys.platform == "win32" and ico is not None:
        try:
            status["wm_seticon"] = bool(_win32_set_icons_from_ico(root, ico))
            try:
                hwnd = int(root.winfo_id())
                status["hwnd"] = hwnd
            except Exception:
                pass
        except Exception:
            pass
    return status


def _win32_set_icons_from_ico(root: Any, ico: Path) -> bool:
    """Load multi-size ICO and assign window + class icons (taskbar).

    Tk's default class icon is the feather; ``WM_SETICON`` alone is not always
    enough — also set ``GCL_HICON`` / ``GCL_HICONSM`` from ExtractIconEx.
    """
    import ctypes
    from ctypes import wintypes

    # Do not call update_idletasks here — re-entering Tk from after(200)
    # while the tray thread starts AVs the process on open (fault.log).
    try:
        # Tk frame hwnd; parent is often the real toplevel for taskbar
        hwnd = int(root.winfo_id())
        user32 = ctypes.windll.user32
        parent = user32.GetParent(hwnd)
        if parent:
            hwnd = int(parent)
    except Exception:
        return False
    if not hwnd:
        return False

    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32
    WM_SETICON = 0x0080
    ICON_SMALL = 0
    ICON_BIG = 1
    # 64-bit: SetClassLongPtr; fall back to SetClassLong
    GCL_HICON = -14
    GCL_HICONSM = -34

    path = str(ico.resolve())
    h_big = wintypes.HICON()
    h_small = wintypes.HICON()
    # Extract first group from ICO (large + small)
    n = shell32.ExtractIconExW(path, 0, ctypes.byref(h_big), ctypes.byref(h_small), 1)
    if n == 0 or (not h_big.value and not h_small.value):
        # Fallback: LoadImage by size
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        h_small_v = user32.LoadImageW(None, path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        h_big_v = user32.LoadImageW(None, path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
        h_small = wintypes.HICON(h_small_v or 0)
        h_big = wintypes.HICON(h_big_v or h_small_v or 0)
    if not h_small.value and h_big.value:
        h_small = h_big
    if not h_big.value and h_small.value:
        h_big = h_small
    if not h_small.value and not h_big.value:
        return False

    hwnd_w = wintypes.HWND(hwnd)
    ok = False
    if h_small.value:
        user32.SendMessageW(hwnd_w, WM_SETICON, ICON_SMALL, h_small)
        ok = True
    if h_big.value:
        user32.SendMessageW(hwnd_w, WM_SETICON, ICON_BIG, h_big)
        ok = True
    # Do not SetClassLongPtrW/GCL_HICON — that AVs on this host during
    # open (tray + icon reapply). WM_SETICON is enough for the taskbar.
    # Stash handles so they are not destroyed mid-session
    try:
        root._rpt_hicon_small = h_small  # type: ignore[attr-defined]
        root._rpt_hicon_big = h_big  # type: ignore[attr-defined]
        root._rpt_icon_hwnd = hwnd  # type: ignore[attr-defined]
    except Exception:
        pass
    return ok
