# Staged installers for paid fulfilment

Catalog packages under `{VERSION}/` are served by the status host after payment
(`open_release_asset` → local source). This keeps fulfilment working when the
GitHub repo is private without requiring a runtime `RPT_GITHUB_TOKEN`.

Current ship: **0.4.1** under `0.4.1/`. Keep prior version dirs only if needed for rollback.

**0.4.1 staging:** Packages staged from `releases/0.4.1/` (Windows multihop PE
rebuilt on Windows host; Apple packages via Mac handoff
`client_app/APPLE_HANDOFF_0.4.1.md`; Android/Linux may carry-forward under
**0.4.1** filenames until native rebuild — see `releases/0.4.1/`). Node-only
**zram + LUKS2** is a host deploy feature and does not change residual client packages.

Do not put `*.priv` here. Re-stage from `releases/{VERSION}/` on each ship.
