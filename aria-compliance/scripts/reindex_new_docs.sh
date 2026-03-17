#!/bin/bash
# reindex_new_docs.sh
# Run this whenever new documents or Obsidian notes are added to ARIA.
# Performs an incremental index — only processes new/changed files.
#
# Usage:
#   chmod +x scripts/reindex_new_docs.sh
#   ./scripts/reindex_new_docs.sh

set -e
cd "$(dirname "$0")/.."

echo "ARIA Incremental Reindex"
echo "========================"

# Step 1: Copy new Obsidian notes to input/
echo "[1/4] Syncing Obsidian notes to input/..."
find obsidian-vault -name "*.md" ! -path "*/_templates/*" -exec cp {} input/ \;

# Step 2: Convert any new PDFs to text and copy to input/
echo "[2/4] Converting new PDFs..."
for pdf in documents/raw/*.pdf; do
  [ -f "$pdf" ] || continue
  base=$(basename "$pdf" .pdf)
  if [ ! -f "input/${base}.txt" ]; then
    python - <<PYEOF
import pymupdf, sys
from pathlib import Path
doc = pymupdf.open("$pdf")
text = "\n\n".join(page.get_text() for page in doc)
Path("input/${base}.txt").write_text(text, encoding='utf-8')
print(f"  Converted: $pdf -> input/${base}.txt")
PYEOF
  fi
done

# Step 3: Incremental GraphRAG index (only processes new/changed files)
echo "[3/4] Running incremental GraphRAG index..."
python -m graphrag index --root . --resume

# Step 4: Reload graph into Neo4j
echo "[4/4] Reloading graph into Neo4j..."
python scripts/load_graphrag_to_neo4j.py
python scripts/obsidian_to_graph.py

echo ""
echo "Incremental index complete"
