# Grok session hygiene (Restore Privacy)

## Why this exists

A multi-day Grok Build session on this product (session id
`019f6d4a-60fa-7943-9009-a1cf59e7fb2f`, cwd `C:\Users\rgsne`) grew large enough
to **crash / fail turns**:

| Metric (at investigation) | Value |
|---------------------------|--------|
| Session age | ~6 days (2026-07-16 → 2026-07-22) |
| On-disk session dir | **~346 MB** |
| `updates.jsonl` alone | **~215 MB** |
| Tool calls | ~6.7k |
| Auto-compactions | **34** (~13.6M tokens compacted) |
| Goal classifier fires | ~187 |
| `turn_ended` with `outcome=error` | including **2026-07-22T10:43:02Z** |
| Peak time-to-first-token | ~170 s |

Root cause class: **session bloat + compaction/goal-harness load**, not a single
bad line of product code. Compaction still leaves multi‑hundred‑MB logs on disk
and expensive resume/stream paths.

## Operator practice

1. **After a deploy or large feature is done**, start a **new session** (`/new`
   in the TUI) for the next task.
2. Mid-session, if responses lag hard or tools hang: `/compact` once, or
   `/new` if the thread is already multi-day.
3. Keep Stripe / Render work in **short sessions** (config + one pay test), not
   the same thread as weekly wipe / packaging epics.
4. Global agent rules: `~/.grok/rules/session-hygiene.md`.
5. Config: `~/.grok/config.toml` → `[session] auto_compact_threshold_percent = 75`
   and `[features] two_pass_compaction = true`.

## Quick health check (optional)

From PowerShell (path is URL-encoded cwd):

```powershell
$s = "$env:USERPROFILE\.grok\sessions\C%3A%5CUsers%5Crgsne\*\summary.json"
Get-ChildItem $s -ErrorAction SilentlyContinue | ForEach-Object {
  $dir = $_.Directory
  $mb = [math]::Round(((Get-ChildItem $dir -Recurse -File -EA SilentlyContinue |
    Measure-Object Length -Sum).Sum / 1MB), 1)
  $sum = Get-Content $_.FullName -Raw | ConvertFrom-Json
  [pscustomobject]@{
    Id = $sum.info.id
    MB = $mb
    Messages = $sum.num_messages
    Updated = $sum.updated_at
  }
} | Sort-Object MB -Descending | Format-Table -AutoSize
```

If a session is **\>~100 MB** or multi-day, prefer `/new` for the next task.

## Do not

- Delete session folders unless you intentionally want to free disk and abandon
  `/resume` for that id.
- Re-open the mega-session only to “keep context” when the work product is
  already on `main` and documented in commits.
