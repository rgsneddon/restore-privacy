#!/usr/bin/env python3
"""Clear all admin Licence database rows (connect_entitlements + device bindings).

Operator / pre-BETA tool. Requires explicit confirm phrase.

Usage (from repo root, with payment DB on default path or RPT_PAYMENT_DATA_DIR)::

    set PYTHONPATH=status_page
    python scripts/clear_admin_licences.py --confirm CLEAR_ALL_LICENCES

Does not delete paid download grants. Does not touch Stripe Dashboard.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "status_page"
if str(STATUS) not in sys.path:
    sys.path.insert(0, str(STATUS))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    import payments

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--confirm",
        required=True,
        help=f"Must be exactly {payments.CLEAR_ALL_LICENCES_CONFIRM!r}",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print licence counts only; do not delete",
    )
    args = ap.parse_args(argv)

    payments.init_db()
    before = payments.list_licences_for_admin()
    path = payments.db_path()
    print(f"db_path={path}")
    print(f"licences_before={len(before)}")
    if args.dry_run:
        print(json.dumps({"dry_run": True, "licences": len(before)}, indent=2))
        return 0
    result = payments.clear_all_licences_for_admin(confirm=args.confirm)
    after = payments.list_licences_for_admin()
    print(json.dumps({**result, "licences_after": len(after)}, indent=2, default=str))
    if after:
        print("ERROR: licence table not empty after clear", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
