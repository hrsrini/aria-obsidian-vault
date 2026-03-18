"""
obsidian_to_graph.py
Syncs the Obsidian vault to Neo4j AuraDB.

For each .md file:
  - Parses YAML frontmatter -> Neo4j node properties
  - Extracts [[wikilinks]] -> REFERENCES edges
  - MERGEs nodes and edges (idempotent, safe to re-run)
  - Creates stub nodes for [[link]] targets that have no note yet

Usage:
  python scripts/obsidian_to_graph.py

Credentials loaded from aria-compliance/.env
"""

import os
import re
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from neo4j import GraphDatabase

# ── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
VAULT_DIR = BASE_DIR / "obsidian-vault"
ENV_FILE = BASE_DIR / ".env"

# ── Load credentials ─────────────────────────────────────────────────────────

load_dotenv(dotenv_path=ENV_FILE)

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ["NEO4J_USER"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

# ── Regex ─────────────────────────────────────────────────────────────────────

WIKILINK_RE = re.compile(r'\[\[([^\]|#]+?)(?:\|[^\]]*)?\]\]')
FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_note(path: Path) -> tuple[dict, list[str]]:
    """Return (frontmatter_dict, [wikilink_targets]) for a note file."""
    text = path.read_text(encoding="utf-8")

    frontmatter = {}
    match = FRONTMATTER_RE.match(text)
    if match:
        try:
            frontmatter = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as e:
            print(f"  WARN: YAML parse error in {path.name}: {e}")

    links = WIKILINK_RE.findall(text)
    # Normalise link targets to the same slug format as note stems
    links = [slugify(l) for l in links]

    return frontmatter, links


def slugify(name: str) -> str:
    """Normalise a note stem or wikilink target to a consistent id."""
    return name.strip().replace(" ", "-")


def note_stem(path: Path) -> str:
    return slugify(path.stem)


def sanitise_props(props: dict) -> dict:
    """Flatten list values to strings so Neo4j accepts them cleanly."""
    clean = {}
    for k, v in props.items():
        if v is None:
            continue
        if isinstance(v, list):
            clean[k] = [str(i) for i in v]
        elif isinstance(v, (str, int, float, bool)):
            clean[k] = v
        else:
            clean[k] = str(v)
    return clean


# ── Neo4j queries ─────────────────────────────────────────────────────────────

MERGE_NODE_QUERY = """
MERGE (n:ComplianceNote {id: $id})
SET n += $props
SET n.stub = false
RETURN n
"""

MERGE_STUB_QUERY = """
MERGE (n:ComplianceNote {id: $id})
ON CREATE SET n.stub = true, n.id = $id
RETURN n
"""

MERGE_EDGE_QUERY = """
MATCH (a:ComplianceNote {id: $source})
MATCH (b:ComplianceNote {id: $target})
MERGE (a)-[:REFERENCES]->(b)
"""


# ── Main ──────────────────────────────────────────────────────────────────────

def run_sync():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    notes_processed = 0
    nodes_upserted = 0
    edges_created = 0
    stubs_created = 0

    # Collect all note stems first so we know what exists
    note_files = [
        p for p in VAULT_DIR.rglob("*.md")
        if "_templates" not in str(p)
    ]

    known_stems = {note_stem(p) for p in note_files}
    all_link_targets: dict[str, list[str]] = {}

    print(f"\nARIA Obsidian -> Neo4j Sync")
    print(f"Vault: {VAULT_DIR}")
    print(f"Found {len(note_files)} note(s) to process\n")

    with driver.session() as session:

        # Pass 1: upsert all real nodes
        for path in note_files:
            stem = note_stem(path)
            frontmatter, links = parse_note(path)
            all_link_targets[stem] = links

            props = sanitise_props(frontmatter)
            props["source_file"] = str(path.relative_to(BASE_DIR))
            props["note_name"] = path.stem

            session.run(MERGE_NODE_QUERY, id=stem, props=props)
            nodes_upserted += 1
            notes_processed += 1
            print(f"  [node]  {stem}")

        # Pass 2: create stub nodes for unknown link targets
        all_targets = {t for links in all_link_targets.values() for t in links}
        unknown_targets = all_targets - known_stems

        for target in sorted(unknown_targets):
            session.run(MERGE_STUB_QUERY, id=target)
            stubs_created += 1
            print(f"  [stub]  {target}")

        # Pass 3: create REFERENCES edges
        for source, links in all_link_targets.items():
            for target in links:
                session.run(MERGE_EDGE_QUERY, source=source, target=target)
                edges_created += 1

    driver.close()

    print(f"""
Sync complete
  Notes processed : {notes_processed}
  Nodes upserted  : {nodes_upserted}
  Stub nodes      : {stubs_created}
  REFERENCES edges: {edges_created}
""")


if __name__ == "__main__":
    try:
        run_sync()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)
