#!/usr/bin/env python3
"""Weekly **entry-only** wipe/rebuild service (exclusive lock; exit failover).

One-week timed path for entry-node snapshot/rebuild. Never wipes exit or both
nodes. Holds exclusive ``rpt-rebuild.lock`` so a second concurrent instance
fails closed.

Default is **dry-run**. Live destructive steps require
``RPT_EPHEMERAL_CONFIRM=yes`` (or ``--live`` with that env).

While entry is draining, clients auto residual-failover to exit; when entry is
healthy again they prefer re-entry (see ``client.multihop.select_residual_endpoint``).

Examples:
  python scripts/weekly_entry_rebuild.py --dry-run
  python scripts/weekly_entry_rebuild.py --dry-run --period 7d
  RPT_EPHEMERAL_CONFIRM=yes python scripts/weekly_entry_rebuild.py --live

Honesty: does not erase provider backups/netflow; re-ship public pin if keys rotate.
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
    assert_weekly_entry_role_only,
    build_weekly_entry_rebuild_plan,
    live_confirm_env_name,
    parse_period_seconds,
    systemd_service_unit,
    systemd_timer_unit,
)
from node.rebuild_lock import (  # noqa: E402
    acquire_rebuild_lock,
    is_locked,
    read_lock,
    release_rebuild_lock,
    update_rebuild_lock_state,
)


def _run_step_command(cmd: str, *, dry_run: bool) -> int:
    text = (cmd or "").strip()
    if not text or text.startswith("#"):
        print(f"  (skip / comment) {text[:160]}")
        return 0
    if dry_run:
        print(f"  [dry-run would run] {text}")
        return 0
    print(f"  [live] {text}")
    r = subprocess.run(text, shell=True)  # noqa: S602
    return int(r.returncode)


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Weekly entry-only wipe/rebuild: exclusive lock, exit preflight, "
            "never two node instances at once"
        )
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
        "--period",
        default=os.environ.get("RPT_EPHEMERAL_PERIOD", "7d"),
        help="Periodic interval (default 7d / one week)",
    )
    p.add_argument(
        "--install-root",
        default=os.environ.get("INSTALL_ROOT", "/opt/restore-privacy"),
    )
    p.add_argument(
        "--role",
        default="entry",
        help="Must be entry (exit/both refused)",
    )
    p.add_argument(
        "--exit-unhealthy",
        action="store_true",
        help="Simulate exit unhealthy → plan aborts wipe (fail closed)",
    )
    p.add_argument(
        "--rotate-keys",
        action="store_true",
        help="Include optional key rotation step",
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
        "--check-lock",
        action="store_true",
        help="Print current exclusive lock state and exit",
    )
    args = p.parse_args(argv)

    if args.print_timer:
        print(systemd_timer_unit(period=args.period), end="")
        return 0
    if args.print_service:
        print(
            systemd_service_unit(
                dry_run=not args.live,
                install_root=args.install_root,
                weekly_entry=True,
            ),
            end="",
        )
        return 0
    if args.check_lock:
        cur = read_lock(args.install_root)
        if cur is None:
            print("lock=absent (no rebuild active)")
            return 0
        print(f"lock=held {cur.to_dict()}")
        return 0

    ok_role, role_msg = assert_weekly_entry_role_only(args.role)
    if not ok_role:
        print(role_msg, file=sys.stderr)
        return 3

    dry_run = True
    if args.live:
        dry_run = False
    elif args.dry_run is True:
        dry_run = True

    if not dry_run:
        ok, msg = assert_live_confirm()
        if not ok:
            print(msg, file=sys.stderr)
            return 2

    exit_healthy = not args.exit_unhealthy and _env_bool("RPT_EXIT_HEALTHY", True)

    plan = build_weekly_entry_rebuild_plan(
        period=args.period,
        install_root=args.install_root,
        dry_run=dry_run,
        rotate_keys=args.rotate_keys,
        role=args.role,
        exit_healthy=exit_healthy,
        provider_snapshot_cmd=os.environ.get("RPT_SNAPSHOT_CMD", ""),
        provider_rebuild_cmd=os.environ.get("RPT_REBUILD_CMD", ""),
    )

    print(plan.format_text())
    print(
        f"# period_seconds={plan.period_seconds} "
        f"(parse: {parse_period_seconds(args.period)}) "
        f"exit_healthy={exit_healthy} role=entry exclusive"
    )
    print("# NEVER two node wipe instances at once — exclusive lock enforced")
    print("# Clients: entry down → exit failover residual; entry up → re-entry preference")

    if dry_run:
        # Demonstrate exclusive lock acquire/refuse without keeping lock
        print("# --- exclusive lock dry-run probe ---")
        ok1, msg1, st1 = acquire_rebuild_lock(
            "entry", install_root=args.install_root, state="draining"
        )
        print(f"# acquire1: ok={ok1} {msg1}")
        ok2, msg2, _st2 = acquire_rebuild_lock(
            "entry", install_root=args.install_root, state="draining"
        )
        print(f"# acquire2 (must fail closed): ok={ok2} {msg2}")
        if st1 is not None:
            release_rebuild_lock(
                install_root=args.install_root, expected_pid=st1.pid
            )
            print("# released dry-run lock")
        # Refuse exit role
        ok_x, msg_x, _ = acquire_rebuild_lock("exit", install_root=args.install_root)
        print(f"# acquire exit (must refuse): ok={ok_x} {msg_x}")
        print("# DRY-RUN complete — no entry wipe executed.")
        print(
            f"# Live: {live_confirm_env_name()}=yes "
            f"python scripts/weekly_entry_rebuild.py --live"
        )
        if not exit_healthy:
            print("# note: plan aborted path (exit unhealthy) — correct fail-closed")
        return 0 if (ok1 and not ok2 and not ok_x) else 1

    # Live: exclusive lock for whole cycle
    if is_locked(args.install_root):
        cur = read_lock(args.install_root)
        print(
            f"refusing live: rebuild already active {cur.to_dict() if cur else ''}",
            file=sys.stderr,
        )
        return 4

    ok, msg, lock_st = acquire_rebuild_lock(
        "entry", install_root=args.install_root, state="draining"
    )
    if not ok:
        print(msg, file=sys.stderr)
        return 4
    print(f"==> exclusive_lock: {msg}")

    if not exit_healthy:
        print("abort: exit unhealthy — fail closed, no entry wipe", file=sys.stderr)
        release_rebuild_lock(
            install_root=args.install_root,
            expected_pid=lock_st.pid if lock_st else None,
        )
        return 5

    failures = 0
    try:
        for step in plan.steps:
            # Lock steps already applied at start / handled specially
            if step.id in (
                "exclusive_lock_acquire",
                "exclusive_lock_release",
                "role_guard",
            ):
                print(f"==> {step.id}: {step.action} (handled by service)")
                continue
            if step.id == "mark_entry_draining":
                update_rebuild_lock_state("draining", install_root=args.install_root)
                print(f"==> {step.id}: draining (clients → exit failover)")
                continue
            if step.id == "mark_rebuilding":
                update_rebuild_lock_state("rebuilding", install_root=args.install_root)
                print(f"==> {step.id}: rebuilding")
                continue
            if step.id == "abort_exit_unhealthy":
                print(f"==> {step.id}: {step.action}")
                failures += 1
                break
            print(f"==> {step.id}: {step.action}")
            rc = _run_step_command(step.command, dry_run=False)
            if rc != 0:
                print(f"step {step.id} failed rc={rc}", file=sys.stderr)
                failures += 1
                if step.destructive:
                    print("stopping after destructive step failure", file=sys.stderr)
                    break
    finally:
        release_rebuild_lock(
            install_root=args.install_root,
            expected_pid=lock_st.pid if lock_st else None,
        )
        print("==> exclusive_lock_release: done (entry ready for re-entry preference)")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
