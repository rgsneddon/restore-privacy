# Apple handoff — Restore Privacy 0.5.0

Catalog monopin: **0.5.0**

## Shipped status (this Mac monopin)

| Package | Status |
|---------|--------|
| `restore-privacy-client-0.5.0-macos.zip` | **Developer ID signed + notarized + stapled** (public catalog seal) |
| `restore-privacy-client-0.5.0-ios.zip` | **Team-signed sideload** (not App Store) |

Hosted at VPS `/opt/restore-privacy/paid_assets/0.5.0/` for paid fulfilment. Default residual entry: **United States**.

## Product behaviour (must ship in macOS + iOS builds)

Parity with desktop (catalog **0.5.0** product pin):

1. **Accept end-user licence** (local only).
2. **Connect allowed = active subscription + keygen activated.**
3. **EXPIRED renew surface** when subscription is revoked/failed/period-ended.
4. **Device bind after active keygen** when node requires payment entitlement.
5. **Download alone does not unlock residual.**
6. Connect only while status **OK**; catalog pay monthly or yearly.
7. **Privacy-scale Settings** — lean residual defaults (shape/obfs/multi-hop off).
8. **Main-shell country picker** above Connect: **IS / RO / US**; default **US**.
9. Banner: **Virtual Private Network**.
10. **Version monopin 0.5.0** — `CFBundleShortVersionString` **0.5.0**.
11. Keygen unlock sheet is single-path (no double-present on Accept).

## Mac rebuild (operator)

```bash
cd client_app
flutter build macos --release
flutter build ios --no-codesign
python3 scripts/build_release_0.5.0.py --apple-only
# residual Team-sign for local NE residual testing:
python3 scripts/sign_macos_residual_team.py --app client_app/build/macos/Build/Products/Release/restore_privacy_client.app
```
