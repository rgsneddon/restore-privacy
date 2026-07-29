# Release 0.5.5

## Catalog monopin
- Product monopin **0.5.5**
- Default residual entry remains **United States**

## Highlights
- **Settings privacy scale:** residual **IPv4** and **IPv6** toggles at the **top** of the privacy-scale list (above traffic shaping, outer obfuscation, multi-hop)
- User-visible explainers + Flutter hover tooltips for residual dual-stack
- Defaults: residual IPv4 **ON**, residual IPv6 **ON** (lean dual-stack residual)
- Connect honesty: status does not claim full residual capture when IPv4 residual is off, or IPv6 protection when IPv6 residual is off

## Package honesty
| Platform | 0.5.5 ship |
|----------|-----------|
| **macOS** | Native monopin seal (DevID + notarize) when Mac-built |
| **iOS** | Native Team-sign sideload when Mac-built |
| **Windows** | CF or native multihop PE when Windows host rebuilds |
| **Linux** | CF or native when package path runs |
| **Android** | CF residual-wire catalog filename 0.5.5 |

## Docs
- `client_app/APPLE_HANDOFF_0.5.5.md`
