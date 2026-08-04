# kyrusfables command cheatsheet

Repo: `/Users/russellsneddon/restore-privacy`  
Pin: `$(cat client/VERSION)`

## Full path (typical Darwin operator Mac)

```bash
cd /Users/russellsneddon/restore-privacy
PIN=$(cat client/VERSION)

# Gates
cd client_app && flutter test \
  test/macos_settings_and_vpn_ne_test.dart \
  test/macos_vpn_permission_sequence_test.dart \
  test/ios_vpn_prepare_honesty_test.dart \
  test/apple_vpn_prepare_before_connect_test.dart \
  test/connect_status_test.dart && cd ..

# Build (+ optional Helsinki in one shot)
python3 "scripts/build_suite_${PIN}.py"
# python3 "scripts/build_suite_${PIN}.py" --host-paid

# Explicit NE / seal re-check (when not already covered)
python3 scripts/apple_ship_gates.py || true
# residual-team side only:
# python3 scripts/sign_macos_residual_team.py --app path/to/restore_privacy_client.app

# Docs: edit README / handoffs if pin or filenames changed

# Git
git add -A && git status
git commit -m "ship(${PIN}): monopin seals, NE tradeoff, docs"
git pull --rebase origin main
git push origin HEAD

# Deploy if not --host-paid
python3 scripts/host_paid_assets_vps.py --stage --upload --force
```

## Seal tradeoff (must hold)

| Artifact | Signing | Host `packet-tunnel-provider` | Gatekeeper |
|----------|---------|--------------------------------|------------|
| monopin `*-macos.zip` | Notarized Developer ID | **no** | openable |
| residual-team zip/app | Apple Development / Team residual | **yes** | residual Connect / System Settings VPN |

## Flutter prepare honesty

- `applePlatformNeedsVpnPrepare` → macOS + iOS
- `macosVpnActionFromPrepareMap` → missing host NE key is N/A; only `== false` is missing
