# Roadmap (snapshot)

## Phase 1: Initialization & Infrastructure
- Initialize `uv` workspace and root `pyproject.toml` members
- Create `.env` and `packages/core/src/config.py` using pydantic-settings
- Implement MongoDB + Neo4j connectors in `packages/core`

## Phase 2: Domain Guardrails (NeMo)
- Define `config.yml` and `rails.co` in `packages/guardrails`
- Implement topical rails to block off-topic queries
- Add unit tests for guardrail responses

## Phase 3: Knowledge Graph & RAG
- Ingestion pipeline for APVMA labels (PDFs parsed to Markdown/JSON)
- Load Neo4j graph and wire GraphRAG queries

## Planned delivery
- API gateway (FastAPI), Next.js UI, LangGraph orchestration, simulation sidecar
- Hybrid retrieval: semantic + Cypher over Neo4j
