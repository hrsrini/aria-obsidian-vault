"""Admin — /admin/corrections/* routes."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import require_admin
from retrieval.aria_retrieval import aria_query, _get_supabase

router = APIRouter(prefix="/admin/corrections", tags=["admin-corrections"])


def sb():
    return _get_supabase()


class CorrectionBody(BaseModel):
    question: str
    wrong_answer: str
    correct_answer: str = None
    source_doc_id: str = None
    obsidian_note: str = None
    test_case_id: str = None
    flagged_by: str = "admin"


class CorrectionPatchBody(BaseModel):
    status: str = None
    correct_answer: str = None
    resolution_note: str = None


@router.get("")
def list_corrections(status: str = None, limit: int = 50, _=Depends(require_admin)):
    q = sb().table("corrections").select("*").order("created_at", desc=True)
    if status:
        q = q.eq("status", status)
    resp = q.limit(limit).execute()
    return {"corrections": resp.data or []}


@router.post("", status_code=201)
def create_correction(body: CorrectionBody, _=Depends(require_admin)):
    resp = sb().table("corrections").insert(body.model_dump()).execute()
    return resp.data[0]


@router.patch("/{correction_id}")
def update_correction(correction_id: str, body: CorrectionPatchBody, _=Depends(require_admin)):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if body.status in ("resolved", "wont_fix"):
        update["resolved_at"] = datetime.now(timezone.utc).isoformat()

    resp = sb().table("corrections").update(update).eq("id", correction_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Correction not found")
    return resp.data[0]


@router.post("/{correction_id}/retest")
async def retest_correction(correction_id: str, _=Depends(require_admin)):
    correction_resp = sb().table("corrections").select("question").eq("id", correction_id).execute()
    if not correction_resp.data:
        raise HTTPException(status_code=404, detail="Correction not found")

    question = correction_resp.data[0]["question"]
    answer = await aria_query(question)

    # Update status to re_testing
    sb().table("corrections").update({"status": "re_testing"}).eq("id", correction_id).execute()

    return {"new_answer": answer, "question": question}
