# Staged installers for paid fulfilment

Catalog packages under `{VERSION}/` are served by the status host after payment
(`open_release_asset` → local source). This keeps fulfilment working when the
GitHub repo is private without requiring a runtime `RPT_GITHUB_TOKEN`.

Do not put `*.priv` here. Re-stage from `releases/{VERSION}/` on each ship.
