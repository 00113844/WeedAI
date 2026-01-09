# WeedAI Project Roadmap

## 1. Project Overview
**WeedAI** is an agronomic AI system (reactive agents) designed to assist with assist agronomist with decision making on integrated weed management (herbicide) management. It leverages a multi-agent architecture with domain-specific guardrails, a knowledge graph (GraphRAG), and a legacy simulation weed seed ecological model. 

## 2. Tech Stack
- **Language:** Python 3.11+ (Backend/AI), TypeScript (Frontend), Java (Legacy Simulation)
- **Package Manager:** `uv` (Workspace mode)
- **Orchestration:** LangGraph, LangChain
- **Guardrails:** NeMo Guardrails
- **Database:** MongoDB (Vector/Docs), Neo4j (Knowledge Graph)
- **API:** FastAPI
- **Frontend:** Next.js, TailwindCSS
- **Infrastructure:** Docker, GCP

## 3. Project Scaffold (Monorepo Structure)
We will use a **`uv` Workspace** to manage multiple components in a single repository.

```text
WeedAI/
├── apps/
│   ├── web/                    # Next.js Frontend
│   │   ├── src/
│   │   ├── package.json
│   │   └── ...
│   ├── api/                    # Main FastAPI Gateway (Orchestrator)
│   │   ├── src/
│   │   │   ├── main.py         # Entry point
│   │   │   └── routes/         # API Endpoints
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   └── simulation-sidecar/     # Python Wrapper for Legacy Java
│       ├── src/
│       │   ├── main.py         # FastAPI app exposing Java logic
│       │   ├── wrapper.py      # Subprocess/JNI calls to Java
│       │   └── java/           # Symlink or submodule to legacy Java code
│       ├── legacy-java/        # The actual Legacy Java Project
│       │   ├── src/
│       │   └── pom.xml
│       ├── pyproject.toml
│       └── Dockerfile          # Multi-stage build (Java + Python)
├── packages/
│   ├── core/                   # Shared Utilities & DB Connections
│   │   ├── src/
│   │   │   ├── db/             # MongoDB & Neo4j connectors
│   │   │   └── config.py       # Pydantic Settings
│   │   └── pyproject.toml
│   ├── graph/                  # LangGraph Logic (The "Brain")
│   │   ├── src/
│   │   │   ├── nodes/          # Individual graph nodes
│   │   │   ├── tools/          # Tools (RAG, Sim calls)
│   │   │   ├── state.py        # GraphState definition
│   │   │   └── workflow.py     # Graph construction
│   │   └── pyproject.toml
│   └── guardrails/             # NeMo Guardrails Config
│       ├── config/
│       │   ├── config.yml      # Main NeMo config
│       │   ├── rails.co        # Colang definitions
│       │   └── actions.py      # Custom actions for rails
│       └── pyproject.toml
├── .env.example                # Template for environment variables
├── pyproject.toml              # Workspace Root
├── uv.lock                     # Single lockfile for all Python apps
├── docker-compose.yml          # Local development orchestration
└── README.md
```

## 4. Development Roadmap

### Daily Diary
- **2026-01-08:** Restarted Gemini markdown extraction in 50-file batches (all short-content skips) and began reverse-engineering the Apparent compatibility matrix to derive structured mix rules.

### Phase 1: Initialization & Infrastructure
- [ ] **Initialize `uv` Workspace:** Set up root `pyproject.toml` with workspace members.
- [ ] **Environment Setup:** Create `.env` file and `packages/core/src/config.py` using `pydantic-settings`.
- [ ] **Database Connectors:** Implement MongoDB and Neo4j clients in `packages/core`.

### Phase 2: Domain Guardrails (NeMo)
- [ ] **Configuration:** Define `config.yml` and `rails.co` in `packages/guardrails`.
- [ ] **Topical Rails:** Implement flows to block off-topic (medical/political) queries.
- [ ] **Testing:** Create unit tests for guardrail responses.

### Phase 3: Knowledge Graph & RAG
- [x] **Ingestion Pipeline:** Parse the `search-results.csv` export to identify unique active ingredient combinations and download representative PDF labels from `elabels.apvma.gov.au`.
- [x] **PDF Parsing:** ~~Use `llama-parse`~~ Using **PyMuPDF4LLM** for local, offline parsing with excellent table extraction.
  - 386 herbicide labels successfully parsed to markdown
  - YAML frontmatter with extracted metadata (product_number, active_constituent, mode_of_action_group)
  - Tables preserved in markdown format (Directions for Use, Weed Tables, Plant-back periods)
- [x] **Testing Module:** Unit and integration tests in `packages/ingestion/tests/` with pytest.
  - Unit tests: Parser config, metadata persistence, mock PDF parsing
  - Integration tests: Live parsing tests
- [x] **Document Cleaning:** Built `cleaner.py` to remove noise from parsed markdown.
  - Removes page headers/footers, safety directions, storage/disposal sections
  - Processed all 388 files with 12.3% size reduction
- [x] **Entity Extraction:** Built Gemini-based structured extraction (`extractor.py`).
  - Uses `google-genai` SDK with Pydantic schema for structured output
  - Extracts: product info, active constituents, MOA groups, crops, weeds, control entries
  - 22/386 files extracted (limited by free tier API quota - 20 requests/day)
  - Output: JSON files in `data/extracted/` ready for graph loading
- [x] **Graph Construction:** Built `packages/graph` with Neo4j integration.
  - **Schema (`schema.py`):** Constraints, indexes, State nodes, ModeOfAction reference data
  - **Loader (`loader.py`):** Loads extracted JSON into Neo4j graph
  - **Queries (`queries.py`):** Query functions for GraphRAG retrieval
  - **Current Graph:** 21 herbicides, 91 crops, 290 weeds, 537 CONTROLS relationships
- [ ] **Complete Extraction:** Resume extraction when API quota resets (or upgrade to paid tier)
- [ ] **Hybrid Retrieval:** Implement a custom retriever in `packages/graph` that combines:
    - **Semantic Search:** `Neo4jVector.similarity_search()` for unstructured context.
    - **Graph Query:** `GraphCypherQAChain` for structured questions (e.g., "List all herbicides for Ryegrass").

### Phase 4: Simulation Sidecar
- [ ] **Containerization:** Create Dockerfile for `apps/simulation-sidecar` (Java + Python).
- [ ] **Wrapper API:** Build FastAPI endpoints to trigger Java CLI commands.
- [ ] **Queue:** Implement async task queue (Redis/Celery) if simulation is slow.

### Phase 5: Orchestration (The Brain)
- [ ] **LangGraph Workflow:** Assemble the graph in `packages/graph` connecting Guardrails, RAG, and Sim tools.
- [ ] **API Gateway:** Expose the graph via `apps/api` using `langserve` or standard FastAPI routes.

### Phase 6: Frontend & Deployment
- [ ] **Next.js App:** Initialize `apps/web`.
- [ ] **UI Components:** Build Chat interface and Map visualization.
- [ ] **Integration:** Connect Frontend to `apps/api`.

## 5. Best Practices & Standards

### Python & `uv`
- **Dependency Management:** Use `uv add <package> --package <component>` to keep dependencies isolated.
- **Lockfile:** Commit `uv.lock` to ensure reproducible builds.
- **Linting:** Use `ruff` for linting and formatting. Configure in root `pyproject.toml`.
- **Type Checking:** Enforce `mypy` (strict mode) for all Python code, especially for LangGraph state definitions.

### Configuration & Security
- **Environment Variables:** NEVER commit `.env` files. Use `.env.example`.
- **Secrets:** Access secrets only via `pydantic-settings` classes, not `os.getenv` directly.
- **API Keys:** Store LLM and DB keys in `.env` and inject them at runtime.

### Code Quality
- **Pre-commit Hooks:** Use `pre-commit` to run `ruff` and `mypy` before every commit.
- **Testing:** Use `pytest` for backend tests. Place tests in `tests/` folder within each package/app.
- **Documentation:** Docstrings for all public functions (Google style).

### Testing Commands
```bash
# Run all unit tests (no API calls)
cd packages/ingestion
pytest tests/ -v -m "not integration"

# Run integration tests (requires LLAMA_CLOUD_API_KEY in .env)
pytest tests/ -v -m integration

# Run with coverage
pytest tests/ --cov=src/ingestion --cov-report=html

# Quick interactive test
python -m tests.test_parser
```

## 6. Getting Started (Commands)

```bash
# 1. Initialize Root
uv init
# (Edit pyproject.toml to add [tool.uv.workspace])

# 2. Create Components
mkdir -p apps/api packages/core
cd apps/api && uv init --app
cd ../../packages/core && uv init --lib

# 3. Add Dependencies
uv add fastapi --package apps/api
uv add pydantic --package packages/core

# 4. Run Development Server
uv run --package apps/api fastapi dev src/main.py
```
