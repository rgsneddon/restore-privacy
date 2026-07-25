# Sequential fleet wipe + multihop results (2026-07-25)

## Multihop structure (2 nodes; expandable)

| User entry | Multihop exit | Residual exit host |
|---|---|---|
| Default IS | RO | 185.146.232.107 |
| RO | IS | 82.221.101.241 |

Rule: **entry = user-selected country**; **exit = random non-entry catalog peer** (with only two nodes, exit is the other country).

Verified on VPS: `mh IS -> RO ; RO -> IS`.

## Host-identity gate (skeptic fix)

- Orchestrator `local_country=IS` → IS local destructive OK; RO **REMOTE** fail-closed.
- RO plan uses `exit_product_pin_check` / `exit_node_elgamal.pub` (not entry pin).
- `mark_wipe_complete(RO)` requires `RPT_REMOTE_WIPE_OK` when not on RO host.
- Never runs local `systemctl stop` / selfhost on orchestrator for target=RO.

## Deploy

- Host: `82.221.101.241` (`restore-privacy-vps`)
- Modules: `node/fleet_wipe.py`, `node/ephemeral_node.py`, `scripts/weekly_entry_rebuild.py`, client multihop/endpoint
- Timer: `rpt-ephemeral-rebuild.timer` **enabled/active**
- Service Description: `RPT weekly sequential fleet wipe/rebuild (IS then RO then new; exclusive lock; peer failover)`
- Next timer: Sat 2026-08-01 ~15:15 UTC (dry-run oneshot)

## Wipe sequence exercised (software + timer dry-run)

| Step | Result |
|---|---|
| 1. IS plan (local) | `weekly_fleet_rebuild`; host gate local; entry pin; exclusive lock |
| 2. Mark IS complete | next = **RO** |
| 3. RO plan on IS orchestrator | stop/selfhost **REMOTE**; exit pin; mark needs `RPT_REMOTE_WIPE_OK` |
| 4. Mark RO complete | cycle roll → next = **IS** |
| 5. CLI dry-run IS then RO | rc=0 both |
| 6. `systemctl start` oneshot IS | status=0/SUCCESS, Description updated |
| 7. oneshot with completed=[IS] | target=RO, lock role=ro, REMOTE gates, exit pin, rc=0 |

Journal (RO oneshot excerpt):

```
target=RO lock_role=ro host=185.146.232.107
host_identity_gate: REMOTE target=RO
stop_runtime: Stop runtime on REMOTE target RO (not orchestrator)
selfhost_reapply: Package reinstall on REMOTE RO … Pin expected: exit_node_elgamal.pub
acquire1 role=ro: ok=True
Finished RPT weekly sequential fleet wipe/rebuild (IS then RO then new; …)
```

## Live provider reimage

**Not run.** Timer/service remain **dry-run**. Full disk reimage needs:

- `RPT_EPHEMERAL_CONFIRM=yes` (live service), and
- for RO: `RPT_REMOTE_WIPE_CMD` (SSH to 185.146.232.107) **or** run weekly rebuild on the RO host with `RPT_FLEET_LOCAL_COUNTRY=RO`.

## Unit tests (local)

`tests.test_weekly_entry_rebuild` + `test_fleet_wipe` + `test_entry_country_selection` — **39 tests OK**.
