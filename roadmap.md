# WeedAI Project Roadmap

## 1. Project Overview
**WeedAI** is an advanced agronomic AI system designed to assist with weed identification, herbicide management, and crop safety. It leverages a multi-agent architecture with domain-specific guardrails, a knowledge graph (GraphRAG), and a legacy simulation wrapper.

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

### Phase 1: Initialization & Infrastructure
- [ ] **Initialize `uv` Workspace:** Set up root `pyproject.toml` with workspace members.
- [ ] **Environment Setup:** Create `.env` file and `packages/core/src/config.py` using `pydantic-settings`.
- [ ] **Database Connectors:** Implement MongoDB and Neo4j clients in `packages/core`.

### Phase 2: Domain Guardrails (NeMo)
- [ ] **Configuration:** Define `config.yml` and `rails.co` in `packages/guardrails`.
- [ ] **Topical Rails:** Implement flows to block off-topic (medical/political) queries.
- [ ] **Testing:** Create unit tests for guardrail responses.

### Phase 3: Knowledge Graph & RAG
- [ ] **Ingestion Pipeline:** Build scripts to parse APVMA PDFs and populate MongoDB/Neo4j.
- [ ] **Graph Logic:** Implement `packages/graph` with RAG tools (Hybrid Search).
- [ ] **Entity Extraction:** Use SpaCy/LLM to extract entities for the graph.

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
