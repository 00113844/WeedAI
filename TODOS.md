# WeedAI To-Do List

## Extraction Pipeline
- [ ] Resume Gemini extraction for remaining 302 markdown files in `data/parsed-clean`, running batches within daily quota (`--limit 50 --delay 1.0`).
- [ ] Investigate the 34 markdown files with insufficient content (see `_extraction_summary.json`) and decide whether to re-parse their source PDFs or drop them.
- [ ] Remove or archive the duplicate `data/parsed-clean` directory created outside the repo root if it is no longer needed.

## Data Quality
- [ ] Spot-check newly generated JSON in `data/extracted` to confirm crop/weed coverage and rate fidelity before bulk loading.
- [ ] Update `_extraction_summary.json` after each extraction batch to track progress and remaining pending files.

## GraphRAG Integration
- [ ] Ingest the expanded JSON set into Neo4j once extraction is complete, refreshing constraints and indexes as needed.
- [ ] Implement hybrid retrieval combining Neo4j vector indexes (`db.index.vector.queryNodes`) with Cypher lookups for GraphRAG queries.
- [ ] Document the hybrid retriever flow (vector + structured query) alongside guardrail entry points for LangGraph orchestration.
