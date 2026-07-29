# Release notes — Restore Privacy **0.5.5**

**Catalog monopin:** 0.5.5

## Highlights

- **Windows Connect fix:** restore `client.windows.hidden_subprocess` so residual `configure_address` / netsh steps no longer fail with `ModuleNotFoundError` (frozen PE hiddenimport pinned).
- **Settings:** dual-stack **IPv4 residual** / **IPv6 residual** are the top switchers in **Browsing speed / privacy scale**.
- Fresh **native Windows multihop** setup for 0.5.5.

## Operators

```bash
python scripts/build_release_0.5.5.py --windows-only
python scripts/host_paid_assets_vps.py --stage --upload --version 0.5.5 --force --allow-missing
python scripts/breadcrumbs_vault.py publish --version 0.5.5
```
