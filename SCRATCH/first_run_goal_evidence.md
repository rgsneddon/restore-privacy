# First-run goal evidence (skeptic-addressed)

## Full licence text
- Scroll pane uses `kFullEndUserLicenceText` from monorepo LICENSE (~11KB).
- Markers: PROPRIETARY FULL COPYRIGHT LICENCE, 1. DEFINITIONS, END OF LICENCE.
- Tests: first_run_licence_scroll.out

## Seed hang
- Timed attach/publish; timeout error path. first_run_seed_confirm.out

## Evolve inherit (real apply + family host)
- applySuiteAccountToWalletAndEvolve → new wallet.initialize + reloadFromStore → hasAppAccess.
- SuiteFamilyHost always reloadFromStore on bus (even when isReady).
- Widget: SuiteFamilyHost ready + ACCESS_OK + inherit banner; cold path NEED_AUTH.
- evolve_inherits_suite_login.out

## macOS VPN sequence + flow order
- macos_vpn_permission_sequence.out, first_run_flow_order.out
