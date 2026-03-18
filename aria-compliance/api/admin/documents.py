"""Admin — /admin/documents/* routes."""
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from .auth import require_admin
from retrieval.aria_retrieval import _get_supabase

router = APIRouter(prefix="/admin/documents", tags=["admin-documents"])


def sb():
    return _get_supabase()


# ── List documents ────────────────────────────────────────────────────────

@router.get("")
def list_documents(
    status: str = None,
    limit: int = 50,
    offset: int = 0,
    _=Depends(require_admin),
):
    q = sb().table("corpus_docs").select("*").order("created_at", desc=True)
    if status:
        q = q.eq("status", status)
    resp = q.range(offset, offset + limit - 1).execute()
    return {"documents": resp.data or [], "total": len(resp.data or [])}


# ── Upload PDF ────────────────────────────────────────────────────────────

@router.post("/upload", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = "sr_letter",
    _=Depends(require_admin),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files accepted")

    # Stage to input/ for GraphRAG
    input_dir = "input"
    os.makedirs(input_dir, exist_ok=True)
    dest = os.path.join(input_dir, file.filename)
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)

    # Create documents record
    resp = sb().table("corpus_docs").insert({
        "filename":    file.filename,
        "source_type": "pdf",
        "status":      "pending",
        "intake_stage": 1,
    }).execute()

    return {"document": resp.data[0], "staged_path": dest}


# ── Supersede a document ──────────────────────────────────────────────────

class SupersedeBody(BaseModel):
    superseded_by_id: str


@router.patch("/{doc_id}/supersede")
def supersede_document(
    doc_id: str,
    body: SupersedeBody,
    _=Depends(require_admin),
):
    resp = sb().table("corpus_docs").update({
        "status":       "superseded",
        "superseded_by": body.superseded_by_id,
    }).eq("id", doc_id).execute()

    if not resp.data:
        raise HTTPException(status_code=404, detail="Document not found")
    return resp.data[0]


# ── Trigger reindex for one document ─────────────────────────────────────

@router.post("/{doc_id}/reindex")
def reindex_document(
    doc_id: str,
    triggered_by: str = "admin",
    _=Depends(require_admin),
):
    # Create a sync_job record — actual execution via /admin/sync/trigger
    resp = sb().table("sync_jobs").insert({
        "job_type":     "graphrag_incremental",
        "triggered_by": triggered_by,
        "status":       "running",
    }).execute()

    job = resp.data[0]
    return {"job_id": job["id"], "status": "running", "doc_id": doc_id}


# ── Related documents via Neo4j ───────────────────────────────────────────

@router.get("/related")
async def related_documents(
    filename: str,
    _=Depends(require_admin),
):
    import asyncio
    from neo4j import AsyncGraphDatabase

    cypher = """
    MATCH (n)
    WHERE toLower(coalesce(n.title, '')) CONTAINS toLower($filename)
       OR toLower(coalesce(n.name,  '')) CONTAINS toLower($filename)
    WITH n LIMIT 5
    MATCH (n)-[r]-(m)
    RETURN
        coalesce(n.title, n.name) AS source,
        type(r)                   AS relationship_type,
        coalesce(m.title, m.name) AS target,
        m.id                      AS target_id,
        labels(m)[0]              AS target_label
    LIMIT 40
    """

    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    results = []
    try:
        async with driver.session() as session:
            records = await session.run(cypher, filename=filename)
            async for r in records:
                results.append(dict(r))
    finally:
        await driver.close()

    return {"related": results, "filename": filename}
