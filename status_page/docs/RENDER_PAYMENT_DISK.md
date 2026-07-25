# Render: durable payment / admin licence store

Admin **licence database** and **paid download grants** live in SQLite
(`paid_downloads.sqlite3`). Residual node wipe does **not** erase them; a
**Render redeploy** will erase them if the file only sits on the ephemeral
container filesystem.

## Blueprint (shipped)

`render.yaml` on the web service:

| Setting | Value |
|---------|--------|
| `plan` | `starter` (or higher) — **free cannot attach disks** |
| `disk.name` | `rpt-payment-data` |
| `disk.mountPath` | `/var/data` |
| `disk.sizeGB` | `1` |
| `RPT_PAYMENT_DATA_DIR` | `/var/data/rpt-payment` |

The status app creates the directory and opens  
`$RPT_PAYMENT_DATA_DIR/paid_downloads.sqlite3` via `payments.payment_data_dir()`.

## One-shot migration (existing free/ephemeral DB)

If you already have grants on the old ephemeral path
(`status_page/data/paid_downloads.sqlite3` inside the service):

1. Apply the blueprint (or attach disk + env in Dashboard).
2. Before the first deploy that only uses the new path, copy the DB onto the
   mounted disk (Shell tab while old file still exists, or one-off job):

   ```bash
   mkdir -p /var/data/rpt-payment
   cp -a /opt/render/project/src/status_page/data/paid_downloads.sqlite3 \
     /var/data/rpt-payment/ 2>/dev/null || true
   # Paths vary by rootDir; prefer copying from wherever paid_downloads.sqlite3 lives today.
   ```

3. Confirm `/admin` → Licence database / Paid download grants still list rows.
4. Keep `RPT_PAYMENT_DATA_DIR=/var/data/rpt-payment` set permanently.

## Honesty

- Residual fleet wipe (IS → RO → DE) is separate; payment store is wipe-protected
  in product wipe helpers.
- Without a paid plan + disk, redeploys reset admin history even if residual
  peers are untouched.
