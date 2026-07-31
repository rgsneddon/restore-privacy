# Apple handoff — Restore Privacy **0.6.0**

**Monopin:** `0.6.0`

## Ship checklist

| Step | Action |
|------|--------|
| 1 | `flutter build macos --release` + `flutter build ios --release --no-codesign` |
| 2 | `python3 scripts/build_release_0.6.0.py --apple-only` (Team residual NE + DevID notarize + iOS Team-sign) |
| 3 | Host: `host_paid_assets_vps.py --stage --upload --version 0.6.0 --force` |

**CFBundleShortVersionString** must equal **0.6.0**.

### Residual vs catalog

| Artifact | Residual NE | Use |
|----------|-------------|-----|
| `*.residual-team.app` | Yes | Local residual Connect |
| Catalog DevID zip | No (AMFI) | Paid download |

### 0.6.0 product notes

- Client receive path for residual **UPDATE_PUSH** (upgrade directive version/url)
- Seamless keygen rollover across monopin still required
- Residual peers IS/DE; default entry DE

```bash
./scripts/open_macos_residual_connect.sh
```
