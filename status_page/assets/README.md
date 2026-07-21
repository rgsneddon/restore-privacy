# Staged installers for paid fulfilment

Catalog packages under `{VERSION}/` are served by the status host after payment
(`open_release_asset` → local source). This keeps fulfilment working when the
GitHub repo is private without requiring a runtime `RPT_GITHUB_TOKEN`.

Current ship: **0.3.5** under `0.3.5/`. Keep prior version dirs only if needed for rollback.

**0.3.5 staging:** All five platform packages staged from `releases/0.3.5/` (Apple
notarized macOS + Team-signed iOS when built on this host; Windows/Android/Linux
may carry-forward prior binaries under **0.3.5** filenames — see
`releases/0.3.5/manifest.json`). Node-only **zram + LUKS2** is a host deploy
feature and does not change residual client packages.

Do not put `*.priv` here. Re-stage from `releases/{VERSION}/` on each ship.
