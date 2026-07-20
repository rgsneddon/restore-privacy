#!/usr/bin/env python3
"""Ephemeral / short-lived RPT node: periodic snapshot and/or rebuild automation.

Default is **dry-run** (prints ordered plan only). Live destructive actions
require ``RPT_EPHEMERAL_CONFIRM=yes`` (or ``--live`` with that env set).

Examples:
  python scripts/ephemeral_node.py --dry-run
  python scripts/ephemeral_node.py --dry-run --mode snapshot --period 7d
  RPT_EPHEMERAL_CONFIRM=yes python scripts/ephemeral_node.py --live --mode rebuild

Optional hooks (shell command strings):
  RPT_SNAPSHOT_CMD   provider snapshot API/CLI
  RPT_REBUILD_CMD    provider reimage/rebuild API/CLI
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from node.ephemeral_node import (  # noqa: E402
    assert_live_confirm,
    build_ephemeral_plan,
    cron_line,
    live_confirm_env_name,
    parse_period_seconds,
    systemd_service_unit,
    systemd_timer_unit,
)


def _run_step_command(cmd: str, *, dry_run: bool) -> int:
    text = (cmd or "").strip()
    if not text or text.startswith("#"):
        print(f"  (skip / comment) {text[:120]}")
        return 0
    if dry_run:
        print(f"  [dry-run would run] {text}")
        return 0
    print(f"  [live] {text}")
    # Shell for operator-provided hooks; selfhost path is intentional
    r = subprocess.run(text, shell=True)  # noqa: S602
    return int(r.returncode)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Ephemeral short-lived RPT node: snapshot / periodic rebuild"
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="Print plan only (default if --live not set)",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help=f"Execute steps (requires {live_confirm_env_name()}=yes)",
    )
    p.add_argument(
        "--mode",
        default="snapshot_then_rebuild",
        choices=("snapshot", "rebuild", "snapshot_then_rebuild"),
        help="snapshot | rebuild | snapshot_then_rebuild",
    )
    p.add_argument(
        "--period",
        default=os.environ.get("RPT_EPHEMERAL_PERIOD", "7d"),
        help="Periodic interval (e.g. 7d, 24h) for schedule hints",
    )
    p.add_argument(
        "--install-root",
        default=os.environ.get("INSTALL_ROOT", "/opt/restore-privacy"),
    )
    p.add_argument(
        "--rotate-keys",
        action="store_true",
        help="Include optional key rotation step in the plan",
    )
    p.add_argument(
        "--print-timer",
        action="store_true",
        help="Print systemd timer unit and exit",
    )
    p.add_argument(
        "--print-service",
        action="store_true",
        help="Print systemd oneshot service unit and exit",
    )
    p.add_argument(
        "--print-cron",
        action="store_true",
        help="Print cron line for periodic schedule and exit",
    )
    args = p.parse_args(argv)

    if args.print_timer:
        print(systemd_timer_unit(period=args.period), end="")
        return 0
    if args.print_service:
        print(
            systemd_service_unit(
                dry_run=not args.live, install_root=args.install_root
            ),
            end="",
        )
        return 0
    if args.print_cron:
        print(cron_line(period=args.period, dry_run=not args.live))
        return 0

    dry_run = True
    if args.live:
        dry_run = False
    elif args.dry_run is True:
        dry_run = True
    else:
        # Default dry-run for safety
        dry_run = True

    if not dry_run:
        ok, msg = assert_live_confirm()
        if not ok:
            print(msg, file=sys.stderr)
            return 2

    plan = build_ephemeral_plan(
        mode=args.mode,
        period=args.period,
        install_root=args.install_root,
        dry_run=dry_run,
        rotate_keys=args.rotate_keys,
        provider_snapshot_cmd=os.environ.get("RPT_SNAPSHOT_CMD", ""),
        provider_rebuild_cmd=os.environ.get("RPT_REBUILD_CMD", ""),
    )

    print(plan.format_text())
    print(
        f"# period_seconds={plan.period_seconds} "
        f"(parse check: {parse_period_seconds(args.period)})"
    )

    if dry_run:
        print("# DRY-RUN complete — no snapshot/rebuild executed.")
        print(f"# Live: {live_confirm_env_name()}=yes python scripts/ephemeral_node.py --live")
        return 0

    # Live: run commands that are not comments
    failures = 0
    for step in plan.steps:
        print(f"==> {step.id}: {step.action}")
        rc = _run_step_command(step.command, dry_run=False)
        if rc != 0:
            print(f"step {step.id} failed rc={rc}", file=sys.stderr)
            failures += 1
            if step.destructive:
                print("stopping after destructive step failure", file=sys.stderr)
                break
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
