"""Windows system tray for Privacy Restored (product tray identity).

Uses Shell_NotifyIcon via ctypes — no extra pip deps (safe for frozen onedir).
Connected vs disconnected use distinct tooltip **and** tray icon (green vs grey badge).
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Callable, Optional

# Product tray identity (distinct from window title "Restore Privacy")
TRAY_DISPLAY_NAME = "Privacy Restored"

# Private message to apply status updates on the tray thread
_WM_RPT_TRAY_STATUS = 0x0400 + 99  # WM_USER + 99


def resolve_tray_icon_path() -> Optional[Path]:
    """Logo ICO/PNG for tray and shortcuts (shipped brand assets)."""
    here = Path(__file__).resolve().parent
    root = here.parents[1]
    candidates = [
        here / "native" / "app_icon.ico",
        here / "native" / "app_icon.png",
        root / "assets" / "brand" / "favicon.ico",
        root / "assets" / "brand" / "logo-256.png",
        root / "assets" / "brand" / "favicon-32.png",
    ]
    # Frozen: next to executable / _MEIPASS
    if getattr(sys, "frozen", False):
        try:
            exe_dir = Path(sys.executable).resolve().parent
            candidates = [
                exe_dir / "app_icon.ico",
                exe_dir / "client" / "windows" / "native" / "app_icon.ico",
                exe_dir / "_internal" / "client" / "windows" / "native" / "app_icon.ico",
                *candidates,
            ]
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                base = Path(meipass)
                candidates = [
                    base / "client" / "windows" / "native" / "app_icon.ico",
                    base / "app_icon.ico",
                    *candidates,
                ]
        except Exception:
            pass
    for p in candidates:
        if p.is_file():
            return p
    return None


def tray_tooltip_for_state(*, connected: bool, residual: bool = True) -> str:
    """Short tray hover text using product tray name."""
    if connected and residual:
        return f"{TRAY_DISPLAY_NAME} — connected (VPN active)"
    if connected:
        return f"{TRAY_DISPLAY_NAME} — session only"
    return f"{TRAY_DISPLAY_NAME} — disconnected"


def tray_icon_state_key(*, connected: bool, residual: bool = True) -> str:
    """Discrete tray visual state for tests / icon selection."""
    if connected and residual:
        return "connected"
    if connected:
        return "session_only"
    return "disconnected"


def make_status_icon_handle(*, connected: bool, residual: bool = True, size: int = 16):
    """Create a small coloured tray HICON (green = connected, grey = disconnected).

    Pure Win32 GDI — no Pillow. Returns HICON or 0 on failure.
    """
    if sys.platform != "win32":
        return 0
    try:
        import ctypes
        from ctypes import wintypes

        # Colours BGRA for 32-bit DIB (Windows bottom-up)
        if connected and residual:
            r, g, b = 27, 118, 126  # STATUS_OK teal
        elif connected:
            r, g, b = 39, 121, 170  # primary blue
        else:
            r, g, b = 136, 136, 136  # grey disconnected

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [
                ("bmiHeader", BITMAPINFOHEADER),
                ("bmiColors", wintypes.DWORD * 3),
            ]

        class ICONINFO(ctypes.Structure):
            _fields_ = [
                ("fIcon", wintypes.BOOL),
                ("xHotspot", wintypes.DWORD),
                ("yHotspot", wintypes.DWORD),
                ("hbmMask", wintypes.HBITMAP),
                ("hbmColor", wintypes.HBITMAP),
            ]

        bi = BITMAPINFO()
        bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.bmiHeader.biWidth = size
        bi.bmiHeader.biHeight = size  # bottom-up
        bi.bmiHeader.biPlanes = 1
        bi.bmiHeader.biBitCount = 32
        bi.bmiHeader.biCompression = 0  # BI_RGB

        bits = ctypes.c_void_p()
        hdc = user32.GetDC(None)
        hbm_color = gdi32.CreateDIBSection(
            hdc, ctypes.byref(bi), 0, ctypes.byref(bits), None, 0
        )
        user32.ReleaseDC(None, hdc)
        if not hbm_color or not bits:
            return 0

        # Fill solid colour (BGRA, alpha 255)
        px = (ctypes.c_ubyte * (size * size * 4)).from_address(bits.value)
        for i in range(size * size):
            o = i * 4
            px[o] = b
            px[o + 1] = g
            px[o + 2] = r
            px[o + 3] = 255

        # 1-bit mask (all opaque → zeros)
        hbm_mask = gdi32.CreateBitmap(size, size, 1, 1, None)
        if not hbm_mask:
            gdi32.DeleteObject(hbm_color)
            return 0

        ii = ICONINFO()
        ii.fIcon = True
        ii.xHotspot = 0
        ii.yHotspot = 0
        ii.hbmMask = hbm_mask
        ii.hbmColor = hbm_color
        hicon = user32.CreateIconIndirect(ctypes.byref(ii))
        gdi32.DeleteObject(hbm_mask)
        gdi32.DeleteObject(hbm_color)
        return int(hicon) if hicon else 0
    except Exception:
        return 0


class WindowsSystemTray:
    """Notify-icon tray: Show window / Connect / Disconnect / Quit.

    Safe no-op when not on Windows or when tray creation fails.
    """

    def __init__(
        self,
        *,
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
    ) -> None:
        self._on_show = on_show
        self._on_quit = on_quit
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._thread: Optional[threading.Thread] = None
        self._hwnd = None
        self._nid = None
        self._running = False
        self._hicon = None
        self._hicon_connected = None
        self._hicon_disconnected = None
        self._connected = False
        self._residual = True
        self._tooltip = tray_tooltip_for_state(connected=False)
        self._lock = threading.Lock()
        self._pending: Optional[tuple[bool, bool]] = None

    def start(self) -> bool:
        if sys.platform != "win32":
            return False
        if self._running:
            return True
        self._running = True
        self._thread = threading.Thread(target=self._run, name="rpt-tray", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        if sys.platform != "win32":
            return
        try:
            import ctypes

            if self._hwnd:
                ctypes.windll.user32.PostMessageW(self._hwnd, 0x0010, 0, 0)  # WM_CLOSE
        except Exception:
            pass

    def update_status(self, *, connected: bool, residual: bool = True) -> None:
        """Update tray tip + icon for connected/disconnected (thread-safe)."""
        with self._lock:
            self._connected = bool(connected)
            self._residual = bool(residual)
            self._tooltip = tray_tooltip_for_state(
                connected=self._connected, residual=self._residual
            )
            self._pending = (self._connected, self._residual)

        if not self._running:
            return
        # Prefer posting to tray thread so Shell_NotifyIcon runs there
        try:
            import ctypes

            if self._hwnd:
                ctypes.windll.user32.PostMessageW(
                    self._hwnd, _WM_RPT_TRAY_STATUS, 0, 0
                )
                return
        except Exception:
            pass
        # Fallback: apply directly (may race until hwnd ready)
        self._apply_notify_modify()

    def _icon_for_state(self, *, connected: bool, residual: bool = True):
        if connected:
            if self._hicon_connected:
                return self._hicon_connected
        else:
            if self._hicon_disconnected:
                return self._hicon_disconnected
        return self._hicon

    def _apply_notify_modify(self) -> None:
        if not self._running or self._hwnd is None:
            return
        with self._lock:
            connected = self._connected
            residual = self._residual
            tip = (self._tooltip or TRAY_DISPLAY_NAME)[:127]
            self._pending = None
        try:
            import ctypes
            from ctypes import wintypes

            class NOTIFYICONDATAW(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("hWnd", wintypes.HWND),
                    ("uID", wintypes.UINT),
                    ("uFlags", wintypes.UINT),
                    ("uCallbackMessage", wintypes.UINT),
                    ("hIcon", wintypes.HICON),
                    ("szTip", wintypes.WCHAR * 128),
                    ("dwState", wintypes.DWORD),
                    ("dwStateMask", wintypes.DWORD),
                    ("szInfo", wintypes.WCHAR * 256),
                    ("uVersion", wintypes.UINT),
                    ("szInfoTitle", wintypes.WCHAR * 64),
                    ("dwInfoFlags", wintypes.DWORD),
                    ("guidItem", ctypes.c_byte * 16),
                    ("hBalloonIcon", wintypes.HICON),
                ]

            NIF_ICON = 0x00000002
            NIF_TIP = 0x00000004
            NIM_MODIFY = 0x00000001
            hicon = self._icon_for_state(connected=connected, residual=residual)
            nid = NOTIFYICONDATAW()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
            nid.hWnd = self._hwnd
            nid.uID = 1
            nid.uFlags = NIF_TIP | (NIF_ICON if hicon else 0)
            nid.hIcon = hicon or 0
            nid.szTip = tip
            ctypes.windll.shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
            self._nid = nid
        except Exception:
            pass

    def _load_base_icon(self):
        import ctypes

        path = resolve_tray_icon_path()
        if path is None:
            return ctypes.windll.user32.LoadIconW(None, 32512)

        ico = str(path)
        if path.suffix.lower() == ".ico":
            h = ctypes.windll.user32.LoadImageW(
                None,
                ico,
                1,  # IMAGE_ICON
                0,
                0,
                0x00000010 | 0x00008000,  # LR_LOADFROMFILE | LR_DEFAULTSIZE
            )
            if h:
                return h
        return ctypes.windll.user32.LoadIconW(None, 32512)

    def _run(self) -> None:
        try:
            self._message_loop()
        except Exception:
            self._running = False

    def _message_loop(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32
        kernel32 = ctypes.windll.kernel32

        WM_USER = 0x0400
        WM_TRAY = WM_USER + 42
        WM_DESTROY = 0x0002
        WM_COMMAND = 0x0111
        WM_RBUTTONUP = 0x0205
        WM_LBUTTONDBLCLK = 0x0203
        WM_LBUTTONUP = 0x0202

        NIF_MESSAGE = 0x00000001
        NIF_ICON = 0x00000002
        NIF_TIP = 0x00000004
        NIM_ADD = 0x00000000
        NIM_DELETE = 0x00000002

        ID_SHOW = 1001
        ID_CONNECT = 1002
        ID_DISCONNECT = 1003
        ID_QUIT = 1004

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT),
                ("lpfnWndProc", ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT),
                ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128),
                ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256),
                ("uVersion", wintypes.UINT),
                ("szInfoTitle", wintypes.WCHAR * 64),
                ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", ctypes.c_byte * 16),
                ("hBalloonIcon", wintypes.HICON),
            ]

        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(
            LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        )
        user32.DefWindowProcW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.DefWindowProcW.restype = LRESULT

        self_ref = self

        def _popup(hwnd):
            menu = user32.CreatePopupMenu()
            user32.AppendMenuW(menu, 0, ID_SHOW, "Open Privacy Restored")
            user32.AppendMenuW(menu, 0, ID_CONNECT, "Connect")
            user32.AppendMenuW(menu, 0, ID_DISCONNECT, "Disconnect")
            user32.AppendMenuW(menu, 0x800, 0, None)  # MF_SEPARATOR
            user32.AppendMenuW(menu, 0, ID_QUIT, "Quit")
            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            user32.SetForegroundWindow(hwnd)
            user32.TrackPopupMenu(menu, 0, pt.x, pt.y, 0, hwnd, None)
            user32.DestroyMenu(menu)

        def wnd_proc(hwnd, msg, wparam, lparam):
            try:
                if msg == _WM_RPT_TRAY_STATUS:
                    self_ref._apply_notify_modify()
                    return 0
                if msg == WM_TRAY:
                    if int(lparam) & 0xFFFF == WM_RBUTTONUP or int(lparam) == WM_RBUTTONUP:
                        _popup(hwnd)
                    elif int(lparam) in (WM_LBUTTONDBLCLK, WM_LBUTTONUP):
                        try:
                            self_ref._on_show()
                        except Exception:
                            pass
                    return 0
                if msg == WM_COMMAND:
                    cmd = int(wparam) & 0xFFFF
                    try:
                        if cmd == ID_SHOW:
                            self_ref._on_show()
                        elif cmd == ID_CONNECT and self_ref._on_connect:
                            self_ref._on_connect()
                        elif cmd == ID_DISCONNECT and self_ref._on_disconnect:
                            self_ref._on_disconnect()
                        elif cmd == ID_QUIT:
                            self_ref._on_quit()
                    except Exception:
                        pass
                    return 0
                if msg == WM_DESTROY:
                    nid = NOTIFYICONDATAW()
                    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
                    nid.hWnd = hwnd
                    nid.uID = 1
                    shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
                    user32.PostQuitMessage(0)
                    return 0
                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
            except Exception:
                return 0

        self._wndproc = WNDPROC(wnd_proc)  # keep ref alive
        hinst = kernel32.GetModuleHandleW(None)
        class_name = "RptPrivacyRestoredTray"
        wc = WNDCLASSW()
        wc.lpfnWndProc = ctypes.cast(self._wndproc, ctypes.c_void_p)
        wc.hInstance = hinst
        wc.lpszClassName = class_name
        try:
            user32.UnregisterClassW(class_name, hinst)
        except Exception:
            pass
        atom = user32.RegisterClassW(ctypes.byref(wc))
        if not atom and ctypes.get_last_error() not in (0, 1410):
            pass

        hwnd = user32.CreateWindowExW(
            0,
            class_name,
            TRAY_DISPLAY_NAME,
            0,
            0,
            0,
            0,
            0,
            None,
            None,
            hinst,
            None,
        )
        if not hwnd:
            self._running = False
            return
        self._hwnd = hwnd

        # Distinct visual states (coloured badges) + brand logo fallback
        self._hicon_disconnected = make_status_icon_handle(
            connected=False, residual=True
        ) or self._load_base_icon()
        self._hicon_connected = make_status_icon_handle(
            connected=True, residual=True
        ) or self._hicon_disconnected
        self._hicon = self._hicon_disconnected

        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self._hicon
        tip = (self._tooltip or TRAY_DISPLAY_NAME)[:127]
        nid.szTip = tip
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        self._nid = nid

        # Apply any status that arrived before hwnd was ready
        with self._lock:
            pending = self._pending
        if pending is not None:
            self._apply_notify_modify()

        msg = wintypes.MSG()
        while self._running and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        self._running = False
