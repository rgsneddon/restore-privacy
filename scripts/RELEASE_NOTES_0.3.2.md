**0.3.2** — Catalog rebuild: Apple IPv6 kill-switch removed; all platforms pin production node 82.221.101.241:44044; packages ship node_elgamal.pub only.

**0.3.2** — Fixed macOS public package seal (Developer ID + notarized) and iOS Team-signed sideload. Non-Apple platforms carry-forward from 0.3.0.

# Restore Privacy **0.3.2** — release notes

**Status:** Public package release (catalog + packaging).  
**Tag:** `0.3.2`  
**URL:** https://github.com/rgsneddon/restore-privacy/releases/tag/0.3.2

Catalog advances from **0.2.9** to **0.3.2**.

## Highlights

- Production node remains **`82.221.101.241:44044`**.
- **Connect continuity** (∇_μ(ρ_t u^μ)=0 product map): flyclient tip-then-full residual path (skip re-HELLO/routes when residual ready; GW/route prefetch during HELLO); Wintun IF settle poll with legacy-floor max (~0.9s) and ASAP return (no fixed 0.4s+0.5s backlog; one resolve per poll).
- **Status / payments:** private `/admin` payment-processor settings + grants; paid downloads (£2.45 Stripe) with private-repo fulfilment proxy; light/dark admin theme.
- Carries forward 0.2.9: macOS hide-to-tray after full-tunnel Connect; residual Team NE path; security audit refresh.
- Carries forward 0.2.3: Settings transparency, licence gate, aggregate monitoring, native pad/obfs/PFS.

## Downloads

| Asset | Notes |
|-------|--------|
| `restore-privacy-client-0.3.2-windows-x64-setup.exe` | Setup installer |
| `restore-privacy-client-0.3.2-android.apk` | Flutter APK |
| `restore-privacy-client-0.3.2-linux-x64.tar.gz` | Installer package |
| `restore-privacy-client-0.3.2-macos.zip` | **Developer ID signed + notarized** when rebuilt on macOS; may stage prior signed tree when tooling absent |
| `restore-privacy-client-0.3.2-ios.zip` | **Team-signed sideload** when rebuilt; may stage prior when tooling absent |

## Signing / privacy

- macOS: Developer ID Application + notarized/stapled when Apple tools/credentials present.
- iOS: Apple Distribution team-signed sideload when available.
- Packages never ship `node_elgamal.priv` or a shared `client_ed25519.priv`.
- Residual public IP only when OS tunnel is connected.

## Upgrade

Install **0.3.2** from this GitHub Release ([0.3.2](https://github.com/rgsneddon/restore-privacy/releases/tag/0.3.2)) or the VPN APP Shop download catalog (catalog **v0.3.2**, paid buttons fulfil the same assets). Accept the end-user licence on first Connect.
