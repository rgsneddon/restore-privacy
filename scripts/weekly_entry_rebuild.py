#!/usr/bin/env python3
"""Weekly **sequential fleet** wipe/rebuild (IS → RO → new peers; exclusive lock).

One-week timed path for residual peer snapshot/rebuild. Wipes **every** catalog
peer over time, but **never concurrently**: Iceland first; only after IS is
fully rebuilt does Romania become next; new countries append recursively.

Holds exclusive ``rpt-rebuild.lock`` for the current target country role so a
second concurrent instance fails closed.

Default is **dry-run**. Live destructive steps require
``RPT_EPHEMERAL_CONFIRM=yes`` (or ``--live`` with that env).

While a peer is draining, clients auto residual-failover to a healthy catalog
peer; when the preferred entry is healthy again they re-prefer it
(see ``client.multihop.select_residual_endpoint`` / ``alternate_peer_endpoint``).

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
    assert_role_reinstall_lists_differ,
    assert_weekly_entry_role_only,
    build_weekly_entry_rebuild_plan,
    entry_reinstall_requirements,
    live_confirm_env_name,
    parse_period_seconds,
    plan_embeds_mandatory_reinstall,
    systemd_service_unit,
    systemd_timer_unit,
)
from node.fleet_wipe import (  # noqa: E402
    load_fleet_wipe_state,
    resolve_weekly_target,
    role_for_country_code,
)
from node.rebuild_lock import (  # noqa: E402
    acquire_rebuild_lock,
    read_lock,
    release_rebuild_lock,
)
from node.wipe_preflight import (  # noqa: E402
    plan_has_required_live_steps,
    run_live_prewipe_gates,
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
            "Weekly sequential fleet wipe/rebuild: IS then RO then new peers; "
            "exclusive lock; peer preflight; never concurrent multi-node wipe"
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
        default="auto",
        help="auto|entry|is|ro — auto picks next_wipe_target (IS then RO then new)",
    )
    p.add_argument(
        "--exit-unhealthy",
        action="store_true",
        help="Simulate peer residual unhealthy → plan aborts wipe (fail closed)",
    )
    p.add_argument(
        "--entry-unhealthy",
        action="store_true",
        help="Simulate local pre-wipe health fail → plan aborts (fail closed)",
    )
    p.add_argument(
        "--skip-live-probes",
        action="store_true",
        help="(tests only) skip real UDP/ss probes; use --exit/--entry-unhealthy flags",
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

    # Refuse bulk roles (exit|both|all) on raw CLI arg before country mapping
    ok_role, role_msg = assert_weekly_entry_role_only(args.role)
    if not ok_role:
        print(role_msg, file=sys.stderr)
        return 3

    # Fleet state: completed peers this cycle
    state = load_fleet_wipe_state(args.install_root)
    completed = list(state.get("completed") or [])
    in_progress = state.get("in_progress")

    decision = resolve_weekly_target(
        completed=completed,
        in_progress=in_progress,
        role_hint=args.role,
    )
    if not decision.allow or not decision.target_code:
        print(f"fleet_refuse: {decision.reason}", file=sys.stderr)
        print(
            f"# fleet completed={completed} in_progress={in_progress} "
            f"order=IS→RO→new"
        )
        return 3

    # Auto cycle roll: persist cleared completed when resolver rolled
    if (
        str(args.role).strip().lower() in ("", "auto", "next", "fleet")
        and decision.completed == ()
        and completed
        and decision.target_code == "IS"
        and "rolled" in (decision.reason or "").lower()
    ):
        from node.fleet_wipe import save_fleet_wipe_state

        save_fleet_wipe_state(
            completed=[],
            in_progress=None,
            install_root=args.install_root,
            cycle_id=str(state.get("cycle_id") or "") + "+1",
        )
        completed = []

    target = decision.target_code
    lock_role = role_for_country_code(target)

    # Default health flags; live path overrides with real probes unless skipped
    peer_healthy = not args.exit_unhealthy and _env_bool("RPT_EXIT_HEALTHY", True)
    local_healthy = not args.entry_unhealthy and _env_bool("RPT_ENTRY_HEALTHY", True)

    if not dry_run and not args.skip_live_probes:
        gate = run_live_prewipe_gates(target_code=target)
        peer_healthy = bool(gate.exit_probe.ok) and gate.allow_wipe
        local_healthy = bool(gate.entry_probe.ok)
        print(f"# live_prewipe target={target} allow={gate.allow_wipe} {gate.reasons[:3]}")

    plan = build_weekly_entry_rebuild_plan(
        period=args.period,
        install_root=args.install_root,
        dry_run=dry_run,
        rotate_keys=args.rotate_keys,
        role=args.role,
        exit_healthy=peer_healthy,
        entry_healthy=local_healthy,
        completed=completed,
        in_progress=in_progress,
        provider_snapshot_cmd=os.environ.get("RPT_SNAPSHOT_CMD", ""),
        provider_rebuild_cmd=os.environ.get("RPT_REBUILD_CMD", ""),
    )

    print(plan.format_text())
    print(
        f"# period_seconds={plan.period_seconds} "
        f"(parse: {parse_period_seconds(args.period)}) "
        f"target={target} lock_role={lock_role} "
        f"peer_healthy={peer_healthy} local_healthy={local_healthy} "
        f"completed={completed}"
    )
    print("# NEVER two node wipe instances at once — exclusive lock + sequential fleet")
    print(
        "# Clients: preferred entry draining → alternate catalog peer failover "
        "(RO entry fails over to IS, not RO again)"
    )
    print(
        "# Continuity honesty: automatic residual failover — not zero packet-loss guarantee"
    )
    print("# Mandatory after wipe: full selfhost reinstall (install.sh + DNS + host privacy)")
    print("# Fleet path: IS complete → RO next → new countries recursive")
    ok_diff, diff_msg = assert_role_reinstall_lists_differ()
    print(f"# role_reinstall_entry_vs_exit: ok={ok_diff} {diff_msg}")
    print(
        "# entry_reinstall_ids="
        + ",".join(r.id for r in entry_reinstall_requirements())
    )
    embeds = plan_embeds_mandatory_reinstall([s.id for s in plan.steps])
    print(f"# plan_embeds_mandatory_reinstall={embeds}")

    if dry_run:
        print("# --- exclusive lock dry-run probe ---")
        ok1, msg1, st1 = acquire_rebuild_lock(
            lock_role, install_root=args.install_root, state="draining"
        )
        print(f"# acquire1 role={lock_role}: ok={ok1} {msg1}")
        ok2, msg2, _st2 = acquire_rebuild_lock(
            "ro" if lock_role != "ro" else "is",
            install_root=args.install_root,
            state="draining",
        )
        print(f"# acquire2 concurrent peer (must fail closed): ok={ok2} {msg2}")
        if st1 is not None:
            release_rebuild_lock(
                install_root=args.install_root, expected_pid=st1.pid
            )
            print("# released dry-run lock")
        ok_x, msg_x, _ = acquire_rebuild_lock("exit", install_root=args.install_root)
        print(f"# acquire exit bulk (must refuse): ok={ok_x} {msg_x}")
        if peer_healthy and local_healthy:
            ok_steps, missing = plan_has_required_live_steps(
                [s.id for s in plan.steps]
            )
            print(
                f"# structural_live_steps: ok={ok_steps} missing={missing}"
            )
        return 0

    # Live: execute plan steps in order. Fail closed on lock / drain / preflight
    # (not only on [DESTRUCTIVE] steps) so a missed exclusive lock cannot race a
    # second concurrent wipe start.
    _fail_closed_ids = frozenset(
        {
            "exclusive_lock_acquire",
            "peer_failover_preflight",
            "entry_node_preflight",
            "mark_entry_draining",
            "mark_rebuilding",
            "mark_fleet_peer_complete",
            "exclusive_lock_release",
        }
    )
    for step in plan.steps:
        rc = _run_step_command(step.command, dry_run=False)
        if rc != 0 and (step.destructive or step.id in _fail_closed_ids):
            print(f"step {step.id} failed rc={rc}", file=sys.stderr)
            release_rebuild_lock(install_root=args.install_root)
            return rc or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
