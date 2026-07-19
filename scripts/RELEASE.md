# Release packaging notes

## Current tag script

For shipping a version, use **only the script matching the tag you are cutting**:

| Tag | Script |
|-----|--------|
| 0.1.8 | `scripts/build_release_0.1.8.py` |

Older `build_release_0.*.py` files are **historical archives**. Prefer copying the
**latest** script when starting a new version rather than editing an ancient one.

Shared gates every release must keep:

1. **`_assert_no_priv(OUT)`** (or equivalent) on the release output directory.
2. Inject / provision that copies **only** `node_elgamal.pub` — never `node_elgamal.priv`.
3. **Never force-add `secrets/`** to git (see root `.gitignore`).
4. **Linux wheels:** re-run `python scripts/package_linux.py` (also invoked from
   `build_release_0.1.8.py`) so manylinux **CPython 3.8–3.12** wheels stay current.

## Checklist (short)

```bash
# Bump VERSION / downloads catalog / installer VERSION first
python scripts/build_release_0.1.8.py   # or the current-tag script
# Confirm releases/<version>/ has windows + linux + android + apple assets
# gh release create <tag> with those files
```
