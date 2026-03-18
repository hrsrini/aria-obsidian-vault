"""
build_registry.py
Scans documents/raw/ and generates registry.csv with one row per document.
doc_type is inferred from filename prefix: FED_ STATE_ FRAMEWORK_ GUIDANCE_
All other fields default to empty string — fill in manually after generation.
"""

import csv
import os
from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "documents" / "raw"
OUTPUT_CSV = Path(__file__).parent.parent / "documents" / "registry.csv"

PREFIX_TO_DOCTYPE = {
    "FED_": "federal_regulation",
    "STATE_": "state_statute",
    "FRAMEWORK_": "framework",
    "GUIDANCE_": "guidance",
}

COLUMNS = [
    "filename",
    "doc_type",
    "issuing_agency",
    "effective_date",
    "status",
    "bank_size",
    "roles",
]


def infer_doc_type(filename: str) -> str:
    for prefix, doc_type in PREFIX_TO_DOCTYPE.items():
        if filename.upper().startswith(prefix):
            return doc_type
    return "unknown"


def build_registry():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(
        f for f in RAW_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in {".pdf", ".md", ".txt", ".docx"}
    )

    rows = []
    for f in files:
        rows.append({
            "filename": f.name,
            "doc_type": infer_doc_type(f.name),
            "issuing_agency": "",
            "effective_date": "",
            "status": "active",
            "bank_size": "",
            "roles": "",
        })

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Registry written: {OUTPUT_CSV}")
    print(f"  {len(rows)} document(s) found in {RAW_DIR}")
    if not rows:
        print("  (No documents yet — add PDFs to documents/raw/ and re-run)")


if __name__ == "__main__":
    build_registry()
