# Architecture

## Current
- Ingestion (packages/ingestion): parse PDFs -> Markdown, clean noise, Gemini extraction to JSON.
- Knowledge Graph (packages/graph): Neo4j schema + loader + helper queries; underpins GraphRAG.
- Data lake layout: `data/labels` -> `data/parsed` -> `data/parsed-clean` -> `data/extracted`.

## Planned (roadmap)
- API gateway (FastAPI) to expose retrieval + recommendations.
- Frontend (Next.js + Tailwind) for operators and agronomists.
- LangGraph orchestration for tool-using agents over graph + vector store.
- Guardrails (NeMo) to enforce domain scope and safety.
- Simulation sidecar: Python wrapper around legacy Java weed-seed ecology model.

## Retrieval pattern (target)
1) Semantic/vector retrieval over chunks for recall.
2) Cypher queries over Neo4j for structured facts (products, crops, weeds, rates, plant-back periods).
3) Response synthesis with guardrails.

## Security & config
- Secrets via `.env` (`GEMINI_API_KEY`, `NEO4J_*`).
- Keep PDFs local; do not commit regulated or proprietary data.
