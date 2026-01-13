# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WeedAI is an agronomic AI system for integrated weed management, specifically processing Australian herbicide label PDFs into a Neo4j knowledge graph for GraphRAG. The pipeline: PDFs → Markdown → Cleaned Markdown → Structured JSON → Neo4j graph.

## Development Commands

### Package Installation
```sh
# Install packages (use uv)
uv pip install -e packages/ingestion
uv pip install -e packages/graph
uv pip install -e packages/guardrails
```

### Ingestion Pipeline
```sh
# Parse PDFs to Markdown (PyMuPDF4LLM)
python -m ingestion.parser                    # all labels
python -m ingestion.parser --single 31209ELBL # single file

# Clean Markdown
python -m ingestion.cleaner data/parsed --output data/parsed-clean

# Extract JSON with Gemini
python -m ingestion.extractor data/parsed-clean --output data/extracted
python -m ingestion.extractor data/parsed-clean --output data/extracted --limit 50 --delay 1.0

# Direct PDF→JSON (Gemini)
python -m ingestion.gemini_parser data/labels --output data/extracted-pdf
```

### Graph Operations
```sh
init-schema              # create constraints/indexes + reference data
init-schema --stats      # show graph statistics
init-schema --clear      # clear graph then reinitialize
load-graph data/extracted # load JSON into Neo4j
```

### Testing
```sh
cd packages/ingestion
pytest tests/ -v -m "not integration"      # unit tests (no API calls)
pytest tests/ -v -m integration             # integration (requires LLAMA_CLOUD_API_KEY)
pytest tests/ --cov=src/ingestion --cov-report=html

cd packages/guardrails
pytest tests/ -v                            # all guardrails tests
pytest tests/test_pii_detection.py -v       # specific test file
```

## Architecture

### Package Structure
- **packages/ingestion/**: PDF parsing, cleaning, Gemini-based extraction
  - `parser.py` - PyMuPDF4LLM parsing with YAML frontmatter
  - `cleaner.py` - Remove headers/footers/safety noise
  - `extractor.py` - Gemini structured extraction with Pydantic schema
  - `gemini_parser.py` - Direct PDF→JSON (alternative)
  - `docling_parser.py` - Docling-based parser for tables

- **packages/graph/**: Neo4j integration
  - `schema.py` - Constraints, indexes, State/ModeOfAction reference nodes
  - `loader.py` - Load extracted JSON into graph
  - `queries.py` - Query functions for GraphRAG retrieval

- **packages/guardrails/**: NeMo Guardrails for safety/compliance
  - `guardrail.py` - GuardrailRunner class
  - `config/config.yml` - NeMo configuration
  - `config/rails.co` - Colang rule definitions
  - `actions/` - PII detection, topic classification

### Neo4j Graph Schema
Nodes: `Herbicide`, `ActiveConstituent`, `ModeOfAction`, `Crop`, `Weed`, `State`

Key relationships:
- `(Herbicide)-[:CONTAINS]->(ActiveConstituent)`
- `(Herbicide)-[:HAS_MODE_OF_ACTION]->(ModeOfAction)`
- `(Herbicide)-[:REGISTERED_FOR]->(Crop)`
- `(Herbicide)-[:CONTROLS {rate, timing, level}]->(Weed)`
- `(Herbicide)-[:REGISTERED_IN]->(State)`

### Data Flow
1. Source PDFs in `data/labels/` (not committed)
2. Parsed Markdown in `data/parsed/`
3. Cleaned Markdown in `data/parsed-clean/`
4. Extracted JSON in `data/extracted/`
5. Loaded into Neo4j via `load-graph`

## Environment Variables

Required in `.env` at repo root:
```
GEMINI_API_KEY=...
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
LLAMA_CLOUD_API_KEY=...   # only for integration tests
```

## Key Models & Prompts

- Extraction uses `gemini-2.5-flash-lite` by default (or `gemini-2.5-flash` for PDF parsing)
- Extraction prompt in `ingestion/extractor.py:EXTRACTION_PROMPT`
- Pydantic schemas: `HerbicideLabel`, `WeedControlEntry`

## Planned Components (Roadmap)

- **apps/api/**: FastAPI gateway for orchestration
- **apps/web/**: Next.js + TailwindCSS frontend
- **apps/simulation-sidecar/**: Python wrapper for legacy Java weed seed ecology model
- **packages/core/**: Shared utilities & DB connections
- Hybrid retrieval: Neo4j vector indexes + Cypher lookups for GraphRAG

## Coding Standards

- Python 3.11+, managed with `uv` workspace
- Build system: Hatchling
- Use `ruff` for linting, `mypy` for type checking
- Tests with `pytest`, markers: `integration`, `unit`
