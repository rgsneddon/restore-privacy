# Node Operator (Mac / desktop)

Operator GUI for running **this host as a residual VPN node lab**, with admin
controls. **Not** the end-user Connect client and **not** the public status shop.

## Launch

```bash
# From monorepo root
python3 -m node_operator
# HTTP GUI on http://127.0.0.1:18765/ (opens browser when available)
# Tk window if _tkinter is installed (--gui tk)

python3 -m node_operator --smoke   # no GUI serve; controller smoke only
python3 -m node_operator --no-browser --port 18765
```

## Modes

| Mode | Behaviour |
|------|-----------|
| **lab** | In-memory sessions + priority admin. **Honest on macOS** (no Linux TUN). |
| **full** | Spawns `python -m node` (needs Linux `/dev/net/tun`). May error on Mac. |

## Admin features

- **Start / stop** residual node stack (lab or full)
- **Connected clients** table (admin only; public `/status` stays title-only)
- **Prioritise clients** — higher integer preferred under contention (IP pool reclaim)
- **Upload packages to host** — manual **stage + upload** of catalog installers to the
  Helsinki paid store (`scripts/host_paid_assets_vps.py`), with dry-run / force /
  allow-missing / install-serve options. Primary path after you build monopin packages.
- **Client updates** — residual push-to-clients is **disabled**; users update manually
  from free Suite download (discrete in-app “new version available” notice only).

### Upload packages (GUI)

1. Build or place installers under `releases/{version}/` (or stage tree).
2. Open the operator GUI → **Upload packages to host**.
3. Set monopin version (default catalog pin), choose Stage and/or Upload.
4. Prefer **Allow missing** for partial ships; use **Dry-run** to print the plan.
5. **Upload packages to Helsinki** runs the shipped host script (SSH key required for real upload).

## Related code

- `node/client_priority.py` — priority store + honour order
- `node/update_push.py` — UPDATE_PUSH enqueue fail-closed (manual update only)
- `node/operator_admin.py` — controller the GUI drives
