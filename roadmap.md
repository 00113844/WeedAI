# WeedAI Project Roadmap

> **Last Updated:** 2026-01-09  
> **Status:** Phase 3 In Progress - Schema Redesign Required

## 1. Project Overview
**WeedAI** is an agronomic AI system (reactive agents) designed to assist agronomists with decision making on integrated weed management (herbicide) management. It leverages a multi-agent architecture with domain-specific guardrails, a knowledge graph (GraphRAG), and a legacy simulation weed seed ecological model. 

## 2. Tech Stack

### Current Stack
| Component | Technology | Status |
|-----------|-----------|--------|
| **Language** | Python 3.11+ | ✅ Active |
| **Package Manager** | `uv` (Workspace mode) | ✅ Active |
| **Vector DB** | Neo4j AuraDB (768d embeddings) | ✅ Connected |
| **Embeddings** | sentence-transformers/all-mpnet-base-v2 | ✅ Working |
| **PDF Parsing** | PyMuPDF4LLM + Docling | ✅ 386 labels parsed |
| **LLM Extraction** | Gemini 2.5 Flash | ⚠️ Limited (API quota) |

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
│   └── simulation-sidecar/     # Legacy Java Wrapper (Phase 6)
├── packages/
│   ├── core/                   # Shared Utilities & DB Connections
│   ├── graph/                  # Neo4j Schema, Loaders, RAG Queries ✅
│   ├── ingestion/              # PDF Parsing, Cleaning, Extraction ✅
│   └── guardrails/             # NeMo Guardrails Config (Phase 5)
├── data/
│   ├── labels/                 # Source PDFs (386 files)
│   ├── docling/                # Docling JSON outputs (386 files) ✅
│   ├── parsed-clean/           # Cleaned markdown (388 files) ✅
│   └── extracted/              # Structured JSON (22 files) ⚠️
└── pyproject.toml              # Workspace Root
```

## 4. Development Roadmap

### Progress Summary

| Phase | Name | Status | Blocker |
|-------|------|--------|---------|
| 1 | Infrastructure | ✅ Done | - |
| 2 | Data Pipeline | ⚠️ 90% | API quota for extraction |
| 3 | Schema Design | 🔴 **CRITICAL** | Flat schema doesn't support agronomic queries |
| 4 | Entity Extraction | ⏸️ Blocked | Waiting for schema redesign |
| 5 | Retrieval Layer | ⚠️ Basic | Needs HybridCypherRetriever upgrade |
| 6 | Orchestration | ⏸️ Not Started | Waiting for retrieval layer |
| 7 | Guardrails | ⏸️ Not Started | Waiting for orchestration |
| 8 | Frontend | ⏸️ Not Started | Waiting for API |

---

### Daily Diary
- **2026-01-09:** Implemented basic GraphRAG (chunker, chunk_loader, vector search). Identified schema limitation - flat Chunk model doesn't support agronomic queries. Created schema redesign TODO with RegisteredUse pattern.
- **2026-01-08:** Restarted Gemini markdown extraction in 50-file batches and began reverse-engineering the Apparent compatibility matrix.

---

### Phase 1: Infrastructure ✅ COMPLETE
- [x] Initialize `uv` Workspace with workspace members
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
- [ ] **Entity Extraction:** 22/386 files extracted (Gemini quota limited)
  - **Option A:** Wait for quota reset, run in batches
  - **Option B:** Use `neo4j-graphrag-python` SimpleKGPipeline (recommended)

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
│   (RAG retrieval)     │   (Multi-hop graph)     │   (Java sidecar)     │
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

| # | Task | Owner | Est. Time |
|---|------|-------|-----------|
| 1 | Finalize `agronomic_schema.yaml` | - | 2h |
| 2 | Install `neo4j-graphrag-python` | - | 30m |
| 3 | Create SimpleKGPipeline extraction script | - | 4h |
| 4 | Run extraction on 10 test files | - | 1h |
| 5 | Validate entity resolution quality | - | 2h |
| 6 | Scale extraction to all 386 files | - | 4h |
| 7 | Implement HybridCypherRetriever | - | 3h |
| 8 | Create LangGraph workflow skeleton | - | 4h |

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
