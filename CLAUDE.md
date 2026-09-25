# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WeedAI is an agronomic AI system for integrated weed management, specifically processing Australian herbicide label PDFs into a Neo4j knowledge graph for GraphRAG. The pipeline: PDFs → Markdown → Cleaned Markdown → Structured JSON → Neo4j graph. Target architecture (not yet built): see `AGENTIC_WEED_MANAGEMENT_DEVELOPMENT_PLAN.md`. Simulation goes through an adapter over the Python port `WeedSeedWizard-py` (`DPIRD-FSI/WeedSeedWizard-py`), pinned to a commit; the Java "sidecar" in older docs is superseded. See `roadmap.md` for phase status.

**Proposed direction, not yet agreed (2026-09-25):** `docs/ALIGNMENT_2026-09.md`. Label content is cited context for the agent, not a recommender; the extraction route is being chosen by the trial in `experiments/2026-09-pdf-inspector-trial/`. Do not start SimpleKGPipeline extraction or the LangGraph skeleton until that is settled.

## Working in this repo (agentic sessions)

- **Repo root is `WeedAI/WeedAI`** (`C:\Users\00113844\Documents\WeedAI\WeedAI` on this machine). The parent `WeedAI/` folder is a wrapper — it holds the working `.venv`, Copilot agent personas under `.github/`, and nothing else. Open Claude Code in the inner folder.
- **`roadmap.md` is the source of truth for status.** At the end of every session: add a line to its Daily Diary, add a dated entry to `CHANGELOG.md`, and make sure `TODOS.md` still agrees with the roadmap's Immediate Next Steps.
- **Git:** work on `main`, push straight to `origin` (HTTPS, `gh` credential helper; SSH is not set up here). GitHub repo is `00113844/WeedAI` (`gtalckmin/WeedAI` is the same repo under the account's old name).
- **Python:** use the outer venv — `../.venv/Scripts/python.exe` (Python 3.12). It has `ingestion`, `graph`, `docling` and the `load-graph` / `init-schema` / `load-chunks` / `chunk-docling` entry points installed. `python` is not on PATH in Git Bash. `packages/ingestion/.venv` (3.11) is stale — ignore it.
- There is **no root `pyproject.toml` / uv workspace**; each package installs on its own (below).

## Development Commands

### Package Installation
```sh
# Install packages individually into ../.venv (use uv)
uv pip install -e packages/ingestion
uv pip install -e packages/graph
# packages/guardrails is a stub (pyproject + design docs only) and its pin
# nemo-guardrails==0.10.0 is unavailable — do not install it yet.
```

### Ingestion Pipeline
```sh
# Parse PDFs to Markdown (PyMuPDF4LLM)
python -m ingestion.parser                    # all labels
python -m ingestion.parser --single 31209ELBL # single file
python -m ingestion.local_parser              # offline PyMuPDF alternative

# Structure-aware parse to JSON with tables (Docling)
python -m ingestion.docling_parser

# Clean Markdown
python -m ingestion.cleaner data/parsed --output data/parsed-clean

# Extract JSON with Gemini — path A (HerbicideLabel schema; what load-graph reads)
python -m ingestion.extractor data/parsed-clean --output data/extracted
python -m ingestion.extractor data/parsed-clean --output data/extracted --limit 50 --delay 1.0

# Extract JSON with Gemini — path B (usage_scenarios schema; no loader yet)
python packages/ingestion/scripts/markdown_to_graph.py   # writes data/extracted-from-md

# Direct PDF→JSON (Gemini) — experimental, superseded
python -m ingestion.gemini_parser data/labels --output data/extracted-pdf
```

### Graph Operations
```sh
init-schema              # create constraints/indexes + reference data
init-schema --stats      # show graph statistics
init-schema --clear      # clear graph then reinitialize
load-graph data/extracted # load HerbicideLabel JSON into Neo4j
chunk-docling            # structure-aware chunks from data/docling
load-chunks              # load chunks + embeddings for vector search
```

### Testing
```sh
cd packages/ingestion
pytest tests/ -v -m "not integration"      # unit tests (no API calls)
pytest tests/ -v -m integration             # integration (requires LLAMA_CLOUD_API_KEY)
pytest tests/ --cov=src/ingestion --cov-report=html
# packages/graph and packages/guardrails have no tests yet.
```

## Architecture

### Package Structure
- **packages/ingestion/**: PDF parsing, cleaning, Gemini-based extraction
  - `parser.py` - PyMuPDF4LLM parsing with YAML frontmatter
  - `local_parser.py` - Offline PyMuPDF parser
  - `docling_parser.py` - Docling-based parser for tables → `data/docling`
  - `cleaner.py` - Remove headers/footers/safety noise
  - `extractor.py` - Gemini structured extraction with Pydantic schema (`HerbicideLabel`)
  - `gemini_parser.py` - Direct PDF→JSON; also defines the `usage_scenarios` schema
  - `scripts/markdown_to_graph.py` - Markdown → `usage_scenarios` JSON (`data/extracted-from-md`)
  - `scripts/resume_gemini.py` - Resume a quota-interrupted extraction run
  - `scraper.py`, `csv_scraper.py` - APVMA label download

- **packages/graph/**: Neo4j integration
  - `schema.py` - Constraints, indexes, State/ModeOfAction reference nodes
  - `loader.py` - Load `HerbicideLabel` JSON into graph
  - `chunker.py`, `chunk_loader.py` - Docling JSON → chunks → Chunk nodes with 768-d embeddings
  - `queries.py` - Query functions for GraphRAG retrieval
  - `tools.py` - LangGraph tool wrappers (vector_search_tool, graph_traversal_tool)

- **packages/guardrails/**: **stub only** — `pyproject.toml` plus design docs
  (`GUARDRAILS_*.md`, `IMPLEMENTATION_INSTRUCTIONS.md`). No source yet.

- **scripts/**: `evaluate_docling.py`, `merge_docling_blocks.py` — one-off Docling QA.

### Neo4j Graph Schema (current, flat — being redesigned, see roadmap Phase 3)
Nodes: `Herbicide`, `ActiveConstituent`, `ModeOfAction`, `Crop`, `Weed`, `State`, `Document`, `Chunk`

Key relationships:
- `(Herbicide)-[:CONTAINS]->(ActiveConstituent)`
- `(Herbicide)-[:HAS_MODE_OF_ACTION]->(ModeOfAction)`
- `(Herbicide)-[:REGISTERED_FOR]->(Crop)`
- `(Herbicide)-[:CONTROLS {rate, timing, level}]->(Weed)`
- `(Herbicide)-[:REGISTERED_IN]->(State)`
- `(Document)-[:CONTAINS_CHUNK]->(Chunk)` (vector index `chunk_embeddings`)

### Data Flow and what is tracked
Full table in `data/README.md`. Summary:

| Stage | Path | Tracked |
|---|---|---|
| 1. Source PDFs | `data/labels/` (386) | yes — legacy, 169 MB; new PDFs ignored |
| 2. Parsed Markdown | `data/parsed/` | no |
| 2b. Docling JSON | `data/docling/` | no |
| 3. Cleaned Markdown | `data/parsed-clean/` (386) | **yes** |
| 4a. `HerbicideLabel` JSON | `data/extracted/` (51) | **yes** — what `load-graph` consumes |
| 4b. `usage_scenarios` JSON | `data/extracted-from-md/` (160) | **yes** — no loader yet |
| 5. Neo4j | AuraDB / local | — |

The two extraction schemas are incompatible; choosing one is the current blocker (roadmap § Immediate Next Steps).

## Environment Variables

Required in `.env` at repo root (`.env.example` lists them):
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
- Pydantic schemas: `HerbicideLabel`, `WeedControlEntry` (extractor); `usage_scenarios` / `WeedControlEdge` (gemini_parser)
- Embeddings: `sentence-transformers/all-mpnet-base-v2` (768-d)

## Planned Components (Roadmap)

- **apps/api/**: FastAPI gateway for orchestration
- **apps/web/**: Next.js + TailwindCSS frontend
- ~~**apps/simulation-sidecar/**: Python wrapper for legacy Java weed seed ecology model~~ Superseded: a WeedSeedWizard-py adapter (plan §4.3)
- **packages/core/**: Shared utilities & DB connections
- Hybrid retrieval: `neo4j-graphrag-python` HybridCypherRetriever over vector + fulltext + Cypher

## Coding Standards

- Python 3.11+ (3.12 in the working venv)
- Build system: Hatchling
- Use `ruff` for linting, `mypy` for type checking
- Tests with `pytest`, markers: `integration`, `unit`
