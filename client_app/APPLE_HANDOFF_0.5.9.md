# Apple handoff — Restore Privacy **0.5.9**

**Monopin:** `0.5.9`

## Ship checklist

| Step | Action |
|------|--------|
| 1 | `flutter build macos --release` + `flutter build ios --release --no-codesign` |
| 2 | `python3 scripts/build_release_0.5.9.py --apple-only` (Team residual NE + DevID notarize + iOS Team-sign) |
| 3 | Host: `host_paid_assets_vps.py --stage --upload --version 0.5.9 --force` |

**CFBundleShortVersionString** must equal **0.5.9**.

### Residual vs catalog

| Artifact | Residual NE | Use |
|----------|-------------|-----|
| `*.residual-team.app` | Yes | Local residual Connect |
| Catalog DevID zip | No (AMFI) | Paid download |

### 0.5.9 product notes

- Residual peers **IS / DE only** (US retired; prefs normalize US → DE)
- Default entry **DE**; multi-hop exit DE
- **Seamless upgrade:** reuse existing product Packet Tunnel protocol on prepare/Connect (do not orphan System VPN prefs after monopin replace)
- Keygen rollover across monopin upgrades (version-agnostic entitlement)

```bash
./scripts/open_macos_residual_connect.sh
```
