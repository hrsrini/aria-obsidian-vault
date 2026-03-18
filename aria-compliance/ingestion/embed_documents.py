"""
D2: Embedding pipeline — chunk documents and upsert to Supabase pgvector.

Usage:
    python ingestion/embed_documents.py                          # default: obsidian-vault/
    python ingestion/embed_documents.py --folder documents/processed/
    python ingestion/embed_documents.py --folder obsidian-vault/ --dry-run

Embedding model : voyage-3 (1024-dim) via Voyage AI
Vector store    : Supabase pgvector (documents table)
Dedup strategy  : SHA-256 hash of (source, content) — skips existing chunks
"""

import argparse
import hashlib
import os
import re
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
VOYAGE_API_KEY = os.environ["VOYAGE_API_KEY"]

# Approximate token budget per chunk (1 token ≈ 4 chars in English)
MAX_TOKENS = 600
CHARS_PER_TOKEN = 4
MAX_CHARS = MAX_TOKENS * CHARS_PER_TOKEN  # 2400 chars

# Overlap carried forward into next chunk (last N chars of previous chunk)
OVERLAP_CHARS = 50 * CHARS_PER_TOKEN  # ~50 tokens


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

def parse_md_file(path: Path) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text) for a .md file."""
    raw = path.read_text(encoding="utf-8")
    frontmatter: dict = {}
    body = raw

    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                frontmatter = {}
            body = parts[2].strip()

    return frontmatter, body


# ---------------------------------------------------------------------------
# Sentence-boundary chunker
# ---------------------------------------------------------------------------

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str) -> list[str]:
    """Split text into chunks ≤ MAX_CHARS at sentence boundaries with overlap."""
    # Split into sentences
    sentences = SENTENCE_END.split(text)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    overlap_tail = ""

    for sentence in sentences:
        slen = len(sentence)

        if current_len + slen > MAX_CHARS and current:
            chunk = (overlap_tail + " " + " ".join(current)).strip()
            chunks.append(chunk)
            # carry forward last portion as overlap
            overlap_tail = " ".join(current)[-OVERLAP_CHARS:]
            current = []
            current_len = 0

        current.append(sentence)
        current_len += slen + 1  # +1 for space

    if current:
        chunk = (overlap_tail + " " + " ".join(current)).strip()
        chunks.append(chunk)

    return [c for c in chunks if len(c) > 50]  # discard trivially short chunks


# ---------------------------------------------------------------------------
# Embedding with exponential backoff
# ---------------------------------------------------------------------------

def embed_batch(texts: list[str], voyage_client) -> list[list[float]]:
    """Embed a batch of texts using voyage-3 with exponential backoff."""
    max_retries = 5
    delay = 1.0

    for attempt in range(max_retries):
        try:
            result = voyage_client.embed(texts, model="voyage-3", input_type="document")
            return result.embeddings
        except Exception as e:
            err = str(e).lower()
            if "rate" in err or "429" in err or "too many" in err:
                if attempt < max_retries - 1:
                    print(f"  Rate limit hit, waiting {delay:.0f}s...")
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
                else:
                    raise
            else:
                raise

    raise RuntimeError("Embedding failed after max retries")


# ---------------------------------------------------------------------------
# Dedup check
# ---------------------------------------------------------------------------

def content_hash(source: str, text: str) -> str:
    return hashlib.sha256(f"{source}:{text}".encode()).hexdigest()


def already_embedded(supabase_client, hashes: list[str]) -> set[str]:
    """Return set of content_hashes already in the documents table."""
    if not hashes:
        return set()
    response = (
        supabase_client.table("documents")
        .select("content_hash")
        .in_("content_hash", hashes)
        .execute()
    )
    return {row["content_hash"] for row in (response.data or [])}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_row(chunk: str, source: str, frontmatter: dict, embedding: list[float]) -> dict:
    """Build a Supabase row dict from chunk data."""
    fm = frontmatter or {}
    # Normalise list values to comma-separated strings for storage
    def listify(v):
        if isinstance(v, list):
            return ", ".join(str(x) for x in v)
        return str(v) if v is not None else None

    roles = fm.get("applies_to_roles") or fm.get("role_relevance")
    sizes = fm.get("applies_to_bank_sizes") or fm.get("bank_size_applicability")
    cats  = fm.get("risk_categories") or fm.get("risk_category")

    return {
        "content":                 chunk,
        "source":                  source,
        "doc_type":                str(fm.get("doc_type", fm.get("type", "regulation"))),
        "issuing_agency":          str(fm.get("issuer", fm.get("issuing_agency", ""))),
        "risk_category":           listify(cats),
        "bank_size_applicability": listify(sizes),
        "role_relevance":          listify(roles),
        "neo4j_entity_id":         str(fm.get("regulation", fm.get("neo4j_entity_id", ""))),
        "content_hash":            content_hash(source, chunk),
        "embedding":               embedding,
    }


def run(folder: str, dry_run: bool = False):
    import voyageai

    voyage = voyageai.Client(api_key=VOYAGE_API_KEY)
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    folder_path = Path(folder)
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")

    # Collect all .txt and .md files, skip _templates/
    files = [
        p for p in folder_path.rglob("*")
        if p.suffix in (".txt", ".md")
        and "_templates" not in str(p)
        and p.is_file()
    ]

    if not files:
        print(f"No .txt or .md files found in {folder}")
        return

    print(f"Found {len(files)} files in {folder}")

    # Phase 1: collect all chunks
    all_chunks: list[tuple[str, str, dict]] = []  # (source, chunk_text, frontmatter)
    for file_path in sorted(files):
        source = str(file_path.relative_to(folder_path))
        if file_path.suffix == ".md":
            frontmatter, body = parse_md_file(file_path)
        else:
            frontmatter = {}
            body = file_path.read_text(encoding="utf-8")

        chunks = chunk_text(body)
        for chunk in chunks:
            all_chunks.append((source, chunk, frontmatter))

    print(f"Total chunks: {len(all_chunks)}")

    if dry_run:
        print("[dry-run] No embeddings created.")
        for source, chunk, _ in all_chunks[:5]:
            print(f"  {source}: {chunk[:80]}...")
        return

    # Phase 2: dedup
    hashes = [content_hash(s, c) for s, c, _ in all_chunks]
    existing = already_embedded(supabase, hashes)
    new_chunks = [
        (s, c, fm) for (s, c, fm), h in zip(all_chunks, hashes)
        if h not in existing
    ]

    skipped = len(all_chunks) - len(new_chunks)
    if skipped:
        print(f"Skipping {skipped} already-embedded chunks")

    if not new_chunks:
        print("All chunks already embedded. Nothing to do.")
        return

    print(f"Embedding {len(new_chunks)} new chunks...")

    # Phase 3: embed in batches of 8 (Voyage rate limit friendly)
    BATCH = 8
    total = len(new_chunks)
    rows: list[dict] = []

    for i in range(0, total, BATCH):
        batch = new_chunks[i : i + BATCH]
        texts = [c for _, c, _ in batch]

        embeddings = embed_batch(texts, voyage)

        for (source, chunk, frontmatter), embedding in zip(batch, embeddings):
            rows.append(build_row(chunk, source, frontmatter, embedding))

        done = min(i + BATCH, total)
        print(f"  Embedded chunk {done} of {total}")

    # Phase 4: upsert to Supabase
    print(f"Upserting {len(rows)} rows to Supabase...")
    UPSERT_BATCH = 50
    for i in range(0, len(rows), UPSERT_BATCH):
        batch_rows = rows[i : i + UPSERT_BATCH]
        supabase.table("documents").insert(batch_rows).execute()

    print(f"Done. {len(rows)} chunks embedded and stored.")


def main():
    parser = argparse.ArgumentParser(description="Embed documents into Supabase pgvector")
    parser.add_argument("--folder", default="obsidian-vault/", help="Folder to embed")
    parser.add_argument("--dry-run", action="store_true", help="Show chunks without embedding")
    args = parser.parse_args()
    run(args.folder, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
