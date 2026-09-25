# WeedAI Project Roadmap

> **Last Updated:** 2026-09-25
> **Status:** Phase 3 schema redesign still open; pipeline data now versioned in git. A revised direction is proposed on branch `pdf-inspector` and awaits agreement: `docs/ALIGNMENT_2026-09.md`. This file is the source of truth for project status — keep the Daily Diary and Immediate Next Steps current, and keep `TODOS.md` in agreement.

## 1. Project Overview
**WeedAI** is an agronomic AI system (reactive agents) designed to assist agronomists with decision making on integrated weed management (herbicide) management. It leverages a multi-agent architecture with domain-specific guardrails, a knowledge graph (GraphRAG), and a legacy simulation weed seed ecological model. 

## 2. Tech Stack

### Current Stack
| Component | Technology | Status |
|-----------|-----------|--------|
| **Language** | Python 3.11+ | ✅ Active |
| **Package Manager** | `uv` (per-package installs; no workspace root yet) | ✅ Active |
| **Vector DB** | Neo4j AuraDB (768d embeddings) | ✅ Connected |
| **Embeddings** | sentence-transformers/all-mpnet-base-v2 | ✅ Working |
| **PDF Parsing** | PyMuPDF4LLM + Docling | ✅ 386 labels parsed |
| **LLM Extraction** | Gemini 2.5 Flash | ⚠️ Split across two incompatible schemas (51 + 160 files); neither carries citations, so re-extraction is proposed |
| **Simulation** | `WeedSeedWizard-py` (Python port, `DPIRD-FSI/WeedSeedWizard-py`) | ✅ `main` at `16d06ba`, Java parity across four regions; replaces the Java sidecar |

### Planned Stack Updates
| Component | Current → Target | Rationale |
|-----------|------------------|-----------|
| **GraphRAG** | Custom → `neo4j-graphrag-python` | Official Neo4j package with SimpleKGPipeline, HybridCypherRetriever |
| **Orchestration** | None → LangGraph | Stateful agents with tool-based retrieval |
| **Guardrails** | None → NeMo + LangGraph interrupt | Topical rails + human-in-the-loop validation |
| **Embeddings** | Local → OpenAI (prod) | Better quality for production, keep local for dev |
| **Frontend** | None → Next.js + TailwindCSS | Planned for Phase 7 |

## 3. Project Scaffold (Monorepo Structure)

```text
WeedAI/
├── apps/
│   ├── web/                    # Next.js Frontend (Phase 7)
│   ├── api/                    # FastAPI Gateway (Phase 6)
│   └── simulation-sidecar/     # SUPERSEDED: simulation goes through a WeedSeedWizard-py adapter (plan §4.3)
├── packages/
│   ├── core/                   # Shared Utilities & DB Connections (not started)
│   ├── graph/                  # Neo4j Schema, Loaders, RAG Queries ✅
│   ├── ingestion/              # PDF Parsing, Cleaning, Extraction ✅
│   └── guardrails/             # Stub: pyproject + design docs only (Phase 7)
├── data/                       # see data/README.md for the full table
│   ├── labels/                 # Source PDFs (386, tracked — legacy)
│   ├── parsed/                 # Raw markdown (386, untracked)
│   ├── docling/                # Docling JSON outputs (386, untracked) ✅
│   ├── parsed-clean/           # Cleaned markdown (386, tracked) ✅
│   ├── extracted/              # HerbicideLabel JSON (51, tracked) — what load-graph reads
│   └── extracted-from-md/      # usage_scenarios JSON (160, tracked) — no loader yet
├── CLAUDE.md                   # Agent instructions (AGENTS.md / GEMINI.md point here)
└── (no workspace pyproject.toml yet — packages install individually)
```

## 4. Development Roadmap

### Progress Summary

| Phase | Name | Status | Blocker |
|-------|------|--------|---------|
| 1 | Infrastructure | ✅ Done | - |
| 2 | Data Pipeline | ⚠️ 90% | Extraction split across two incompatible schemas — pick one, then finish |
| 3 | Schema Design | 🔴 **CRITICAL** | Flat schema doesn't support agronomic queries |
| 4 | Entity Extraction | ⏸️ Blocked | Waiting for schema redesign |
| 5 | Retrieval Layer | ⚠️ Basic | Needs HybridCypherRetriever upgrade |
| 6 | Orchestration | ⏸️ Not Started | Waiting for retrieval layer |
| 7 | Guardrails | ⏸️ Not Started | Waiting for orchestration |
| 8 | Frontend | ⏸️ Not Started | Waiting for API |

---

### Daily Diary
- **2026-09-25 (Rodrigo, branch `pdf-inspector`):** Brought `AGENTIC_WEED_MANAGEMENT_DEVELOPMENT_PLAN.md` into the repo verbatim, with Gustavo's 2026-09-21 roadmap and TODOS lines. Added `docs/ALIGNMENT_2026-09.md` (what is stale, WeedSeedWizard-py state, proposed direction, eight decision points), `docs/REPO_CLEANUP_PROPOSAL.md` (for decision, nothing moved yet) and the `experiments/2026-09-pdf-inspector-trial/` scaffold. Marked the Java sidecar references superseded. WeedSeedWizard-py `dev` was merged to `main` the same day. Proposed, not agreed: labels as cited agent context, optimiser deferred, extraction route chosen by the trial.
- **2026-09-21:** Refined the development plan to make Weed Seed Wizard the sole primary simulation engine. RIM is now an optional future economic comparator and is removed from the MVP critical path. No implementation work was started.
- **2026-09-21:** Audited the current WeedAI, `DPIRD-FSI/WeedSeedWizard-py`, and `00113844/RIM-Online` boundaries and added `AGENTIC_WEED_MANAGEMENT_DEVELOPMENT_PLAN.md`. The plan defines a local-first modular architecture, versioned Pydantic contracts, canonical `RegisteredUse` knowledge model, framework-neutral WSW/RIM adapters, deterministic multi-objective recommendation pipeline, agent safety boundary, and phased path to an online service. Key integration gates: WSW remains parity/integration incomplete; RIM's public CLI currently targets the older engine rather than the evidence-backed `rim.calcs` path.
- **2026-09-16:** Resumed after 8 months. Committed `data/parsed-clean` (386), `data/extracted` (51) and `data/extracted-from-md` (160) to git with an allow-list `.gitignore` and `data/README.md`. Fixed push (origin → HTTPS via `gh`). Reconciled `CLAUDE.md`, this roadmap, `TODOS.md` and `CHANGELOG.md` with the actual repo state (guardrails is a stub; no workspace root; two extraction schemas). Established Claude Code project memory. Next blocker: choose the canonical extraction schema.
- **2026-01-09:** Implemented basic GraphRAG (chunker, chunk_loader, vector search). Identified schema limitation - flat Chunk model doesn't support agronomic queries. Created schema redesign TODO with RegisteredUse pattern.
- **2026-01-08:** Restarted Gemini markdown extraction in 50-file batches and began reverse-engineering the Apparent compatibility matrix.

---

### Phase 1: Infrastructure ✅ COMPLETE
- [x] Per-package `pyproject.toml` (Hatchling) installable with `uv pip install -e` — a root uv workspace was planned but never created (see Known repo debt)
- [x] Environment Setup: `.env` with Neo4j AuraDB credentials
- [x] Neo4j AuraDB connection established (instance: `81fbf7d8`)
- [x] Pydantic settings for configuration

---

### Phase 2: Data Pipeline ⚠️ 90% COMPLETE
- [x] **PDF Collection:** 386 herbicide labels from APVMA
- [x] **PDF Parsing (PyMuPDF4LLM):** All labels → markdown with YAML frontmatter
- [x] **PDF Parsing (Docling):** All labels → JSON with table extraction
- [x] **Document Cleaning:** `cleaner.py` removes noise (12.3% size reduction)
- [x] **Chunk Generation:** `chunker.py` creates structure-aware chunks from Docling JSON
- [ ] **Entity Extraction:** two partial runs with **incompatible schemas** — must converge on one
  - `data/extracted/` — 51/386 via `ingestion.extractor` (`HerbicideLabel`; the only schema `load-graph` reads)
  - `data/extracted-from-md/` — 160/386 via `scripts/markdown_to_graph.py` (`usage_scenarios`, HRAC numeric MoA; no loader)
  - **Option A:** Standardise on `HerbicideLabel`, resume `extractor` for the remaining 335 (`--limit 50 --delay 1.0`)
  - **Option B:** Standardise on `usage_scenarios`, write a loader, resume for the remaining 226
  - **Option C:** Skip both; extract straight into the Phase 3 `RegisteredUse` schema with `neo4j-graphrag-python` SimpleKGPipeline (recommended — avoids a second migration)

---

### Phase 3: Schema Design 🔴 CRITICAL PATH

> **Current Problem:** The flat schema (Herbicide → CONTROLS → Weed) doesn't support real agronomic queries like:
> - "What controls ryegrass in wheat at 3-leaf stage?"
> - "What's the withholding period before grazing?"
> - "What rate for barley grass in canola?"

#### 3.1 Current Schema (Insufficient)
```
Herbicide -[CONTROLS]-> Weed
Herbicide -[REGISTERED_FOR]-> Crop
Document -[CONTAINS_CHUNK]-> Chunk (with embedding)
```

#### 3.2 Target Schema (RegisteredUse Pattern)
```yaml
# packages/graph/schema/agronomic_schema.yaml
node_types:
  - Product          # Herbicide product identity
  - ActiveIngredient # Chemical actives with concentrations
  - ModeOfAction     # Resistance groups (A-Z)
  - RegisteredUse    # CENTRAL HUB - links product to agronomic context
  - Crop             # Target crop with type (cereal/legume/etc)
  - Weed             # Target weed with lifecycle
  - GrowthStage      # Crop/weed timing constraints
  - ApplicationRate  # Rate, water volume, method
  - Restriction      # Withholding, re-cropping, buffer zones

relationship_types:
  - CONTAINS         # Product -> ActiveIngredient
  - HAS_MOA          # Product -> ModeOfAction
  - HAS_USE          # Product -> RegisteredUse (one product, many uses)
  - FOR_CROP         # RegisteredUse -> Crop
  - CONTROLS         # RegisteredUse -> Weed (with efficacy, max_stage)
  - AT_TIMING        # RegisteredUse -> GrowthStage
  - HAS_RATE         # RegisteredUse -> ApplicationRate
  - WITH_RESTRICTION # RegisteredUse -> Restriction
  - COMPATIBLE_WITH  # Product <-> Product (tank mix)
  - ROTATE_WITH      # ModeOfAction <-> ModeOfAction (resistance mgmt)

patterns:
  - [Product, HAS_USE, RegisteredUse]
  - [RegisteredUse, FOR_CROP, Crop]
  - [RegisteredUse, CONTROLS, Weed]
  - [RegisteredUse, AT_TIMING, GrowthStage]
  - [RegisteredUse, HAS_RATE, ApplicationRate]
  - [RegisteredUse, WITH_RESTRICTION, Restriction]
```

#### 3.3 Tasks
- [ ] **Design:** Finalize `agronomic_schema.yaml` with node/relationship properties
- [ ] **Migrate:** Create migration script for existing chunks
- [ ] **Validate:** Test schema with sample queries
- [ ] **Document:** Update wiki with new schema ERD

---

### Phase 4: Entity Extraction ⏸️ BLOCKED

> **Blocked by:** Phase 3 schema design

#### 4.1 Recommended Approach: neo4j-graphrag-python

```python
# Use official Neo4j GraphRAG package for LLM-based extraction
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from neo4j_graphrag.llm import OpenAILLM

kg_builder = SimpleKGPipeline(
    llm=OpenAILLM(model_name="gpt-4o"),
    driver=driver,
    schema=agronomic_schema,  # From Phase 3
    from_pdf=False,
    perform_entity_resolution=True,  # Deduplication!
    on_error="IGNORE"
)

# Process each Docling chunk
for chunk in chunks:
    await kg_builder.run_async(text=chunk.text)
```

#### 4.2 Tasks
- [ ] **Install:** `uv add neo4j-graphrag --package graph`
- [ ] **Configure:** Create extraction pipeline with agronomic schema
- [ ] **Extract:** Process all 386 Docling JSON files
- [ ] **Validate:** Spot-check entity resolution quality

---

### Phase 5: Retrieval Layer ⚠️ BASIC WORKING

#### 5.1 Current State
- [x] Vector index created (768d, cosine similarity)
- [x] 184 chunks loaded with embeddings
- [x] Basic `search_chunks()` working
- [x] LangGraph tools defined (vector_search_tool, graph_traversal_tool)

#### 5.2 Target State: HybridCypherRetriever

```python
# Use official Neo4j retriever for hybrid search
from neo4j_graphrag.retrievers import HybridCypherRetriever

retriever = HybridCypherRetriever(
    driver=driver,
    vector_index_name="chunk_embeddings",
    fulltext_index_name="chunk_fulltext",
    embedder=embedder,
    retrieval_query="""
        MATCH (chunk)-[:FROM_USE]->(use:RegisteredUse)
        MATCH (use)-[:FOR_CROP]->(crop:Crop)
        MATCH (use)-[:CONTROLS]->(weed:Weed)
        RETURN chunk.text, crop.name, weed.common_name, use.rate
    """
)
```

#### 5.3 Tasks
- [ ] **Upgrade:** Replace custom `hybrid_search()` with `HybridCypherRetriever`
- [ ] **Fulltext Index:** Add fulltext index for keyword search
- [ ] **Retrieval Queries:** Write agronomic-specific Cypher for graph traversal
- [ ] **Testing:** Benchmark retrieval quality on sample queries

---

### Phase 6: Orchestration (LangGraph) ⏸️ NOT STARTED

> **Blocked by:** Phase 5 retrieval layer

#### 6.1 Architecture

```
User Query
    ↓
[Input Guardrail] ─── NeMo topical filter
    ↓
[Router Node] ─── Classify: factual / recommendation / simulation
    ↓
┌───────────────────────┬─────────────────────────┬──────────────────────┐
│   Factual Query       │   Recommendation        │   Simulation         │
│   (RAG retrieval)     │   (Multi-hop graph)     │   (WSW-py adapter)   │
│                       │                         │                      │
│   HybridRetriever     │   Graph traversal +     │   Subprocess call    │
│   → LLM synthesis     │   MOA rotation logic    │   → result parsing   │
└───────────────────────┴─────────────────────────┴──────────────────────┘
    ↓
[Output Guardrail] ─── Validate agronomic safety
    ↓
Response
```

#### 6.2 Tasks
- [ ] **State Definition:** Define `AgentState` with messages, context, tool_calls
- [ ] **Tools:** Wrap retrievers as LangGraph tools with Pydantic schemas
- [ ] **Nodes:** Implement router, retriever, synthesizer nodes
- [ ] **Workflow:** Compile graph with checkpointer for persistence
- [ ] **API:** Expose via FastAPI with streaming support

---

### Phase 7: Guardrails ⏸️ NOT STARTED

#### 7.1 NeMo Guardrails (Topical Filtering)
```colang
# packages/guardrails/config/rails.co
define user ask about herbicides
  "What herbicide controls ryegrass?"
  "Best spray for wild oats in wheat?"

define user ask off topic
  "What's the weather today?"
  "Tell me a joke"

define flow
  user ask off topic
  bot refuse and redirect
    "I'm specialized in herbicide recommendations. How can I help with weed management?"
```

#### 7.2 LangGraph Validation (Human-in-the-Loop)
```python
from langgraph.types import interrupt

def validate_recommendation(state):
    if state.recommendation.risk_level == "HIGH":
        # Pause for human review
        human_response = interrupt({
            "query": "High-risk recommendation requires approval",
            "recommendation": state.recommendation
        })
        return {"approved": human_response["approved"]}
    return {"approved": True}
```

#### 7.3 Tasks
- [ ] **NeMo Config:** Define topical rails in Colang
- [ ] **Input Rails:** Filter off-topic, medical, political queries
- [ ] **Output Rails:** Validate agronomic safety (rates, withholding periods)
- [ ] **HITL:** Implement interrupt pattern for high-risk recommendations
- [ ] **Testing:** Create test suite for guardrail scenarios

---

### Phase 8: Frontend & Deployment ⏸️ NOT STARTED

- [ ] Next.js app initialization
- [ ] Chat interface with streaming
- [ ] Map visualization (paddock/field context)
- [ ] Docker Compose for local dev
- [ ] GCP deployment (Cloud Run + AuraDB)

---

## 5. Immediate Next Steps (Priority Order)

> **Under review (2026-09-25).** The plan orders the work contracts, then deterministic core, then agent, and the table below predates it. Proposed replacement, pending agreement (`docs/ALIGNMENT_2026-09.md` §4):
> 1. Agree scope and the decision points in `docs/ALIGNMENT_2026-09.md`.
> 2. Run the extraction trial on the WA wheat and annual ryegrass labels (`experiments/2026-09-pdf-inspector-trial/`) and pick the text layer by measurement.
> 3. Agree one citable use-record schema (trial `schema_draft.py` is a starting point) and re-extract the pilot set; check it against the PDFs.
> 4. Scale re-extraction; retire `data/extracted/` and `data/extracted-from-md/`.
> 5. Retrieval with citations, then the agent loop, per the plan's phases.
>
> Rows 1, 4 and 5 below (SimpleKGPipeline, `test_subsample_30.txt`) are on hold until the trial reports.

| # | Task | Owner | Est. Time |
|---|------|-------|-----------|
| 1 | **Decide the canonical extraction schema** (Phase 2 options A/B/C above). Recommendation: C — extract directly into the `RegisteredUse` schema so the 51/160 partial runs are not migrated twice. Record the decision here and in `TODOS.md`. | - | 1h |
| 2 | Finalize `agronomic_schema.yaml` (Phase 3.2) with node/relationship properties | - | 2h |
| 3 | Install `neo4j-graphrag-python` into `../.venv` (`uv pip install neo4j-graphrag`) | - | 30m |
| 4 | Create SimpleKGPipeline extraction script reading `data/parsed-clean` (or Docling chunks) | - | 4h |
| 5 | Run extraction on the 30-file subsample (`test_subsample_30.txt`) | - | 1h |
| 6 | Validate entity resolution quality; spot-check against source PDFs | - | 2h |
| 7 | Scale extraction to all 386 files; commit outputs under `data/` | - | 4h |
| 8 | Implement HybridCypherRetriever + fulltext index (Phase 5.3) | - | 3h |
| 9 | Create LangGraph workflow skeleton (Phase 6.2) | - | 4h |

### Known repo debt (not blocking, fix opportunistically)
- `data/labels/*.pdf` (386 files, 169 MB) are tracked despite `*.pdf` in `.gitignore` — every clone pulls them. Untracking (`git rm --cached`) would shrink future clones; history keeps them either way.
- Two virtualenvs: `../.venv` (3.12, working, has everything) and `packages/ingestion/.venv` (3.11, stale). Delete the stale one.
- No root `pyproject.toml` — the "uv workspace" in this doc was never created; packages install individually.
- `packages/guardrails` pins `nemo-guardrails==0.10.0`, which is not on PyPI; the package has no source yet.
- `test_subsample.sh` / `SUBSAMPLE_TEST.md` hard-code macOS paths (`/Users/dpird-mac/...`) and `brew`; they need a Windows/cross-platform pass before reuse.
- `_wiki_temp/` is a git submodule pointer to the GitHub wiki clone; `wiki/` duplicates its pages. Pick one.
- `packages/ingestion/search-results.csv` is tracked; unclear if it is still needed.

---

## 6. Best Practices & Standards

### GraphRAG Best Practices (from neo4j-graphrag-python)
- **Schema-driven extraction:** Define node_types, relationship_types, patterns upfront
- **Entity resolution:** Enable `perform_entity_resolution=True` to deduplicate
- **Hybrid retrieval:** Combine vector + fulltext + graph traversal
- **Chunking:** Use structure-aware chunking (tables, sections) not arbitrary splits

### LangGraph Best Practices
- **Tool-based retrieval:** Wrap retrievers as tools with Pydantic schemas
- **Checkpointing:** Use `MemorySaver` or `PostgresSaver` for persistence
- **Streaming:** Enable streaming for real-time UX
- **Human-in-the-loop:** Use `interrupt()` for high-stakes decisions

### Testing Commands
```bash
# Run graph package tests
cd packages/graph && pytest tests/ -v

# Test vector search
python -c "from graph import search_chunks; print(search_chunks('ryegrass', k=3))"

# Validate schema
python -c "from graph import init_schema; init_schema()"
```
