"""
D4: ARIA hybrid retrieval engine.

Core public API:
    aria_query(question: str) -> str

Architecture:
    1. vector_search  — embed question with voyage-3, query Supabase match_documents
    2. graph_search   — extract entities with Claude Haiku, traverse Neo4j ≤3 hops
    3. fuse_context   — deduplicate and format both result sets
    4. Generate       — Claude Sonnet with ARIA system prompt + fused context
    5. log_query      — audit row in Supabase query_log
"""

import asyncio
import hashlib
import json
import os
from typing import Any

import anthropic
import voyageai
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase
from supabase import create_client, Client as SupabaseClient

load_dotenv()

# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------
NEO4J_URI      = os.environ["NEO4J_URI"]
NEO4J_USER     = os.environ["NEO4J_USER"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
SUPABASE_URL   = os.environ["SUPABASE_URL"]
SUPABASE_KEY   = os.environ["SUPABASE_SERVICE_KEY"]
VOYAGE_API_KEY = os.environ["VOYAGE_API_KEY"]

# ---------------------------------------------------------------------------
# Client singletons (module-level, re-used across calls)
# ---------------------------------------------------------------------------
_anthropic: anthropic.AsyncAnthropic | None = None
_voyage:    voyageai.AsyncClient | None     = None
_supabase:  SupabaseClient | None           = None


def _get_anthropic() -> anthropic.AsyncAnthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = anthropic.AsyncAnthropic()
    return _anthropic


def _get_voyage() -> voyageai.AsyncClient:
    global _voyage
    if _voyage is None:
        _voyage = voyageai.AsyncClient(api_key=VOYAGE_API_KEY)
    return _voyage


def _get_supabase() -> SupabaseClient:
    global _supabase
    if _supabase is None:
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


# ---------------------------------------------------------------------------
# ARIA system prompt
# ---------------------------------------------------------------------------
ARIA_SYSTEM_PROMPT = """
You are ARIA — an expert US banking compliance advisor with 20 years of experience.
You have deep knowledge of federal banking regulations, state banking statutes
(including NC Chapter 53C), ERM frameworks, and role-specific obligations.

When answering:
1. Cite the specific CFR citation, SR Letter, or statute section that governs the answer.
2. Note bank size applicability — which requirements apply at which asset thresholds
   ($1Bn, $3Bn, $10Bn, $50Bn, $100Bn, $250Bn).
3. Distinguish role-specific obligations (Board vs CRO vs CISO vs CFO).
4. Flag when a guidance document supersedes an earlier one and what changed.
5. Give practical implementation guidance, not just regulatory text.
6. Warn about common examiner focus areas and MRA (Matter Requiring Attention) triggers.
7. If context is insufficient, say so clearly rather than speculating.

Format: structured response with clear headers where appropriate.
Always ground your answer in the regulatory context provided below.
""".strip()


# ---------------------------------------------------------------------------
# D4a: Vector search
# ---------------------------------------------------------------------------

async def vector_search(question: str, top_k: int = 8) -> list[dict[str, Any]]:
    """
    Embed question with voyage-3 and query Supabase match_documents RPC.
    Returns list of {content, source, similarity}.
    """
    voyage = _get_voyage()
    result = await voyage.embed([question], model="voyage-3", input_type="query")
    embedding: list[float] = result.embeddings[0]

    supabase = _get_supabase()
    # Supabase Python client is sync — run in thread to avoid blocking event loop
    response = await asyncio.to_thread(
        lambda: supabase.rpc(
            "match_documents",
            {"query_embedding": embedding, "match_count": top_k}
        ).execute()
    )

    return response.data or []


# ---------------------------------------------------------------------------
# D4b: Graph search
# ---------------------------------------------------------------------------

ENTITY_EXTRACTION_PROMPT = """
Extract banking regulatory entities from this compliance question.
Return ONLY a JSON array of strings — entity names, regulation IDs, SR letter numbers,
CFR citations, or key banking terms. Maximum 6 entities.

Example output: ["SR 16-11", "DFAST", "$10 billion threshold", "CRO"]

Question: {question}
""".strip()


async def graph_search(question: str, hops: int = 3) -> list[dict[str, Any]]:
    """
    1. Use Claude Haiku to extract banking entities from the question.
    2. Traverse Neo4j up to `hops` deep from those entities.
    Returns list of node/relationship dicts.
    """
    # Step 1: Entity extraction via Claude Haiku
    client = _get_anthropic()
    haiku_response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": ENTITY_EXTRACTION_PROMPT.format(question=question)
        }]
    )

    raw = haiku_response.content[0].text.strip()
    try:
        # Extract JSON array even if wrapped in markdown code fence
        json_match = raw
        if "```" in raw:
            json_match = raw.split("```")[1].strip().lstrip("json").strip()
        entities: list[str] = json.loads(json_match)
        if not isinstance(entities, list):
            entities = []
    except (json.JSONDecodeError, IndexError):
        entities = []

    if not entities:
        return []

    # Step 2: Neo4j traversal
    cypher = """
    MATCH (n)
    WHERE any(e IN $entities WHERE
        toLower(coalesce(n.title, '')) CONTAINS toLower(e) OR
        toLower(coalesce(n.name,  '')) CONTAINS toLower(e) OR
        toLower(coalesce(n.id,    '')) CONTAINS toLower(e)
    )
    WITH n LIMIT 10
    MATCH path = (n)-[r*1..{hops}]-(m)
    RETURN
        n.title AS start_node,
        n.name  AS start_name,
        type(last(relationships(path))) AS rel_type,
        m.title AS end_node,
        m.name  AS end_name,
        labels(m)[0] AS end_label,
        m.description AS end_description
    LIMIT 60
    """.format(hops=hops)

    driver = AsyncGraphDatabase.driver(
        NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
    )
    results: list[dict] = []
    try:
        async with driver.session() as session:
            records = await session.run(cypher, entities=entities)
            async for record in records:
                results.append(dict(record))
    finally:
        await driver.close()

    return results


# ---------------------------------------------------------------------------
# D4c: Context fusion
# ---------------------------------------------------------------------------

def fuse_context(
    vector_results: list[dict[str, Any]],
    graph_results:  list[dict[str, Any]]
) -> str:
    """
    Deduplicate vector results and cap graph results.
    Returns a formatted string with two labelled sections.
    """
    # Deduplicate vector results by content hash
    seen: set[str] = set()
    unique_vector: list[dict] = []
    for r in vector_results:
        h = hashlib.md5(r.get("content", "").encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique_vector.append(r)

    # Cap graph results
    capped_graph = graph_results[:15]

    lines: list[str] = []

    # --- Vector section ---
    lines.append("=== RELEVANT REGULATORY TEXT ===")
    if unique_vector:
        for i, r in enumerate(unique_vector, 1):
            source = r.get("source", "unknown")
            sim    = r.get("similarity", 0)
            content = r.get("content", "").strip()
            lines.append(f"\n[{i}] Source: {source} (similarity: {sim:.3f})")
            lines.append(content)
    else:
        lines.append("No matching regulatory text found.")

    # --- Graph section ---
    lines.append("\n=== REGULATORY RELATIONSHIPS (GRAPH) ===")
    if capped_graph:
        for r in capped_graph:
            start = r.get("start_node") or r.get("start_name") or "?"
            end   = r.get("end_node")   or r.get("end_name")   or "?"
            rel   = r.get("rel_type", "RELATES_TO")
            desc  = r.get("end_description") or ""
            line  = f"  {start}  --[{rel}]-->  {end}"
            if desc:
                line += f"  |  {desc[:120]}"
            lines.append(line)
    else:
        lines.append("No graph relationships found.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# D4d: Query log
# ---------------------------------------------------------------------------

def log_query(
    question:              str,
    answer:                str,
    graph_nodes_traversed: list[dict],
    vector_chunks_used:    list[dict],
    supabase_client:       SupabaseClient,
) -> None:
    """Insert an audit row into query_log. Silently swallows errors."""
    try:
        supabase_client.table("query_log").insert({
            "question":              question,
            "answer":                answer,
            "graph_nodes_traversed": graph_nodes_traversed[:15],
            "vector_chunks_used":    [
                {"source": r.get("source"), "similarity": r.get("similarity")}
                for r in vector_chunks_used
            ],
        }).execute()
    except Exception as e:
        print(f"[log_query warning] Could not write audit log: {e}")


# ---------------------------------------------------------------------------
# D4e: Main query function
# ---------------------------------------------------------------------------

async def aria_query(question: str) -> str:
    """
    Parallel hybrid retrieval + Claude Sonnet generation.
    This is the core public API of the entire system.
    """
    # Run vector and graph search in parallel
    vector_results, graph_results = await asyncio.gather(
        vector_search(question),
        graph_search(question),
    )

    context = fuse_context(vector_results, graph_results)

    client = _get_anthropic()
    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=ARIA_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"REGULATORY CONTEXT:\n{context}\n\n"
                    f"COMPLIANCE QUESTION:\n{question}"
                )
            }
        ]
    )

    answer = message.content[0].text.strip()

    # Async-safe logging (don't block the response)
    asyncio.create_task(
        asyncio.to_thread(
            log_query,
            question,
            answer,
            graph_results,
            vector_results,
            _get_supabase(),
        )
    )

    return answer


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

async def _cli(question: str):
    print(f"\nQuestion: {question}\n")
    print("-" * 60)
    answer = await aria_query(question)
    print(answer)
    print("-" * 60)


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What is SR 16-11?"
    asyncio.run(_cli(q))
