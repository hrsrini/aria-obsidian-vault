"""
Phase E — ARIA 20-question evaluation framework.

Run: python tests/evaluate.py

Categories (5 questions each):
  1. Simple Citation Lookup
  2. Threshold Cluster
  3. Role Obligations
  4. State-Federal Interaction

Target: 17/20 overall, 4/5 per category.
"""

import asyncio
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from retrieval.aria_retrieval import aria_query

# ---------------------------------------------------------------------------
# Evaluation set
# ---------------------------------------------------------------------------

EVAL_SET = [
    # ── Category 1: Simple Citation Lookup ──────────────────────────────────
    {
        "category": "Citation Lookup",
        "question": "What is the minimum CET1 capital ratio requirement under Basel III?",
        "must_contain": ["4.5", "cet1", "basel"],
    },
    {
        "category": "Citation Lookup",
        "question": "What does SR 16-11 govern and who does it apply to?",
        "must_contain": ["risk management", "100 billion", "federal reserve"],
    },
    {
        "category": "Citation Lookup",
        "question": "What CFR part governs capital adequacy for national banks?",
        "must_contain": ["12 cfr", "part 3", "occ"],
    },
    {
        "category": "Citation Lookup",
        "question": "What is the leverage ratio requirement under Basel III?",
        "must_contain": ["leverage", "tier 1", "4%"],
    },
    {
        "category": "Citation Lookup",
        "question": "What is the purpose of SR 12-7 and what does it cover?",
        "must_contain": ["model risk", "validation", "sr 11-7"],
    },

    # ── Category 2: Threshold Cluster ───────────────────────────────────────
    {
        "category": "Threshold Cluster",
        "question": "What regulations activate when a bank crosses $10 billion in total assets?",
        "must_contain": ["dfast", "cfpb", "10"],
    },
    {
        "category": "Threshold Cluster",
        "question": "At what asset size does CCAR stress testing become mandatory?",
        "must_contain": ["100", "ccar", "federal reserve"],
    },
    {
        "category": "Threshold Cluster",
        "question": "What capital buffer requirements apply above the 4.5% CET1 minimum?",
        "must_contain": ["conservation buffer", "2.5", "capital"],
    },
    {
        "category": "Threshold Cluster",
        "question": "What BSA/AML requirements change when a bank reaches $1 billion in assets?",
        "must_contain": ["bsa", "aml", "1 billion"],
    },
    {
        "category": "Threshold Cluster",
        "question": "What enhanced prudential standards apply to banks with over $50 billion in assets?",
        "must_contain": ["50 billion", "enhanced", "prudential"],
    },

    # ── Category 3: Role Obligations ────────────────────────────────────────
    {
        "category": "Role Obligations",
        "question": "What are the specific risk management obligations of the CRO under SR 16-11?",
        "must_contain": ["cro", "risk appetite", "three lines"],
    },
    {
        "category": "Role Obligations",
        "question": "What does the Board own versus senior management under SR 16-11?",
        "must_contain": ["board", "oversight", "management"],
    },
    {
        "category": "Role Obligations",
        "question": "What are the CISO's obligations under federal banking cybersecurity guidance?",
        "must_contain": ["ciso", "information security", "risk"],
    },
    {
        "category": "Role Obligations",
        "question": "What is the role of internal audit under the three lines of defense model?",
        "must_contain": ["internal audit", "third line", "independent"],
    },
    {
        "category": "Role Obligations",
        "question": "What must the CFO certify or attest to under Sarbanes-Oxley for bank holding companies?",
        "must_contain": ["cfo", "financial", "internal control"],
    },

    # ── Category 4: State-Federal Interaction ───────────────────────────────
    {
        "category": "State-Federal Interaction",
        "question": "How does NC Chapter 53C define capital requirements for state-chartered banks?",
        "must_contain": ["53c", "fdic", "federal"],
    },
    {
        "category": "State-Federal Interaction",
        "question": "What authority does the NC Commissioner of Banks have under Chapter 53C?",
        "must_contain": ["commissioner", "examination", "nccob"],
    },
    {
        "category": "State-Federal Interaction",
        "question": "How does NC Chapter 53C interact with federal BSA/AML requirements?",
        "must_contain": ["53c", "bsa", "federal"],
    },
    {
        "category": "State-Federal Interaction",
        "question": "Which federal regulator oversees a North Carolina state-chartered bank that is FDIC-insured?",
        "must_contain": ["fdic", "state", "federal"],
    },
    {
        "category": "State-Federal Interaction",
        "question": "What happens when NC state capital requirements conflict with federal minimums?",
        "must_contain": ["federal", "preempt", "minimum"],
    },
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def check(answer: str, must_contain: list[str]) -> tuple[bool, list[str]]:
    low = answer.lower()
    missing = [t for t in must_contain if t.lower() not in low]
    return len(missing) == 0, missing


async def run_evaluation():
    print("=" * 70)
    print("ARIA Evaluation Framework — 20 Questions")
    print("=" * 70)

    categories: dict[str, list[bool]] = {}
    total_pass = 0

    for i, item in enumerate(EVAL_SET, 1):
        cat = item["category"]
        q = item["question"]
        print(f"\nQ{i:02d} [{cat}]")
        print(f"     {q[:85]}{'...' if len(q) > 85 else ''}")

        start = time.time()
        try:
            answer = await aria_query(q)
            elapsed = time.time() - start
            ok, missing = check(answer, item["must_contain"])
            status = "PASS" if ok else "FAIL"
            print(f"     [{status}] {elapsed:.0f}s", end="")
            if not ok:
                print(f" — missing: {missing}", end="")
            print()
        except Exception as e:
            ok = False
            print(f"     [ERROR] {e}")

        categories.setdefault(cat, []).append(ok)
        if ok:
            total_pass += 1

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("RESULTS BY CATEGORY")
    print("=" * 70)
    for cat, results in categories.items():
        score = sum(results)
        bar = "".join("P" if r else "F" for r in results)
        status = "OK" if score >= 4 else "BELOW TARGET"
        print(f"  {cat:<30} {score}/5  [{bar}]  {status}")

    print(f"\nOVERALL: {total_pass}/20")

    if total_pass >= 17:
        print("\nEVALUATION PASSED — Target 17/20 met")
        return True
    else:
        print(f"\nEVALUATION BELOW TARGET — got {total_pass}/20, need 17")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_evaluation())
    sys.exit(0 if success else 1)
