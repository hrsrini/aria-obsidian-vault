"""Admin — /admin/test/* routes."""
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import require_admin
from retrieval.aria_retrieval import aria_query, vector_search, graph_search, fuse_context
from retrieval.aria_retrieval import _get_supabase

router = APIRouter(prefix="/admin/test", tags=["admin-tests"])


def sb():
    return _get_supabase()


# ── Ad-hoc query ──────────────────────────────────────────────────────────

class RunQueryBody(BaseModel):
    question: str
    role_filter: str = None
    bank_size_filter: str = None


@router.post("/run")
async def run_query(body: RunQueryBody, _=Depends(require_admin)):
    question = body.question
    if body.role_filter:
        question = f"[Role: {body.role_filter}] {question}"
    if body.bank_size_filter:
        question = f"[Bank size: {body.bank_size_filter}] {question}"

    vector_results, graph_results = await asyncio.gather(
        vector_search(question),
        graph_search(question),
    )
    context = fuse_context(vector_results, graph_results)
    answer = await aria_query(body.question)

    return {
        "answer": answer,
        "raw_context": {
            "vector_chunks": vector_results,
            "graph_nodes": graph_results[:10],
            "fused": context[:2000],
        },
    }


# ── Test library CRUD ─────────────────────────────────────────────────────

class TestCaseBody(BaseModel):
    question: str
    expected_answer: str
    category: str
    role_filter: str = None
    bank_size_filter: str = None
    created_by: str = "admin"


@router.get("/library")
def list_library(category: str = None, _=Depends(require_admin)):
    q = sb().table("test_cases").select("*").order("created_at", desc=True)
    if category:
        q = q.eq("category", category)
    resp = q.execute()
    return {"test_cases": resp.data or []}


@router.post("/library", status_code=201)
def create_test_case(body: TestCaseBody, _=Depends(require_admin)):
    resp = sb().table("test_cases").insert(body.model_dump()).execute()
    return resp.data[0]


@router.put("/library/{case_id}")
def update_test_case(case_id: str, body: TestCaseBody, _=Depends(require_admin)):
    resp = sb().table("test_cases").update(body.model_dump()).eq("id", case_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Test case not found")
    return resp.data[0]


@router.delete("/library/{case_id}", status_code=204)
def delete_test_case(case_id: str, _=Depends(require_admin)):
    sb().table("test_cases").delete().eq("id", case_id).execute()


# ── Run full library ──────────────────────────────────────────────────────

@router.post("/run-library")
async def run_library(_=Depends(require_admin)):
    cases_resp = sb().table("test_cases").select("*").execute()
    cases = cases_resp.data or []
    if not cases:
        return {"results": [], "pass_rate": 0, "total": 0}

    results = []
    passed = 0

    for case in cases:
        try:
            answer = await aria_query(case["question"])
            ok = case["expected_answer"].lower()[:80] in answer.lower()
            status = "pass" if ok else "fail"
            if ok:
                passed += 1

            # Update test case record
            sb().table("test_cases").update({
                "last_run_at":  datetime.now(timezone.utc).isoformat(),
                "last_result":  status,
                "last_actual":  answer[:500],
            }).eq("id", case["id"]).execute()

            results.append({"id": case["id"], "question": case["question"][:80], "result": status})
        except Exception as e:
            results.append({"id": case["id"], "question": case["question"][:80], "result": "error", "error": str(e)})

    pass_rate = round(passed / len(cases) * 100, 1)
    return {"results": results, "passed": passed, "total": len(cases), "pass_rate": pass_rate}


# ── Regression history ────────────────────────────────────────────────────

@router.get("/regression-history")
def regression_history(_=Depends(require_admin)):
    # Summarise last_result distribution from test_cases
    resp = sb().table("test_cases").select("last_result, last_run_at, category").execute()
    data = resp.data or []

    pass_count  = sum(1 for r in data if r["last_result"] == "pass")
    fail_count  = sum(1 for r in data if r["last_result"] == "fail")
    total = len(data)
    pass_rate = round(pass_count / max(total, 1) * 100, 1)

    return {
        "pass_count":  pass_count,
        "fail_count":  fail_count,
        "not_run":     sum(1 for r in data if r["last_result"] == "not_run"),
        "total":       total,
        "pass_rate":   pass_rate,
    }
