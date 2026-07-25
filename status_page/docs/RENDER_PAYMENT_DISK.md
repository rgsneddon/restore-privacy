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

## Apply to live service

### A) Script (API key)

```powershell
$env:RENDER_API_KEY = 'rnd_...'   # Dashboard → Account Settings → API Keys
cd path\to\restore_privacy
.\scripts\apply_render_payment_disk.ps1
```

Sets `RPT_PAYMENT_DATA_DIR=/var/data/rpt-payment`, tries disk create via API, triggers deploy.
Use `-WhatIf` to list the service without changes. Exit `2` if the API key is missing.

### B) Dashboard Blueprint

Blueprints → open the repo blueprint → **Apply** / sync so `render.yaml` disk + env land on
`restore-privacy-status`. Service plan must be **starter+** before disk attach succeeds.

### C) Manual Disks page

Service → **Disks** → add disk mount `/var/data` → Environment →  
`RPT_PAYMENT_DATA_DIR=/var/data/rpt-payment` → deploy.

## One-shot migration (existing free/ephemeral DB)

If you already have grants on the old ephemeral path
(`status_page/data/paid_downloads.sqlite3` inside the service):

1. Apply the blueprint (or attach disk + env in Dashboard).
2. **Automatic (shipped):** on startup, when the durable DB has **no** grant or
   licence rows but a legacy `paid_downloads.sqlite3` still has history, the
   status app **copies** that file into `$RPT_PAYMENT_DATA_DIR` once
   (`payments.ensure_payment_db_migrated_from_legacy`). It never overwrites a
   durable DB that already has rows.
3. Manual fallback (Shell tab if auto-migrate cannot find the old path):

   ```bash
   mkdir -p /var/data/rpt-payment
   cp -a /opt/render/project/src/status_page/data/paid_downloads.sqlite3 \
     /var/data/rpt-payment/ 2>/dev/null || true
   # Paths vary by rootDir; prefer copying from wherever paid_downloads.sqlite3 lives today.
   ```

4. Confirm `/admin` → Licence database / Paid download grants still list rows
   (admin shows grant/licence counts and an ephemeral-risk warning if the env
   is not on the persistent disk).
5. Keep `RPT_PAYMENT_DATA_DIR=/var/data/rpt-payment` set permanently.

## Honesty

- Residual fleet wipe (IS → RO → DE) is separate; payment store is wipe-protected
  in product wipe helpers.
- Without a paid plan + disk, redeploys reset admin history even if residual
  peers are untouched.
