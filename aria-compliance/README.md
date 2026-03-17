# ARIA — Banking Compliance Intelligence System

ARIA answers US banking compliance questions with the depth of a 20-year compliance
veteran: specific citations, role-level obligations, asset-size applicability, and
awareness of which regulations supersede others.

It combines **vector similarity search** (Supabase pgvector) with **knowledge graph
traversal** (MS GraphRAG + Neo4j AuraDB) to answer multi-hop regulatory questions
that classic RAG cannot handle.

---

## Project Structure

```
aria-compliance/
├── api/                        # FastAPI application (Phase E)
├── ingestion/                  # Document processing scripts (Phase B/C)
├── retrieval/                  # Hybrid retrieval engine (Phase D)
├── obsidian-vault/             # Human-curated regulation notes
│   ├── 00-inbox/               # Drop new documents here for review
│   ├── 01-federal-regulations/ # SR Letters, OCC Bulletins, Basel III, etc.
│   ├── 02-state-statutes/      # NC Chapter 53C and other state law
│   ├── 03-federal-guidance/    # FFIEC, FDIC, Fed guidance docs
│   ├── 04-risk-frameworks/     # COSO ERM, NIST CSF, Basel frameworks
│   ├── 05-role-obligations/    # CRO, CISO, Board, CFO obligation notes
│   ├── 06-thresholds/          # Asset thresholds and trigger logic
│   ├── 07-definitions/         # Regulatory term definitions
│   ├── 08-expert-insights/     # Examiner focus areas, pitfalls
│   └── 09-amendments-log/      # Change history for superseded regs
├── documents/
│   ├── raw/                    # Original PDFs — never modify
│   └── processed/              # Chunked output from ingestion
├── graphrag-output/            # GraphRAG index artifacts + settings.yaml
├── scripts/                    # Utility scripts (build_registry.py, etc.)
├── tests/                      # Verification tests
├── .env.example                # Environment variable template
├── requirements.txt
├── railway.toml                # Railway deployment config
└── README.md
```

---

## Build Phases

| Phase | Weeks | Deliverable |
|-------|-------|-------------|
| **A — Foundation** | 1–2 | Repo scaffold, infra accounts, Obsidian vault, 10 priority notes |
| **B — Graph Build** | 3–5 | GraphRAG index, Neo4j load, obsidian→graph sync, Cypher verified |
| **C — Vector Store** | 6–7 | Supabase pgvector loaded, semantic search validated on 10 queries |
| **D — RAG Engine** | 8–11 | FastAPI + query orchestrator, parallel vector+graph, Claude answers |
| **E — Production** | 12–14 | Railway deploy, cron sync, update workflow documented and tested |

Each phase must be verified before proceeding to the next.

---

## Environment Setup

### 1. Copy environment file

```bash
cp .env.example .env
```

Fill in all values in `.env`:

| Variable | Where to get it |
|----------|----------------|
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `NEO4J_URI` | Neo4j AuraDB dashboard (bolt:// URI) |
| `NEO4J_USER` | Neo4j AuraDB (default: `neo4j`) |
| `NEO4J_PASSWORD` | Neo4j AuraDB dashboard |
| `SUPABASE_URL` | Supabase project settings → API |
| `SUPABASE_ANON_KEY` | Supabase project settings → API |
| `SUPABASE_SERVICE_KEY` | Supabase project settings → API |
| `RAILWAY_ENVIRONMENT` | Set to `development` locally |
| `PORT` | `8000` locally |

### 2. Create infrastructure accounts

- **Neo4j AuraDB** — free tier at https://aura.neo4j.io (up to 200K nodes)
- **Supabase** — free tier at https://supabase.com, enable pgvector:
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  ```

### 3. Install dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## Running Locally

```bash
# Start the API server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Health check
curl http://localhost:8000/health

# Query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What does SR 16-11 require of the CRO?", "role": "CRO"}'
```

## Running on Railway

Railway detects Python projects automatically via `requirements.txt`.

1. Push this repo to GitHub
2. Create a new Railway project → Deploy from GitHub repo
3. Add all environment variables from `.env.example` in Railway dashboard
4. Railway will build and deploy using the start command in `railway.toml`

```bash
# Deploy manually (after Railway CLI setup)
railway up
```

---

## Utility Scripts

```bash
# Build document registry CSV from documents/raw/
python scripts/build_registry.py
```

Outputs `documents/registry.csv` — fill in metadata columns manually before ingestion.

---

## Regulation Note Template

Every document in `obsidian-vault/` follows this structure:

```markdown
---
regulation: SR 16-11
issuer: Federal Reserve
effective_date: 2016-01-01
status: active          # active | superseded | proposed
supersedes: SR 95-51
applies_to_roles: [CRO, Board, CFO, Model Risk Manager]
applies_to_bank_sizes: [">$10Bn", ">$50Bn"]
risk_categories: [model_risk, operational_risk]
jurisdiction: federal
---

## Summary
2-3 sentence plain-English summary.

## Key Requirements
- Bullet list of mandates

## Examiner Focus Areas
- What regulators check during examination

## Common Pitfalls
- What banks typically get wrong

## Related Regulations
See also: [[Basel III Capital Rules]] | [[SR 11-7]]

## Supersession Note
This supersedes [[SR 95-51]]. Key change: expanded scope to non-bank subsidiaries.
```

---

## Hard Constraints

- **Never** skip Obsidian note curation for any new document
- **Never** delete superseded regulation notes — mark `status: superseded` and link replacement
- **Never** re-index the full corpus — always use `graphrag index --root . --incremental`
- **Always** tag `applies_to_bank_sizes` in note frontmatter
- **Never** hardcode API keys — use environment variables only
