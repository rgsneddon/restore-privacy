"""python -m client.windows — launch Windows GUI client.

On Windows with console ``python.exe``, re-exec via ``pythonw`` so a bare CLI
window is not left open behind the GUI (see launch_gui.py). Elevation also
prefers the windowed host.
"""

from __future__ import annotations

import sys


def _should_reexec_windowed() -> bool:
    if sys.platform != "win32":
        return False
    # Frozen products are already windowed when built with --windowed
    if getattr(sys, "frozen", False):
        return False
    try:
        from client.windows.launch_gui import should_reexec_to_windowed_host

        return should_reexec_to_windowed_host()
    except Exception:
        name = __import__("pathlib").Path(sys.executable).name.lower()
        if name == "pythonw.exe":
            return False
        try:
            import ctypes

            return bool(ctypes.windll.kernel32.GetConsoleWindow())
        except Exception:
            return name in ("python.exe", "python")


if _should_reexec_windowed():
    from client.windows.launch_gui import main as launch_main

    raise SystemExit(launch_main())

# Windowed host (or no pythonw): free console if still attached, then GUI
try:
    from client.windows.launch_gui import free_console_if_attached

    free_console_if_attached()
except Exception:
    pass

from client.windows.app import main

raise SystemExit(main())
