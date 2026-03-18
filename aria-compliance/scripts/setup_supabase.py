"""
D1 + D5: Supabase pgvector schema setup
Run: python scripts/setup_supabase.py

If SUPABASE_DB_URL is set in .env, executes SQL directly via psycopg2.
Otherwise, prints SQL for manual execution in the Supabase SQL Editor.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

SCHEMA_SQL = """
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table for vector storage (Voyage-3 = 1024 dims)
CREATE TABLE IF NOT EXISTS documents (
    id                      uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    content                 text NOT NULL,
    source                  text,
    doc_type                text,
    issuing_agency          text,
    risk_category           text,
    bank_size_applicability text,
    role_relevance          text,
    neo4j_entity_id         text,
    content_hash            text,
    embedding               vector(1024),
    created_at              timestamp DEFAULT now()
);

-- IVFFlat index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS documents_embedding_idx
    ON documents USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Unique index to prevent duplicate chunks
CREATE UNIQUE INDEX IF NOT EXISTS documents_source_hash_idx
    ON documents (source, content_hash)
    WHERE content_hash IS NOT NULL;

-- Semantic search function
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding vector(1024),
    match_count     int,
    filter          jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (id uuid, content text, source text, similarity float)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.content,
        d.source,
        1 - (d.embedding <=> query_embedding) AS similarity
    FROM documents d
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Query audit log table
CREATE TABLE IF NOT EXISTS query_log (
    id                    uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    question              text,
    answer                text,
    graph_nodes_traversed jsonb,
    vector_chunks_used    jsonb,
    created_at            timestamp DEFAULT now()
);
"""


def run():
    db_url = os.getenv("SUPABASE_DB_URL")

    if not db_url:
        print("SUPABASE_DB_URL not set — printing SQL for manual execution.")
        print("Paste the SQL below into: Supabase Dashboard > SQL Editor")
        print()
        print("=" * 70)
        sys.stdout.buffer.write(SCHEMA_SQL.encode("utf-8"))
        print()
        print("=" * 70)
        sys.exit(0)

    try:
        import psycopg2
    except ImportError:
        print("psycopg2 not found. Run: pip install psycopg2-binary")
        sys.exit(1)

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()

        # Run each statement individually for clearer error reporting
        statements = [s.strip() for s in SCHEMA_SQL.split(";") if s.strip()]
        for stmt in statements:
            cur.execute(stmt)

        cur.close()
        conn.close()

        print("Supabase schema ready:")
        print("  documents table        — vector(1024), ivfflat index")
        print("  match_documents()      — cosine similarity RPC")
        print("  query_log table        — audit trail")

    except Exception as e:
        print(f"Error: {e}")
        print()
        print("Run this SQL manually in the Supabase SQL Editor:")
        print(SCHEMA_SQL)
        sys.exit(1)


if __name__ == "__main__":
    run()
