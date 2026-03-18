"""Admin — /admin/sync/* routes with SSE log streaming."""
import asyncio
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .auth import require_admin
from retrieval.aria_retrieval import _get_supabase

router = APIRouter(prefix="/admin/sync", tags=["admin-sync"])

JOB_COMMANDS = {
    "obsidian_sync":         [sys.executable, "scripts/obsidian_to_graph.py"],
    "graphrag_incremental":  ["python", "-m", "graphrag", "index", "--root", ".", "--resume"],
    "graphrag_full":         ["python", "-m", "graphrag", "index", "--root", "."],
    "embed":                 [sys.executable, "ingestion/embed_documents.py", "--folder", "obsidian-vault/"],
    "verify":                [sys.executable, "scripts/verify_graph.py"],
}

# In-memory log buffer per job_id (cleared on restart)
_log_buffers: dict[str, list[str]] = {}


def sb():
    return _get_supabase()


# ── Trigger a sync job ────────────────────────────────────────────────────

class TriggerBody(BaseModel):
    job_type: str
    triggered_by: str = "admin"


@router.post("/trigger", status_code=201)
async def trigger_job(body: TriggerBody, _=Depends(require_admin)):
    if body.job_type not in JOB_COMMANDS:
        raise HTTPException(status_code=400, detail=f"Unknown job_type: {body.job_type}")

    resp = sb().table("sync_jobs").insert({
        "job_type":     body.job_type,
        "triggered_by": body.triggered_by,
        "status":       "running",
    }).execute()
    job = resp.data[0]
    job_id = job["id"]

    _log_buffers[job_id] = []

    # Run in background
    asyncio.create_task(_run_job(job_id, body.job_type))

    return {"job_id": job_id, "status": "running", "job_type": body.job_type}


async def _run_job(job_id: str, job_type: str):
    cmd = JOB_COMMANDS[job_type]
    start = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        lines = []
        async for line in proc.stdout:
            text = line.decode("utf-8", errors="replace").rstrip()
            lines.append(text)
            _log_buffers.setdefault(job_id, []).append(text)

        await proc.wait()
        duration = int(time.time() - start)
        status = "completed" if proc.returncode == 0 else "failed"
        log_output = "\n".join(lines)

        sb().table("sync_jobs").update({
            "status":           status,
            "completed_at":     datetime.now(timezone.utc).isoformat(),
            "duration_seconds": duration,
            "log_output":       log_output[:10000],
            "error_message":    None if status == "completed" else log_output[-500:],
        }).eq("id", job_id).execute()

    except Exception as e:
        sb().table("sync_jobs").update({
            "status":        "failed",
            "error_message": str(e),
        }).eq("id", job_id).execute()


# ── Stream job log via SSE ────────────────────────────────────────────────

@router.get("/jobs/{job_id}/log")
async def stream_log(job_id: str, _=Depends(require_admin)):
    async def event_generator():
        sent = 0
        max_wait = 1800  # 30 min timeout
        waited = 0

        while waited < max_wait:
            buf = _log_buffers.get(job_id, [])
            if len(buf) > sent:
                for line in buf[sent:]:
                    yield f"data: {line}\n\n"
                sent = len(buf)

            # Check if job is done
            resp = sb().table("sync_jobs").select("status").eq("id", job_id).execute()
            if resp.data and resp.data[0]["status"] in ("completed", "failed"):
                yield f"data: [JOB {resp.data[0]['status'].upper()}]\n\n"
                break

            await asyncio.sleep(0.5)
            waited += 0.5

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Job history ───────────────────────────────────────────────────────────

@router.get("/jobs")
def job_history(limit: int = 20, _=Depends(require_admin)):
    resp = sb().table("sync_jobs").select(
        "id, job_type, triggered_by, status, started_at, completed_at, duration_seconds, docs_processed, error_message"
    ).order("started_at", desc=True).limit(limit).execute()
    return {"jobs": resp.data or []}


# ── Schedule (placeholder — configurable via Railway cron) ───────────────

_schedule = {"enabled": True, "time_utc": "02:00", "scope": "all"}


@router.get("/schedule")
def get_schedule(_=Depends(require_admin)):
    return _schedule


@router.put("/schedule")
def update_schedule(payload: dict, _=Depends(require_admin)):
    _schedule.update(payload)
    return _schedule
