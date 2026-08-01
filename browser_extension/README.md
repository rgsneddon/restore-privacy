# Restore Privacy Suite — browser extension

Chromium **Manifest V3** extension for **browser-scoped** Connect / Disconnect.
It sits beside **Restore Privacy Suite 1.0.0** native installers; it is not a
replacement for residual TUN.

## Honesty

- **Browser only:** routes this browser’s traffic via the configured **local proxy** path (`chrome.proxy`).
- **Not OS residual:** does **not** create Wintun / Packet Tunnel / system residual TUN. Suite native clients (Windows · Android · macOS · iOS · Linux, catalog **1.0.0**) remain the residual product path.
- Default proxy target is `socks5://127.0.0.1:1080` (local companion / future bridge). Override via Connect options if your browser stack exposes a different local path.

## Load unpacked (developer)

1. Open Chromium / Chrome / Edge → `chrome://extensions`
2. Enable **Developer mode**
3. **Load unpacked** → select this `browser_extension/` directory

Any custom browser that loads Chromium MV3 extensions can use the same package.

## Files

| Path | Role |
|------|------|
| `manifest.json` | MV3 manifest (`proxy`, `storage`) |
| `lib/vpn_core.js` | Pure enable/disable/status (unit-tested) |
| `lib/proxy_adapter.js` | `chrome.proxy.settings` adapter |
| `background.js` | Service worker |
| `popup.html` / `popup.js` / `popup.css` | Connect / Disconnect UI |

## Package zip (release asset)

```bash
cd browser_extension
zip -r ../releases/0.4.4/restore-privacy-browser-extension-0.4.4.zip . \
  -x '*.DS_Store' -x '*__pycache__*'
```

## Pay / native residual

https://restoreprivacy.online/
