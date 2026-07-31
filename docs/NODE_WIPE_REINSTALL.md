# Node wipe / rebuild reinstall (sequential fleet)

## Sequential fleet wipe (~7d) — **one peer at a time**

Planner: `node/fleet_wipe.py` (`PREFERRED_FLEET_ORDER = IS → DE`).  
Orchestrator entrypoint: `scripts/weekly_entry_rebuild.py` (still hosts the timer; fleet order is multi-peer).

| Rule | Detail |
|------|--------|
| Order | **IS first**, then **DE**, then **US** (and any later catalog peers) — finish prior peer before starting next |
| Concurrency | Exclusive lock — **never** concurrent multi-node wipe |
| Continuity | **Best-effort** hop to a healthy alternate while a peer drains (not zero packet-loss; hop is not guaranteed) |
| Failsafe | If hop does not succeed, the client may disconnect or restart and will require **manual reconnection** whilst privacy-preserving weekly node wipedown occurs |
| After wipe | **Mandatory full selfhost reinstall** on the wiped peer |
| Live | Requires `RPT_EPHEMERAL_CONFIRM=yes`; dry-run is the safe default |

Results snapshot: [FLEET_WIPE_RESULTS_2026-07-25.md](FLEET_WIPE_RESULTS_2026-07-25.md).

---

## Legacy note: weekly entry-only planner helpers

Older helpers still describe **entry-only** weekly wipe (exit stays up for failover). Current product fleet wipe is sequential across catalog peers as above.

## Weekly timed wipe (~7d) — **entry only**

Script: `scripts/weekly_entry_rebuild.py`  
Planner: `node.ephemeral_node.build_weekly_entry_rebuild_plan`

| Rule | Detail |
|------|--------|
| Role | **entry** only — `assert_weekly_entry_role_only` **refuses** `exit` / `both` / `all` |
| Lock | Exclusive `rpt-rebuild.lock` (never two concurrent wipes) |
| Pre-wipe | Fail closed if **exit residual** or **entry** health fails |
| After wipe | **Mandatory full selfhost reinstall** (`SKIP_DNS=0 SKIP_HOST_PRIVACY=0 bash scripts/selfhost_node.sh`) |
| Post | `health_check` then release lock; clients prefer re-entry when entry healthy |

Full reinstall is **not** stop-only or runtime scrub alone. After rebuild the plan always includes `selfhost_reapply` (install.sh + tunnel DNS + host privacy + no-log). Live wipe is refused if `plan_has_required_live_steps` misses that step.

Dry-run (safe):

```bash
python scripts/weekly_entry_rebuild.py --dry-run --period 7d
```

Live (destructive; needs confirm):

```bash
RPT_EPHEMERAL_CONFIRM=yes python scripts/weekly_entry_rebuild.py --live
```

## Entry reinstall requirements

Pure helper: `entry_reinstall_requirements()`

Shared with exit: core install, tunnel DNS, host privacy, full selfhost, UDP/status health.

**Entry-unique:** product entry pin, weekly failover preflights, exclusive entry lock, client re-entry preference.

## Exit reinstall (manual — **not** weekly timer)

Pure helper: `exit_reinstall_requirements()` + `build_exit_manual_reinstall_plan()`

Exit stays up so clients can residual-failover while entry drains. Do **not** enable the weekly entry wipe timer on the exit host.

**Exit-unique:** distinct exit ElGamal keys (`product/exit_node_elgamal.pub`), UDP 44044 firewall/panel, hop host monopin (Romania ≠ Iceland), no weekly timer.

See also `scripts/MULTIHOP_EXIT_HOP_PREP.md`.

## Honesty

- Provider off-box backups/netflow are **not** erased by product wipe.
- Continuity during weekly fleet wipe is **best-effort residual hop** to a healthy catalog peer (not zero packet-loss; not a guaranteed seamless hop).
- **Failsafe:** if hop does not succeed, the client may disconnect or restart and will require **manual reconnection** whilst privacy-preserving weekly node wipedown occurs. Press Connect again when a peer is residual-ready (full hop redesign is deferred).

## After reinstall: private capacity token

Selfhost / wipe reinstall does **not** publish live client counts. If you use
**near-capacity residual migration**, re-apply the private capacity token on
each residual node after rebuild:

```bash
sudo bash scripts/install_capacity_token_env.sh
# or: sudo env RPT_CAPACITY_TOKEN='…' bash scripts/install_capacity_token_env.sh
```

Operator clients that probe need the same `RPT_CAPACITY_TOKEN`. Full operator
guide: [CAPACITY_PROBES.md](CAPACITY_PROBES.md). Template: `scripts/hop_env.example`.
**Romania (RO) Mac SSH finalize** (unlimited-class bandwidth / extendable at cost + shared token):
[RO_CAPACITY_MAC_FINALIZE.md](RO_CAPACITY_MAC_FINALIZE.md).


## Homepage display (0.3.7+)

Public homepage shows **entry-only** clear timer. Exit wipe countdown was removed; exit is never weekly-wiped.
