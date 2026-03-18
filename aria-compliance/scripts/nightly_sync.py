"""
Phase E — Nightly sync pipeline.
Runs the full update cycle: Obsidian -> Neo4j -> GraphRAG (incremental) -> Supabase.

Schedule: 0 2 * * * (2am UTC via Railway cron)
Run manually: python scripts/nightly_sync.py
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def run_step(label: str, cmd: list[str]) -> tuple[bool, str]:
    """Run a subprocess step and return (success, output)."""
    print(f"\n[{label}] Running: {' '.join(cmd)}")
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 min max per step
        )
        elapsed = time.time() - start
        output = (result.stdout + result.stderr).strip()
        if result.returncode == 0:
            print(f"[{label}] OK ({elapsed:.0f}s)")
            return True, output
        else:
            print(f"[{label}] FAILED (exit {result.returncode})\n{output}")
            return False, output
    except subprocess.TimeoutExpired:
        return False, f"{label} timed out after 30 minutes"
    except Exception as e:
        return False, str(e)


def count_input_files() -> int:
    input_dir = Path("input")
    if not input_dir.exists():
        return 0
    return len(list(input_dir.glob("**/*.txt")) + list(input_dir.glob("**/*.md")))


def log_to_supabase(summary: dict):
    """Write sync result to query_log for audit trail."""
    try:
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
        sb.table("query_log").insert({
            "question": "NIGHTLY_SYNC",
            "answer": json.dumps(summary),
            "graph_nodes_traversed": [],
            "vector_chunks_used": [],
        }).execute()
        print("\nSync result logged to Supabase query_log.")
    except Exception as e:
        print(f"\nWarning: could not log to Supabase: {e}")


def main():
    started_at = datetime.now(timezone.utc)
    print(f"ARIA Nightly Sync — {started_at.isoformat()}")
    print("=" * 60)

    steps = []

    # Step 1: Obsidian vault -> Neo4j
    ok, out = run_step("obsidian_to_graph", [sys.executable, "scripts/obsidian_to_graph.py"])
    steps.append({"step": "obsidian_to_graph", "ok": ok})

    # Step 2: GraphRAG incremental index (only if input/ has files)
    n_input = count_input_files()
    if n_input > 0:
        ok, out = run_step(
            "graphrag_index",
            ["python", "-m", "graphrag", "index", "--root", ".", "--resume"]
        )
        steps.append({"step": "graphrag_index", "ok": ok, "input_files": n_input})
    else:
        print("\n[graphrag_index] Skipped — no files in input/")
        steps.append({"step": "graphrag_index", "ok": True, "skipped": True})

    # Step 3: GraphRAG output -> Neo4j
    ok, out = run_step(
        "load_graphrag_to_neo4j",
        [sys.executable, "scripts/load_graphrag_to_neo4j.py"]
    )
    steps.append({"step": "load_graphrag_to_neo4j", "ok": ok})

    # Step 4: Obsidian vault -> Supabase embeddings
    ok, out = run_step(
        "embed_documents",
        [sys.executable, "ingestion/embed_documents.py", "--folder", "obsidian-vault/"]
    )
    steps.append({"step": "embed_documents", "ok": ok})

    # Summary
    finished_at = datetime.now(timezone.utc)
    elapsed_total = (finished_at - started_at).total_seconds()
    all_ok = all(s["ok"] for s in steps)

    summary = {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "elapsed_seconds": round(elapsed_total),
        "all_ok": all_ok,
        "steps": steps,
    }

    print("\n" + "=" * 60)
    print(f"Nightly sync {'COMPLETE' if all_ok else 'COMPLETED WITH ERRORS'}")
    print(f"Duration: {elapsed_total:.0f}s")
    for s in steps:
        status = "OK" if s["ok"] else "FAIL"
        skipped = " (skipped)" if s.get("skipped") else ""
        print(f"  {s['step']}: {status}{skipped}")

    log_to_supabase(summary)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
