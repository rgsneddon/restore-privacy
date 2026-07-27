# Release 0.5.1

## Catalog monopin
- Product monopin **0.5.1**

## Highlights
- **macOS / iOS:** Discrete **Quit** control on the main connection screen (bottom-right). Selecting Quit **stops the Packet Tunnel** then **exits** the app completely (minimize still keeps residual up).
- **Keygen portability:** Active `RPT-KEY-…` re-applies on newer monopin builds (subscription-scoped, not app-version-scoped).
- **Upgrade banner:** “New version available” + paid download path on Windows, Linux, and Flutter residual shells (absolute `https://` pay URLs).
- **Status host:** Public `GET /api/catalog-version` for live monopin discovery (after deploy).

## Package honesty (this ship)

| Platform | Build |
|----------|--------|
| **macOS** | Native Flutter rebuild on Mac when secrets/signing allow; residual Team-sign for local NE |
| **iOS** | Native Flutter rebuild on Mac when Team-sign path available |
| **Windows** | Build on Windows x64 — see `client/windows/WINDOWS_HANDOFF_0.5.1.md` |
| **Linux** | Prefer native rebuild; else CF from prior pin with honest notes |
| **Android** | Flutter release when SDK present; else CF residual-wire with honest notes |

## Operator

```bash
python3 scripts/build_release_0.5.1.py --apple-only
python3 scripts/build_release_0.5.1.py --windows-only   # Windows host
RPT_SSH_USER=raskul RPT_SSH_SUDO=1 python3 scripts/host_paid_assets_vps.py \
  --stage --upload --version 0.5.1 --force
```

## Docs
- `client_app/APPLE_HANDOFF_0.5.1.md`
- `client/windows/WINDOWS_HANDOFF_0.5.1.md`
