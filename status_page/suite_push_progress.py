"""In-process push-job progress for admin Helsinki suite push UI.

Pure state transitions are unit-tested; jobs run stage/upload with callbacks.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

# job_id -> job dict
_JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()

# Row status values for the responsive table
STATUS_PENDING = "pending"
STATUS_UPLOADING = "uploading"
STATUS_DONE = "done"
STATUS_SKIPPED = "skipped"
STATUS_ERROR = "error"

DONE_STATUSES = frozenset({STATUS_DONE, STATUS_SKIPPED})


def progress_transition(
    row: dict[str, Any],
    *,
    status: str,
    progress: int | None = None,
) -> dict[str, Any]:
    """Pure per-row progress transition (pending → uploading → done)."""
    out = dict(row)
    st = (status or STATUS_PENDING).strip().lower()
    out["status"] = st
    if progress is not None:
        out["progress"] = max(0, min(100, int(progress)))
    elif st == STATUS_PENDING:
        out["progress"] = 0
    elif st == STATUS_UPLOADING and int(out.get("progress") or 0) < 10:
        out["progress"] = 10
    elif st in (STATUS_DONE, STATUS_SKIPPED):
        out["progress"] = 100
    elif st == STATUS_ERROR:
        out["progress"] = int(out.get("progress") or 0)
    # Green-done flag for UI
    out["done"] = st in DONE_STATUSES
    out["green_done"] = st == STATUS_DONE
    return out


def job_snapshot(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        j = _JOBS.get(job_id)
        return dict(j) if j else None


def list_job_packages(job_id: str) -> list[dict[str, Any]]:
    snap = job_snapshot(job_id)
    if not snap:
        return []
    return list(snap.get("packages") or [])


def create_job_from_inventory(inv: dict[str, Any], *, options: dict[str, Any] | None = None) -> str:
    """Create a pending job from brand inventory rows."""
    job_id = uuid.uuid4().hex[:16]
    packages = []
    for p in inv.get("packages") or []:
        packages.append(
            progress_transition(
                {
                    "kind": p.get("kind"),
                    "product": p.get("product"),
                    "platform": p.get("platform"),
                    "filename": p.get("filename"),
                    "present": p.get("present"),
                    "staged": p.get("staged"),
                    "size": p.get("size"),
                    "path": p.get("path"),
                },
                status=STATUS_PENDING,
                progress=0,
            )
        )
    job = {
        "id": job_id,
        "state": "pending",
        "ok": None,
        "error": "",
        "created_unix": int(time.time()),
        "updated_unix": int(time.time()),
        "options": dict(options or {}),
        "packages": packages,
        "total": len(packages),
        "done_count": 0,
        "message": "",
    }
    with _LOCK:
        _JOBS[job_id] = job
    return job_id


def _update_file(job_id: str, filename: str, status: str, progress: int) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        pkgs = list(job.get("packages") or [])
        for i, p in enumerate(pkgs):
            if p.get("filename") == filename:
                pkgs[i] = progress_transition(p, status=status, progress=progress)
                break
        job["packages"] = pkgs
        job["done_count"] = sum(1 for p in pkgs if p.get("done"))
        job["updated_unix"] = int(time.time())
        if job.get("state") == "pending":
            job["state"] = "running"


def _finish_job(job_id: str, *, ok: bool, error: str = "", message: str = "") -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job["ok"] = ok
        job["error"] = error
        job["message"] = message
        job["state"] = "complete" if ok else "failed"
        job["updated_unix"] = int(time.time())
        # Mark remaining pending as skipped on success dry-run end
        if ok:
            pkgs = []
            for p in job.get("packages") or []:
                if p.get("status") == STATUS_PENDING:
                    pkgs.append(progress_transition(p, status=STATUS_SKIPPED, progress=0))
                else:
                    pkgs.append(p)
            job["packages"] = pkgs
            job["done_count"] = sum(1 for p in pkgs if p.get("done"))


def start_push_job(
    controller: Any,
    *,
    version: str | None = None,
    stage: bool = True,
    upload: bool = True,
    dry_run: bool = False,
    force: bool = False,
    allow_missing: bool = True,
    install_serve: bool = False,
) -> dict[str, Any]:
    """Create job, start background brand push, return job id + initial snapshot."""
    inv = controller.list_local_packages(version=version, brand_wide=True)
    if not inv.get("ok") and not inv.get("packages"):
        return {"ok": False, "error": inv.get("error") or "inventory failed"}
    opts = {
        "version": version or controller.catalog_version_default(),
        "stage": stage,
        "upload": upload,
        "dry_run": dry_run,
        "force": force,
        "allow_missing": allow_missing,
        "install_serve": install_serve,
    }
    job_id = create_job_from_inventory(inv, options=opts)

    def worker() -> None:
        def cb(filename: str, status: str, progress: int) -> None:
            _update_file(job_id, filename, status, progress)

        try:
            result = controller.push_suite_packages(
                version=opts["version"],
                stage=stage,
                upload=upload,
                dry_run=dry_run,
                force=force,
                allow_missing=allow_missing,
                install_serve=install_serve,
                progress_cb=cb,
                brand_wide=True,
            )
            if result.get("missing_ssh_keys"):
                _finish_job(
                    job_id,
                    ok=False,
                    error=str(result.get("error") or "SSH keys missing"),
                    message="missing_ssh_keys",
                )
                return
            _finish_job(
                job_id,
                ok=bool(result.get("ok")),
                error=str(result.get("error") or ""),
                message=str(result.get("suite") or ""),
            )
        except Exception as exc:  # noqa: BLE001
            _finish_job(job_id, ok=False, error=str(exc)[:300])

    # For dry_run without background need, still use thread so poll UI works
    th = threading.Thread(target=worker, name=f"suite-push-{job_id}", daemon=True)
    th.start()
    snap = job_snapshot(job_id) or {}
    return {"ok": True, "job_id": job_id, "job": snap}
