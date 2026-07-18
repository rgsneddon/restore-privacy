"""python -m client.windows — launch Windows GUI client.

On Windows with a console-attached ``python.exe``, re-exec via ``pythonw`` so a
bare CLI window is not left open behind the GUI (see launch_gui.py).
"""

from __future__ import annotations

import sys


def _should_reexec_windowed() -> bool:
    if sys.platform != "win32":
        return False
    # Frozen products are already windowed when built with --windowed
    if getattr(sys, "frozen", False):
        return False
    name = __import__("pathlib").Path(sys.executable).name.lower()
    if name == "pythonw.exe":
        return False
    # Only re-exec when a real console is attached (user double-click / Start-Process)
    try:
        import ctypes

        return bool(ctypes.windll.kernel32.GetConsoleWindow())
    except Exception:
        return True


if _should_reexec_windowed():
    from client.windows.launch_gui import main as launch_main

    raise SystemExit(launch_main())

from client.windows.app import main

raise SystemExit(main())
