# SRE Knowledge Base

Sample operational documentation for the Lab 1a vector store demo.

## Documents

| File | Category | Description |
|------|----------|-------------|
| `runbook-db-performance.md` | runbook | Database performance troubleshooting |
| `runbook-memory-pressure.md` | runbook | Memory and OOM issues |
| `runbook-network-latency.md` | runbook | Network connectivity problems |
| `playbook-sev1-response.md` | playbook | SEV1 incident protocol |
| `playbook-rollback.md` | playbook | Emergency rollback procedures |
| `guide-cpu-analysis.md` | guide | CPU profiling techniques |
| `guide-query-optimization.md` | guide | Database query tuning |
| `postmortem-2026-01-15.md` | postmortem | Sample incident analysis |

## Loading Data

These documents are designed to be:
1. Chunked (if >2000 tokens)
2. Embedded using `text-embedding-3-small`
3. Loaded into Cosmos DB with vector index

See `scripts/load_knowledge_base.py` for the loading script.
