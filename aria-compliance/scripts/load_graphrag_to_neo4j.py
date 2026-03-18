"""
load_graphrag_to_neo4j.py
Loads GraphRAG parquet output into Neo4j AuraDB.

Reads:
  graphrag-output/output/create_final_entities.parquet
  graphrag-output/output/create_final_relationships.parquet
  graphrag-output/output/create_final_community_reports.parquet

MERGEs all data idempotently — safe to re-run.

Usage:
  python scripts/load_graphrag_to_neo4j.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent
OUTPUT_DIR  = BASE_DIR / "graphrag-output" / "output"
ENV_FILE    = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE)
NEO4J_URI      = os.environ["NEO4J_URI"]
NEO4J_USER     = os.environ["NEO4J_USER"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

# ── Cypher queries ─────────────────────────────────────────────────────────────

MERGE_ENTITY = """
MERGE (e:GraphRAGEntity {id: $id})
SET e.uuid        = $uuid,
    e.name        = $name,
    e.type        = $type,
    e.description = $description
"""

MERGE_RELATIONSHIP = """
MATCH (a:GraphRAGEntity {id: $src_id})
MATCH (b:GraphRAGEntity {id: $tgt_id})
MERGE (a)-[r:RELATES_TO {type: $rel_type}]->(b)
SET r.description = $description
"""

MERGE_COMMUNITY = """
MERGE (c:CommunityNode {id: $id})
SET c.title   = $title,
    c.summary = $summary,
    c.rank     = $rank
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def safe_str(val, max_len=2000):
    if pd.isna(val):
        return ""
    return str(val)[:max_len]


def find_parquet(name):
    """Find a parquet file by partial name match under OUTPUT_DIR."""
    candidates = list(OUTPUT_DIR.rglob(f"*{name}*"))
    if not candidates:
        return None
    return candidates[0]


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_entities(session):
    path = find_parquet("entities")
    if not path:
        print("  WARN: create_final_entities.parquet not found — skipping")
        return 0
    df = pd.read_parquet(path)
    print(f"  Entities parquet: {len(df)} rows, columns: {list(df.columns)}")
    count = 0
    for _, row in df.iterrows():
        uuid  = safe_str(row.get("id", ""))
        name  = safe_str(row.get("title", row.get("name", "")))
        etype = safe_str(row.get("type", ""))
        desc  = safe_str(row.get("description", ""))
        # Use title as the merge key so relationships can find nodes by name
        node_id = name if name else uuid
        if not node_id:
            continue
        session.run(MERGE_ENTITY, id=node_id, uuid=uuid, name=name,
                    type=etype, description=desc)
        count += 1
    return count


def load_relationships(session):
    path = find_parquet("relationships")
    if not path:
        print("  WARN: create_final_relationships.parquet not found — skipping")
        return 0
    df = pd.read_parquet(path)
    print(f"  Relationships parquet: {len(df)} rows, columns: {list(df.columns)}")
    count = 0
    for _, row in df.iterrows():
        src  = safe_str(row.get("source", ""))
        tgt  = safe_str(row.get("target", ""))
        rtype= safe_str(row.get("type", row.get("relationship_type", "RELATES_TO")))
        desc = safe_str(row.get("description", ""))
        if not src or not tgt:
            continue
        try:
            session.run(MERGE_RELATIONSHIP, src_id=src, tgt_id=tgt,
                        rel_type=rtype, description=desc)
            count += 1
        except Exception:
            pass  # Skip if source/target nodes don't exist yet
    return count


def load_communities(session):
    path = find_parquet("community_reports")
    if not path:
        print("  WARN: create_final_community_reports.parquet not found — skipping")
        return 0
    df = pd.read_parquet(path)
    print(f"  Communities parquet: {len(df)} rows, columns: {list(df.columns)}")
    count = 0
    for _, row in df.iterrows():
        cid     = safe_str(row.get("id", row.get("community", "")))
        title   = safe_str(row.get("title", ""))
        summary = safe_str(row.get("summary", ""), max_len=4000)
        rank    = float(row.get("rank", 0) or 0)
        if not cid:
            continue
        session.run(MERGE_COMMUNITY, id=cid, title=title, summary=summary, rank=rank)
        count += 1
    return count


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    if not OUTPUT_DIR.exists():
        print(f"ERROR: output directory not found: {OUTPUT_DIR}")
        print("Run GraphRAG indexing first: python -m graphrag index --root .")
        sys.exit(1)

    print(f"\nARIA Graph Load — GraphRAG -> Neo4j")
    print(f"Output dir: {OUTPUT_DIR}\n")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        print("Loading entities...")
        entities = load_entities(session)

        print("Loading relationships...")
        relationships = load_relationships(session)

        print("Loading community reports...")
        communities = load_communities(session)

    driver.close()

    print(f"""
Load complete
  Entities loaded     : {entities}
  Relationships loaded: {relationships}
  Communities loaded  : {communities}
""")


if __name__ == "__main__":
    run()
