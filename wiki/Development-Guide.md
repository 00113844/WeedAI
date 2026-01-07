# Development Guide

## Prereqs
- Python 3.11+
- `uv` (workspace-friendly)
- Neo4j running locally or remote URI

## Install
```sh
uv pip install -e packages/ingestion
uv pip install -e packages/graph
```

## Environment
Create `.env` at repo root:
```
GEMINI_API_KEY=...
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
LLAMA_CLOUD_API_KEY=...   # only for integration tests using LlamaParse
```

## Testing
```sh
cd packages/ingestion
pytest tests/ -v -m "not integration"      # fast unit tests
pytest tests/ -v -m integration             # requires LLAMA_CLOUD_API_KEY
```

## Coding notes
- Keep PDFs out of git; treat `data/labels` as local-only.
- Re-run parsing/cleaning before extraction if you adjust prompts or cleaner rules.
- Prefer deterministic batch runs; capture outputs under `data/parsed-clean` and `data/extracted`.

## Tooling
- PyMuPDF4LLM for parsing
- Gemini 2.5 for extraction (markdown and optional PDF direct)
- Neo4j for graph storage
