"""Admin — /admin/intake/* routes (Regulation Intake Wizard state machine)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import require_admin
from retrieval.aria_retrieval import _get_supabase

router = APIRouter(prefix="/admin/intake", tags=["admin-intake"])


REGULATOR_MAP = {
    "sr_letter":      "Federal Reserve",
    "occ_bulletin":   "OCC",
    "fed_guidance":   "Federal Reserve",
    "nccob_circular": "NCCOB",
}

FILENAME_PATTERN = {
    "sr_letter":      "GUIDANCE_SR-XX-YY.pdf",
    "occ_bulletin":   "OCC_BULLETIN-YYYY-NN.pdf",
    "fed_guidance":   "FED_Topic-YYYY.pdf",
    "nccob_circular": "NCCOB_CIRCULAR-YYYY-NN.pdf",
}


def sb():
    return _get_supabase()


# ── Start intake session ──────────────────────────────────────────────────

class StartIntakeBody(BaseModel):
    document_id: str
    doc_type: str
    triggered_by: str
    supersedes_doc_id: str = None


@router.post("/start", status_code=201)
def start_intake(body: StartIntakeBody, _=Depends(require_admin)):
    row = {
        "document_id":  body.document_id,
        "doc_type":     body.doc_type,
        "triggered_by": body.triggered_by,
        "stage":        1,
        "status":       "in_progress",
    }
    if body.supersedes_doc_id:
        row["supersedes_doc_id"] = body.supersedes_doc_id

    resp = sb().table("intake_sessions").insert(row).execute()
    return resp.data[0]


# ── Update stage ──────────────────────────────────────────────────────────

class StageUpdateBody(BaseModel):
    stage: int
    status: str = "in_progress"


@router.patch("/{session_id}/stage")
def update_stage(session_id: str, body: StageUpdateBody, _=Depends(require_admin)):
    resp = sb().table("intake_sessions").update({
        "stage":  body.stage,
        "status": body.status,
    }).eq("id", session_id).execute()

    if not resp.data:
        raise HTTPException(status_code=404, detail="Session not found")
    return resp.data[0]


# ── Confirm Obsidian gate (Stage 2 hard gate) ─────────────────────────────

@router.post("/{session_id}/confirm-obsidian")
def confirm_obsidian(session_id: str, _=Depends(require_admin)):
    resp = sb().table("intake_sessions").update({
        "obsidian_gate_checked": True,
        "stage": 3,
    }).eq("id", session_id).execute()

    if not resp.data:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"confirmed": True, "session": resp.data[0]}


# ── Generate Obsidian frontmatter template ────────────────────────────────

class TemplateBody(BaseModel):
    doc_type: str
    filename: str
    date_issued: str = "YYYY-MM-DD"


@router.post("/generate-template")
def generate_template(body: TemplateBody, _=Depends(require_admin)):
    regulator = REGULATOR_MAP.get(body.doc_type, "Unknown")

    # Infer title from filename
    title = body.filename.replace(".pdf", "").replace("_", " ").replace("-", " ")

    template = f"""---
title: {title}
type: {body.doc_type}
issued_by: {regulator}
date_issued: {body.date_issued}
effective_date: YYYY-MM-DD
status: active
supersedes: []
superseded_by: []
jurisdictions: [US-Federal]
tags: []
related_programs: []
examiner_focus: []
---

## Summary
[Expert summary here — 2-3 sentences]

## Key Requirements
- [Requirement 1]
- [Requirement 2]

## Bank Size Applicability
- [Threshold and what changes]

## Related Regulations
[Add [[wikilinks]] to related regulations]

## Common Pitfalls
[Expert notes on what banks get wrong]

## Examiner Focus Areas
[What examiners check in examinations]
"""
    return {"template": template, "filename_pattern": FILENAME_PATTERN.get(body.doc_type)}


# ── Complete intake session ───────────────────────────────────────────────

@router.post("/{session_id}/complete")
def complete_intake(session_id: str, _=Depends(require_admin)):
    session_resp = sb().table("intake_sessions").select("started_at").eq("id", session_id).execute()
    if not session_resp.data:
        raise HTTPException(status_code=404, detail="Session not found")

    started = datetime.fromisoformat(session_resp.data[0]["started_at"].replace("Z", "+00:00"))
    duration = int((datetime.now(timezone.utc) - started).total_seconds())

    resp = sb().table("intake_sessions").update({
        "status":           "complete",
        "stage":            5,
        "completed_at":     datetime.now(timezone.utc).isoformat(),
        "duration_seconds": duration,
    }).eq("id", session_id).execute()

    # Update linked document status
    session = resp.data[0]
    if session.get("document_id"):
        sb().table("corpus_docs").update({
            "status":       "indexed",
            "intake_stage": None,
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", session["document_id"]).execute()

    return session


# ── List all sessions ─────────────────────────────────────────────────────

@router.get("")
def list_sessions(
    status: str = None,
    limit: int = 20,
    _=Depends(require_admin),
):
    q = sb().table("intake_sessions").select("*, documents(filename, status)").order("created_at", desc=True)
    if status:
        q = q.eq("status", status)
    resp = q.limit(limit).execute()
    return {"sessions": resp.data or []}
