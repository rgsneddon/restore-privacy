# Release 0.5.1

## Catalog monopin
- Product monopin **0.5.1**

## Highlights
- Discrete **Quit** on Apple residual main connection screen (tunnel stop → app exit)
- Keygen re-apply across monopin upgrades while subscription is active
- “New version available” paid update path on all client surfaces
- Public `/api/catalog-version` monopin endpoint

## Package table

| Platform | Note |
|----------|------|
| **macOS** | Native Mac rebuild when sealed; residual Team-sign for developer NE |
| **iOS** | Native Mac rebuild / Team-signed sideload when available |
| **Windows / Linux / Android** | Complete on Windows computer — `WINDOWS_HANDOFF_0.5.1.md` |

## Operator

```bash
python scripts/build_release_0.5.1.py
RPT_SSH_USER=raskul RPT_SSH_SUDO=1 python scripts/host_paid_assets_vps.py --stage --upload --version 0.5.1 --force
```
