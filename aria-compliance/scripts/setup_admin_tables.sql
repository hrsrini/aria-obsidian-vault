-- ARIA Admin Dashboard — Step 1: Database Schema
-- Run in Supabase SQL Editor: https://supabase.com/dashboard/project/ktxbpgttiriikqcgecrg/sql

-- TABLE 1: corpus_docs (admin corpus registry — separate from Phase D vector chunks table)
CREATE TABLE IF NOT EXISTS corpus_docs (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    filename         text NOT NULL,
    source_type      text NOT NULL CHECK (source_type IN ('pdf', 'obsidian')),
    status           text NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'indexed', 'failed', 'superseded')),
    intake_stage     int CHECK (intake_stage BETWEEN 1 AND 5),
    superseded_by    uuid REFERENCES corpus_docs(id),
    obsidian_path    text,
    node_count       int DEFAULT 0,
    chunk_count      int DEFAULT 0,
    last_synced_at   timestamptz,
    created_at       timestamptz DEFAULT now()
);

-- TABLE 2: test_cases
CREATE TABLE IF NOT EXISTS test_cases (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    question         text NOT NULL,
    role_filter      text CHECK (role_filter IN ('CRO', 'CISO', 'Board', 'CFO') OR role_filter IS NULL),
    bank_size_filter text,
    expected_answer  text NOT NULL,
    category         text NOT NULL
                     CHECK (category IN ('foundational', 'multi-hop', 'role', 'state-federal', 'edge')),
    last_run_at      timestamptz,
    last_result      text NOT NULL DEFAULT 'not_run'
                     CHECK (last_result IN ('pass', 'fail', 'not_run')),
    last_actual      text,
    created_by       text NOT NULL,
    created_at       timestamptz DEFAULT now()
);

-- TABLE 3: corrections
CREATE TABLE IF NOT EXISTS corrections (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    test_case_id     uuid REFERENCES test_cases(id),
    question         text NOT NULL,
    wrong_answer     text NOT NULL,
    correct_answer   text,
    source_doc_id    uuid REFERENCES corpus_docs(id),
    obsidian_note    text,
    status           text NOT NULL DEFAULT 'flagged'
                     CHECK (status IN ('flagged', 'in_review', 're_testing', 'resolved', 'wont_fix')),
    resolution_note  text,
    flagged_by       text NOT NULL,
    resolved_at      timestamptz,
    created_at       timestamptz DEFAULT now()
);

-- TABLE 4: sync_jobs
CREATE TABLE IF NOT EXISTS sync_jobs (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type         text NOT NULL
                     CHECK (job_type IN ('obsidian_sync', 'graphrag_incremental', 'graphrag_full', 'embed', 'verify')),
    triggered_by     text NOT NULL,
    status           text NOT NULL DEFAULT 'running'
                     CHECK (status IN ('running', 'completed', 'failed')),
    started_at       timestamptz DEFAULT now(),
    completed_at     timestamptz,
    duration_seconds int,
    log_output       text,
    docs_processed   int DEFAULT 0,
    error_message    text
);

-- TABLE 5: intake_sessions (wizard state machine)
CREATE TABLE IF NOT EXISTS intake_sessions (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id           uuid REFERENCES corpus_docs(id),
    stage                 int NOT NULL DEFAULT 1 CHECK (stage BETWEEN 1 AND 5),
    status                text NOT NULL DEFAULT 'in_progress'
                          CHECK (status IN ('in_progress', 'complete', 'failed', 'abandoned')),
    doc_type              text NOT NULL
                          CHECK (doc_type IN ('sr_letter', 'occ_bulletin', 'fed_guidance', 'nccob_circular')),
    obsidian_gate_checked boolean NOT NULL DEFAULT false,
    related_docs_surfaced text[],
    supersedes_doc_id     uuid REFERENCES corpus_docs(id),
    test_query            text,
    test_response         text,
    verify_result         text CHECK (verify_result IN ('passed', 'flagged') OR verify_result IS NULL),
    started_at            timestamptz DEFAULT now(),
    completed_at          timestamptz,
    duration_seconds      int,
    triggered_by          text NOT NULL,
    created_at            timestamptz DEFAULT now()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_corpus_docs_status     ON corpus_docs(status);
CREATE INDEX IF NOT EXISTS idx_corpus_docs_created_at ON corpus_docs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_test_cases_category   ON test_cases(category);
CREATE INDEX IF NOT EXISTS idx_test_cases_last_result ON test_cases(last_result);
CREATE INDEX IF NOT EXISTS idx_corrections_status    ON corrections(status);
CREATE INDEX IF NOT EXISTS idx_sync_jobs_status      ON sync_jobs(status);
CREATE INDEX IF NOT EXISTS idx_sync_jobs_started_at  ON sync_jobs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_intake_sessions_status ON intake_sessions(status);
