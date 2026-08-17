"""Grok Build CLI jobs for the GOD page."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

BRIEF_LINE = "Evolve Suite is the surface. The four agents have the brief."

_JOBS: dict[str, dict[str, Any]] = {}


def detect_device(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if "iphone" in ua or "ipad" in ua or "ios" in ua:
        return "ios"
    if "android" in ua:
        return "android"
    if "macintosh" in ua or "mac os" in ua:
        return "macos"
    if "windows" in ua:
        return "windows"
    if "linux" in ua:
        return "linux"
    return "macos"


def run_suite_build(
    *,
    device: str = "macos",
    brief: str = BRIEF_LINE,
    xai_fn=None,
) -> dict[str, Any]:
    plat = (device or "macos").strip().lower() or "macos"
    text = (brief or BRIEF_LINE).strip() or BRIEF_LINE
    note = ""
    if xai_fn is not None:
        try:
            note = str(xai_fn(plat, text) or text)
        except Exception:
            note = text
    from grokbot import LEARNERS, grokbot_assist_learn

    lines = [f"Grok Build · {plat}", note or text]
    for agent in LEARNERS:
        grokbot_assist_learn(agent, "evolve_suite", text, persist=True)
        lines.append(f"{agent} has the brief")
    lines.append(BRIEF_LINE)
    download = f"/downloads/evolve-suite-{plat}.zip"
    return {
        "ok": True,
        "done": True,
        "device": plat,
        "download": download,
        "lines": lines,
        "brief": text,
    }


def start_suite_build(
    *,
    device: str = "",
    brief: str = "",
    user_agent: str = "",
    cookie: str = "",
    authorization: str = "",
    token: str = "",
) -> dict[str, Any]:
    _ = (cookie, authorization, token)
    plat = (device or "").strip() or detect_device(user_agent)
    job = run_suite_build(device=plat, brief=brief or BRIEF_LINE)
    job_id = uuid4().hex[:12]
    job["id"] = job_id
    _JOBS[job_id] = job
    return job


def get_suite_build(job_id: str) -> dict[str, Any]:
    hit = _JOBS.get(str(job_id or ""))
    if not hit:
        return {"ok": False, "reason": "unknown_job"}
    return dict(hit)


def tick_suite_build(job_id: str) -> dict[str, Any]:
    hit = get_suite_build(job_id)
    if not hit.get("ok"):
        return hit
    hit["tick"] = int(hit.get("tick") or 0) + 1
    _JOBS[str(job_id)] = hit
    return hit
