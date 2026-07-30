# Apple handoff — Restore Privacy **0.5.8**

**Monopin:** `0.5.8`

## Ship checklist

| Step | Action |
|------|--------|
| 1 | `flutter build macos --release` + `flutter build ios --release --no-codesign` |
| 2 | `python3 scripts/build_release_0.5.8.py --apple-only` (Team residual NE + DevID notarize + iOS Team-sign) |
| 3 | Host: `host_paid_assets_vps.py --stage --upload --version 0.5.8 --force` |

**CFBundleShortVersionString** must equal **0.5.8**.

### Residual vs catalog

| Artifact | Residual NE | Use |
|----------|-------------|-----|
| `*.residual-team.app` | Yes | Local residual Connect |
| Catalog DevID zip | No (AMFI) | Paid download |

### 0.5.8 product notes

- Upgrade banner → monopin download mint (status host)
- Keygen rollover on upgrade
- Cover timer interval + session crypto reuse; privacy-scale lean defaults
- Residual peers IS/DE/US; IPv4 always on; IPv6 Settings toggle

```bash
./scripts/open_macos_residual_connect.sh
```
