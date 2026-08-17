#!/usr/bin/env python3
"""Refresh GOD installer inventory (compat wrapper).

Prefer ``scripts/refresh_god_release_links.py``. This name stays so older
handoff notes still work. Helsinki now runs the full refresh on a timer.
"""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).with_name("refresh_god_release_links.py")),
        run_name="__main__",
    )
