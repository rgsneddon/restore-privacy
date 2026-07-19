# Release packaging notes

## Current tag script

For shipping a version, use **only the script matching the tag you are cutting**:

| Tag | Script |
|-----|--------|
| 0.1.9 (prep) | Copy `scripts/build_release_0.1.8.py` → `build_release_0.1.9.py` when cutting packages; see `scripts/RELEASE_NOTES_0.1.9.md` |
| 0.1.8 | `scripts/build_release_0.1.8.py` (last fully packaged public catalog until 0.1.9 assets ship) |

Older `build_release_0.*.py` files are **historical archives**. Prefer copying the
**latest** script when starting a new version rather than editing an ancient one.

**0.1.9 product change (source):** UK public-IP geo gate removed from client
connect paths (no third-party geo admission). Node admission crypto unchanged.

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
