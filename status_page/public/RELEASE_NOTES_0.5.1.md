# Release 0.5.1

## Catalog monopin
- Product monopin **0.5.1**

## Highlights
- Discrete **Quit** on Apple residual main connection screen (tunnel stop → app exit)
- Keygen re-apply across monopin upgrades while subscription is active
- macOS paid zip **CFBundleShortVersionString == 0.5.1** (no stale pre-monopin CF as current catalog)

## Package table

| Platform | Note |
|----------|------|
| **macOS** | Native monopin **0.5.1** CFBundle; DevID+notarize when sealed |
| **iOS** | Native monopin **0.5.1** sideload when available |
| **Windows / Linux / Android** | See `WINDOWS_HANDOFF_0.5.1.md` for remaining PE rebuilds |

## Operator

```bash
python scripts/build_release_0.5.1.py --apple-only
RPT_SSH_USER=raskul RPT_SSH_SUDO=1 python scripts/host_paid_assets_vps.py --stage --upload --version 0.5.1 --force
```
