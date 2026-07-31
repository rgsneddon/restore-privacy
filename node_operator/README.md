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
| **lab** | In-memory sessions + priority / update-push admin. **Honest on macOS** (no Linux TUN). |
| **full** | Spawns `python -m node` (needs Linux `/dev/net/tun`). May error on Mac. |

## Admin features

- **Start / stop** residual node stack (lab or full)
- **Connected clients** table (admin only; public `/status` stays title-only)
- **Prioritise clients** — higher integer preferred under contention (IP pool reclaim)
- **Push update** — version/url/message directive to connected clients (`UPDATE_PUSH` wire type + client receive path)

## Related code

- `node/client_priority.py` — priority store + honour order
- `node/update_push.py` — operator push + client apply
- `node/operator_admin.py` — controller the GUI drives
- `client/update_receive.py` — residual frame receive helper
