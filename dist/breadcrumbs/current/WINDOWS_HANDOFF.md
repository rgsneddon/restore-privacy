# WINDOWS_HANDOFF_1.0.5.md missing

Monopin 1.0.5: build native PE on Windows and upload to paid_assets/1.0.5/.

---

> **Breadcrumbs vault (Helsinki)** is the source of truth for “what to update” on this monopin. Do **not** treat a private GitHub pull of this file as the primary task queue.
> Fetch: `https://135.181.152.10.sslip.io/breadcrumbs/current/manifest.json` with `X-RPT-Asset-Token`.

---

## Brand-wide large-drive mirror (all installer slots)

The Windows **larger drive** must hold a working monorepo copy **and** every brand
asset from the inventory — not only the Suite Windows setup.exe.

| | |
|--|--|
| **Env** | `RPT_WINDOWS_DRIVE` (or `--dest`) = large-drive root |
| **Monorepo dest** | `{RPT_WINDOWS_DRIVE}/restore-privacy` |
| **Brand slots** | **35** (browser, node_installer, node_operator, rpmail, rpoffice, rpos, rpos_app, suite_client) |
| **Monopin** | **1.0.5** |

```powershell
$env:RPT_WINDOWS_DRIVE = "D:\RestorePrivacyMirror"   # larger drive
python scripts\windows_brand_mirror.py plan
python scripts\windows_brand_mirror.py apply --dest $env:RPT_WINDOWS_DRIVE
```

Inventory kinds covered: suite_client, browser/Rx, rpos, rpos_app (Pens/Tables/Slides),
node_installer, node_operator, rpmail, rpoffice.

Full checklist: vault `WINDOWS_BRAND_CHECKLIST.md` / `windows_brand_mirror.json`
(after `python scripts\breadcrumbs_vault.py stage`).

Native PE remains required: `scripts\build_windows_multihop.py` →
`releases\1.0.5\restore-privacy-client-1.0.5-windows-x64-setup.exe`.
