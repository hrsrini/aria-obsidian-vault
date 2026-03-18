"""
D6: Phase D verification — 5 compliance query tests.

Run: python tests/test_retrieval.py

Pass criteria: at least 4 of 5 queries return answers containing expected content.
All checks are case-insensitive substring matches.
"""

import asyncio
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from retrieval.aria_retrieval import aria_query

# ---------------------------------------------------------------------------
# Test definitions
# ---------------------------------------------------------------------------

TESTS = [
    {
        "id": "Q1",
        "question": (
            "What are the CET1 capital requirements under Basel III and "
            "how do they interact with the capital conservation buffer?"
        ),
        "must_contain": ["12 cfr", "4.5", "conservation buffer", "cet1"],
        "description": "Basel III CET1 + capital conservation buffer",
    },
    {
        "id": "Q2",
        "question": (
            "As a CRO at a bank approaching $10Bn in assets, what risk programs "
            "must I have in place?"
        ),
        "must_contain": ["dfast", "bsa", "10 b", "sr 12-7"],
        "description": "CRO obligations at $10Bn threshold",
    },
    {
        "id": "Q3",
        "question": "What does SR 16-11 supersede and what did it change?",
        "must_contain": ["sr 95-51", "16-11", "slhc"],
        "description": "SR 16-11 supersession chain",
    },
    {
        "id": "Q4",
        "question": "How does NC Chapter 53C interact with federal capital requirements?",
        "must_contain": ["53c", "nccob", "fdic", "dual"],
        "description": "NC state law vs federal capital reqs",
    },
    {
        "id": "Q5",
        "question": "What are the most common examiner findings in board governance?",
        "must_contain": ["sr 16-11", "board", "management", "mra"],
        "description": "Examiner findings — board governance",
    },
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def check_answer(answer: str, must_contain: list[str]) -> tuple[bool, list[str]]:
    """Return (passed, missing_terms)."""
    lower = answer.lower()
    missing = [term for term in must_contain if term.lower() not in lower]
    return len(missing) == 0, missing


async def run_tests():
    print("=" * 70)
    print("ARIA Phase D — Retrieval Engine Test Suite")
    print("=" * 70)

    passed = 0
    results = []

    for test in TESTS:
        print(f"\n{test['id']}: {test['description']}")
        print(f"Q: {test['question'][:90]}{'...' if len(test['question']) > 90 else ''}")

        start = time.time()
        try:
            answer = await aria_query(test["question"])
            elapsed = time.time() - start
            ok, missing = check_answer(answer, test["must_contain"])

            status = "PASS" if ok else "FAIL"
            if ok:
                passed += 1

            print(f"[{status}] ({elapsed:.1f}s)")
            if not ok:
                print(f"  Missing terms: {missing}")
                print(f"  Answer excerpt: {answer[:300]}...")
            else:
                print(f"  Answer excerpt: {answer[:200]}...")

            results.append({"id": test["id"], "status": status, "answer": answer})

        except Exception as e:
            elapsed = time.time() - start
            print(f"[ERROR] ({elapsed:.1f}s): {e}")
            results.append({"id": test["id"], "status": "ERROR", "answer": str(e)})

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"Results: {passed}/{len(TESTS)} PASS")
    for r in results:
        print(f"  {r['id']}: {r['status']}")

    if passed >= 4:
        print("\nPHASE D COMPLETE")
        return True
    else:
        print(f"\nTarget: 4/5 — got {passed}/5. Check vector store population and graph traversal.")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
