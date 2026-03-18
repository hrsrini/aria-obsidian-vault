"""
Phase E: ARIA FastAPI application.

Endpoints:
    GET  /                  -> redirect to chat UI
    GET  /health            -> service liveness
    GET  /health/graph      -> Neo4j node count
    GET  /health/vector     -> Supabase document count
    POST /ask               -> compliance query
    POST /ask-voice         -> voice transcript query
    GET  /query-log         -> audit log browser
"""

import asyncio
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure repo root is on path when running from Railway
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from retrieval.aria_retrieval import aria_query, _get_supabase
from api.admin import documents as admin_documents
from api.admin import intake as admin_intake
from api.admin import health as admin_health
from api.admin import tests as admin_tests
from api.admin import corrections as admin_corrections
from api.admin import sync as admin_sync

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up Supabase client on startup
    _get_supabase()
    yield

app = FastAPI(
    title="ARIA Banking Compliance Intelligence",
    version="1.0.0",
    lifespan=lifespan,
)

# Admin routers
app.include_router(admin_documents.router)
app.include_router(admin_intake.router)
app.include_router(admin_health.router)
app.include_router(admin_tests.router)
app.include_router(admin_corrections.router)
app.include_router(admin_sync.router)

# CORS — restrict origins after testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000
    print(f"{request.method} {request.url.path} {response.status_code} {duration:.0f}ms")
    return response

# ---------------------------------------------------------------------------
# Static files + root redirect
# ---------------------------------------------------------------------------

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/static/index.html")

# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health/graph")
async def health_graph():
    try:
        import os
        from neo4j import AsyncGraphDatabase
        driver = AsyncGraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
        )
        async with driver.session() as session:
            result = await session.run("MATCH (n) RETURN count(n) AS nodes")
            record = await result.single()
            nodes = record["nodes"]
        await driver.close()
        return {"neo4j_nodes": nodes, "status": "ok"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"neo4j_nodes": 0, "status": "error", "detail": str(e)},
        )


@app.get("/health/vector")
async def health_vector():
    try:
        sb = _get_supabase()
        resp = await asyncio.to_thread(
            lambda: sb.table("documents").select("id", count="exact").execute()
        )
        count = resp.count or 0
        return {"document_chunks": count, "status": "ok"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"document_chunks": 0, "status": "error", "detail": str(e)},
        )

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str

class VoiceRequest(BaseModel):
    transcript: str

# ---------------------------------------------------------------------------
# /ask
# ---------------------------------------------------------------------------

@app.post("/ask")
async def ask(body: AskRequest):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    try:
        answer = await aria_query(body.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"aria_query failed: {e}")

    # Count citation markers (CFR, SR, §, Chapter references)
    import re
    citations = len(re.findall(
        r"(?:12 CFR|SR \d{2}-\d+|§\s*\d+|Chapter \d+|Part \d+)",
        answer, re.IGNORECASE
    ))

    query_id = str(uuid.uuid4())
    return {
        "answer": answer,
        "query_id": query_id,
        "sources_cited": citations,
    }


# ---------------------------------------------------------------------------
# /ask-voice
# ---------------------------------------------------------------------------

@app.post("/ask-voice")
async def ask_voice(body: VoiceRequest):
    if not body.transcript.strip():
        raise HTTPException(status_code=400, detail="transcript must not be empty")

    try:
        answer = await aria_query(body.transcript)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"aria_query failed: {e}")

    query_id = str(uuid.uuid4())
    return {
        "answer": answer,
        "query_id": query_id,
    }


# ---------------------------------------------------------------------------
# /query-log
# ---------------------------------------------------------------------------

@app.get("/query-log")
async def query_log(limit: int = 20, offset: int = 0):
    try:
        sb = _get_supabase()
        resp = await asyncio.to_thread(
            lambda: sb.table("query_log")
            .select("id, question, answer, created_at")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return {"queries": resp.data or [], "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
