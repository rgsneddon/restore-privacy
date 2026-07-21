# Restore Privacy **0.2.9** — release notes

**Status:** Public package release (signed Apple packages published).  
**Tag:** `0.2.9`  
**URL:** https://github.com/rgsneddon/restore-privacy/releases/tag/0.2.9

Catalog jumps from public **0.2.3** straight to **0.2.9** (no intermediate public tags 0.2.4–0.2.8).

## Highlights

- Production node remains **`82.221.101.241:44044`**.
- **macOS:** hide main window to menu-bar tray after product full-tunnel Connect (Show / Disconnect / Quit); Packet Tunnel stays up until explicit Disconnect.
- **macOS residual:** Team residual Packet Tunnel sign path + home secrets seed for residual without host App Group.
- **Security audit:** public AUDIT.md / audit.md and 4-hour node audit refresh.
- Carries forward 0.2.3: Settings transparency, licence gate, aggregate monitoring, native pad/obfs/PFS, threat model docs, LUKS FDE helpers.

## Downloads

| Asset | Notes |
|-------|--------|
| `restore-privacy-client-0.2.9-windows-x64-setup.exe` | Setup installer |
| `restore-privacy-client-0.2.9-android.apk` | Flutter APK |
| `restore-privacy-client-0.2.9-linux-x64.tar.gz` | Installer package |
| `restore-privacy-client-0.2.9-macos.zip` | **Developer ID signed + notarized** (`node_elgamal.pub` only); host omits restricted NE entitlement so the app **opens** under Gatekeeper (Packet Tunnel NE remains on the appex) |
| `restore-privacy-client-0.2.9-ios.zip` | **Team-signed sideload** (`node_elgamal.pub` only) |

## Signing / privacy

- macOS: Developer ID Application (SFCBP95595) + notarized/stapled.
- iOS: Apple Distribution team-signed sideload (Runner + Packet Tunnel).
- Packages never ship `node_elgamal.priv` or a shared `client_ed25519.priv`.
- Residual public IP only when OS tunnel is connected.

## Upgrade

Install **0.2.9** from this GitHub Release ([0.2.9](https://github.com/rgsneddon/restore-privacy/releases/tag/0.2.9)) or the status page download catalog (catalog **v0.2.9**, paid buttons fulfil the same assets). Accept the end-user licence on first Connect.
