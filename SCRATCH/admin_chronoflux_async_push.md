# Admin ChronoFlux — async suite push seal

## Gap
Primary Helsinki suite push UX is async (`data-async-push=1` → job worker).
Sync Handler path already sealed; worker success did not.

## Fix
`status_page/suite_push_progress.py` worker calls `progress_admin_action` only
when `job_ok` after `push_suite_packages`, stores `job["chronoflux"]`.
Failures / start alone do not mint.

## Tests
`tests/test_admin_chronoflux.py::TestAsyncSuitePushChronoflux`
- success mints push_suite_packages block + job chronoflux snapshot
- failure does not mint
- source asserts `if job_ok:` + progress_admin_action

Unit test side_effect overrides `remote`/`ledger_path` without kwargs clash
(production passes `remote=True`).

## Verify
```
PYTHONPATH=status_page python3 -m unittest tests.test_admin_chronoflux -v
# 10 OK
```
