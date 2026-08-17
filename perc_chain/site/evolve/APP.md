# Embedded web analyser (`/app/`)

`https://evolve.restoreprivacy.online/app/` is a Flutter web build of Evolve
**4.2.1** (`--base-href /app/`, no `GROK_PROXY_URL`). Chronoflux runs in the
browser; Grok construal stays heuristic.

The compiled `build/web` tree is **not** in git (~40 MB). Rebuild and upload:

```bash
cd ~/evolve
flutter build web --release --base-href /app/ --no-wasm-dry-run
python3 ~/restore-privacy/scripts/deploy_evolve_web_helsinki.py
```

Landing iframe and “Open in the browser” point at `/app/` on this host.
Do not send users to `rgsneddon.github.io/evolve/` — that shell was
published with `<base href="/">` and does not load.
