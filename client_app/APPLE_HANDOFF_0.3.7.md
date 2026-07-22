# Apple handoff — Restore Privacy 0.3.7

Catalog monopin: **0.3.7**

Build on Mac (Developer ID + notarize macOS; Team-signed iOS):

```bash
cd client_app
flutter build macos --release
flutter build ios --release
# then package + sign per APPLE_BUILD.md / prior handoffs
```

Includes subscription keygen unlock (licence accept then keygen), multi-hop residual when enabled.
