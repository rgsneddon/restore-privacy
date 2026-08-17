"""GNFP tip helpers for the GOD dashboard."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

GNFP_TICKER = "GNFP"
_EXPLORER_STATS = "https://explorer.restoreprivacy.online/api/stats"
_CACHED_TIP: int | None = None


def gnfp_tip_height() -> int:
    global _CACHED_TIP
    if _CACHED_TIP is not None:
        return _CACHED_TIP
    try:
        req = urllib.request.Request(
            _EXPLORER_STATS,
            headers={"User-Agent": "god-rpai/hub", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=2) as res:
            data = json.loads(res.read().decode("utf-8", errors="replace") or "{}")
        if isinstance(data, dict):
            for key in ("height", "tipHeight", "tip"):
                if data.get(key) is not None:
                    _CACHED_TIP = max(0, int(data[key]))
                    return _CACHED_TIP
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError, TypeError):
        _CACHED_TIP = 0
        return 0
    _CACHED_TIP = 0
    return 0
