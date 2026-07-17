# macOS — build on Mac later

Flutter `macos/` scaffold is present.

## On your Mac

```bash
cd client_app
flutter pub get
flutter run -d macos
# or
flutter build macos
```

## Product behavior

Same retro CLI window and auto-connect as Windows/Android (`lib/main.dart`).

For **full system VPN** on macOS, add a **System Extension / Network Extension** packet tunnel that speaks RPT2 (shared protocol with `client/connect.py`). The UI app can stay Flutter; the extension is native Swift/ObjC.

## Keys

Load from a user-local secrets dir (mirror of Windows `~/.restore-privacy/secrets/`):

- `client_ed25519.priv`
- `node_elgamal.pub`

Endpoint default: `104.156.224.47:44044` UDP (`lib/rpt_config.dart`).

## Signing

Notarization and Developer ID signing are done on the Mac only.
