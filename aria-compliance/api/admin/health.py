"""Admin — /admin/health/* routes."""
import asyncio
import os

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from .auth import require_admin
from retrieval.aria_retrieval import _get_supabase

router = APIRouter(prefix="/admin/health", tags=["admin-health"])


def sb():
    return _get_supabase()


@router.get("/stats")
async def health_stats(_=Depends(require_admin)):
    from neo4j import AsyncGraphDatabase

    # Neo4j counts
    neo4j_nodes = 0
    neo4j_rels = 0
    try:
        driver = AsyncGraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
        )
        async with driver.session() as session:
            r1 = await session.run("MATCH (n) RETURN count(n) AS c")
            rec = await r1.single()
            neo4j_nodes = rec["c"]
            r2 = await session.run("MATCH ()-[r]->() RETURN count(r) AS c")
            rec2 = await r2.single()
            neo4j_rels = rec2["c"]
        await driver.close()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    # corpus_docs = admin registry; documents = Phase D vector chunks table
    registry_count = sb().table("corpus_docs").select("id", count="exact").execute().count or 0
    vector_count   = sb().table("documents").select("id", count="exact").execute().count or 0
    coverage_pct   = round((vector_count / max(registry_count, 1)) * 100, 1)

    return {
        "neo4j_nodes":        neo4j_nodes,
        "neo4j_relationships": neo4j_rels,
        "vector_chunks":      vector_count,
        "documents_indexed":  registry_count,
        "embedding_coverage_pct": coverage_pct,
    }


@router.get("/coverage-gaps")
async def coverage_gaps(_=Depends(require_admin)):
    """Documents in registry but missing vector embeddings."""
    registry = sb().table("corpus_docs").select("id, filename, status").execute()
    embedded = sb().table("corpus_docs").select("source").execute()

    embedded_sources = {r["source"] for r in (embedded.data or [])}
    gaps = [
        d for d in (registry.data or [])
        if d["filename"] not in embedded_sources and d["status"] != "superseded"
    ]
    return {"gaps": gaps, "count": len(gaps)}


@router.get("/last-sync")
def last_sync(_=Depends(require_admin)):
    resp = sb().table("corpus_docs").select(
        "id, filename, status, last_synced_at, node_count, chunk_count"
    ).order("last_synced_at", desc=True).limit(50).execute()
    return {"documents": resp.data or []}
