"""Windows system tray for Privacy Restored (product tray identity).

Uses Shell_NotifyIcon via ctypes — no extra pip deps (safe for frozen onedir).
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Callable, Optional

# Product tray identity (distinct from window title "Restore Privacy")
TRAY_DISPLAY_NAME = "Privacy Restored"


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
        self._tooltip = tray_tooltip_for_state(connected=False)

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
            from ctypes import wintypes

            if self._hwnd:
                ctypes.windll.user32.PostMessageW(self._hwnd, 0x0010, 0, 0)  # WM_CLOSE
        except Exception:
            pass

    def update_status(self, *, connected: bool, residual: bool = True) -> None:
        self._tooltip = tray_tooltip_for_state(connected=connected, residual=residual)
        if not self._running or self._nid is None or self._hwnd is None:
            return
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

            NIF_TIP = 0x00000004
            NIM_MODIFY = 0x00000001
            nid = NOTIFYICONDATAW()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
            nid.hWnd = self._hwnd
            nid.uID = 1
            nid.uFlags = NIF_TIP
            tip = self._tooltip[:127]
            nid.szTip = tip
            ctypes.windll.shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
        except Exception:
            pass

    def _load_icon(self):
        import ctypes
        from ctypes import wintypes

        path = resolve_tray_icon_path()
        if path is None:
            # Stock application icon
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
        # Fallback stock icon
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

        # 64-bit Windows: LRESULT / WPARAM / LPARAM are pointer-sized
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
        # Unregister stale class from prior test runs
        try:
            user32.UnregisterClassW(class_name, hinst)
        except Exception:
            pass
        atom = user32.RegisterClassW(ctypes.byref(wc))
        if not atom and ctypes.get_last_error() not in (0, 1410):  # already exists
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
        self._hicon = self._load_icon()

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

        msg = wintypes.MSG()
        while self._running and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        self._running = False
