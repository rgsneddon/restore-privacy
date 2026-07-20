#!/usr/bin/env python3
"""Operator entry: rotate node long-term ElGamal keys + product public pin.

Usage:
  python scripts/rotate_node_keys.py --secrets-dir /opt/restore-privacy/secrets
  RPT_KEY_BACKEND=sealed python scripts/rotate_node_keys.py

Clients re-provision node_elgamal.pub only (never a shared client private key).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from node.key_rotation import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
