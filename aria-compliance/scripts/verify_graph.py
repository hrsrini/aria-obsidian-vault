"""
verify_graph.py
Runs 5 verification Cypher queries against Neo4j AuraDB.
Prints PASS/FAIL for each. All 5 must pass before Phase C is complete.

Usage:
  python scripts/verify_graph.py
"""

import os, sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

driver = GraphDatabase.driver(
    os.environ["NEO4J_URI"],
    auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])
)

results = []

def check(label, query, evaluate_fn, hint=""):
    with driver.session() as s:
        data = s.run(query).data()
    passed, detail = evaluate_fn(data)
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}]  {label}")
    if detail:
        print(f"         {detail}")
    if not passed and hint:
        print(f"         Hint: {hint}")
    results.append(passed)

print("\n=== ARIA Graph Verification ===\n")

# ── Query 1: Total node count > 50 ────────────────────────────────────────────
check(
    label="Q1 — Total node count > 50",
    query="MATCH (n) RETURN count(n) AS total_nodes",
    evaluate_fn=lambda d: (
        d[0]["total_nodes"] > 50,
        f"total_nodes = {d[0]['total_nodes']}"
    ),
    hint="Run GraphRAG indexing and load_graphrag_to_neo4j.py first"
)

# ── Query 2: Total relationship count > 100 ───────────────────────────────────
check(
    label="Q2 — Total relationship count > 100",
    query="MATCH ()-[r]->() RETURN count(r) AS total_relationships",
    evaluate_fn=lambda d: (
        d[0]["total_relationships"] > 100,
        f"total_relationships = {d[0]['total_relationships']}"
    ),
    hint="Run GraphRAG indexing and load_graphrag_to_neo4j.py first"
)

# ── Query 3: At least 3 Regulation entities ───────────────────────────────────
check(
    label="Q3 — At least 3 Regulation entities",
    query="MATCH (n) WHERE n.type = 'Regulation' OR n.type = 'REGULATION' RETURN n.name AS name LIMIT 10",
    evaluate_fn=lambda d: (
        len(d) >= 3,
        f"found {len(d)} Regulation nodes: {[r['name'] for r in d[:5]]}"
    ),
    hint="GraphRAG entity_types must include 'Regulation'"
)

# ── Query 4: SR-16-11 has outgoing relationships ──────────────────────────────
check(
    label="Q4 — SR-16-11 node has outgoing relationships",
    query="""
        MATCH (a)-[r]->(b)
        WHERE a.id CONTAINS 'SR-16-11' OR a.name CONTAINS 'SR 16-11'
              OR a.id CONTAINS 'SR-16-11'
        RETURN a.id AS src, type(r) AS rel, b.id AS tgt
        LIMIT 10
    """,
    evaluate_fn=lambda d: (
        len(d) >= 1,
        f"found {len(d)} relationships from SR-16-11: "
        + str([(r['src'], r['rel'], r['tgt']) for r in d[:3]])
    ),
    hint="Check obsidian_to_graph.py ran and SR-16-11 note has wikilinks"
)

# ── Query 5: 10Bn threshold node has outgoing relationships ───────────────────
check(
    label="Q5 — $10Bn threshold node has >= 2 relationships",
    query="""
        MATCH (t)-[r]->(n)
        WHERE t.id CONTAINS '10Bn' OR t.name CONTAINS '10Bn'
              OR t.id CONTAINS '10bn' OR t.name CONTAINS '10 billion'
        RETURN t.id AS src, type(r) AS rel, n.id AS tgt
        LIMIT 10
    """,
    evaluate_fn=lambda d: (
        len(d) >= 2,
        f"found {len(d)} relationships from 10Bn threshold: "
        + str([(r['src'], r['rel'], r['tgt']) for r in d[:3]])
    ),
    hint="Check obsidian_to_graph.py ran and 10Bn-Threshold note has wikilinks"
)

driver.close()

print()
passed = sum(results)
total  = len(results)
print(f"Results: {passed}/{total} passed")
print()
if passed == total:
    print("PHASE C COMPLETE")
else:
    print(f"ACTION NEEDED — {total - passed} check(s) failed. Diagnose above.")
