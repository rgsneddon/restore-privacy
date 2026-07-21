# Staged installers for paid fulfilment

Catalog packages under `{VERSION}/` are served by the status host after payment
(`open_release_asset` → local source). This keeps fulfilment working when the
GitHub repo is private without requiring a runtime `RPT_GITHUB_TOKEN`.

Current ship: **0.3.3** under `0.3.3/`. Keep prior version dirs only if needed for rollback.

**0.3.3 staging:** Windows setup was rebuilt on this host; Android APK and Linux tarball match `releases/0.3.0` (see `releases/0.3.0/SHA256SUMS.json`). macOS and iOS zips are **byte-identical to 0.2.3 priors** staged when Apple toolchains were absent — they are not freshly rebuilt 0.3.0 clients; residual Packet Tunnel signing still needs Mac work for a true 0.3.0 Apple rebuild.

Do not put `*.priv` here. Re-stage from `releases/{VERSION}/` on each ship.
