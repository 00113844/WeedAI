# WeedAI To-Do List

## 🔴 HIGH PRIORITY: Graph Schema Redesign

The current flat schema doesn't capture the rich agronomic relationships in herbicide labels. Need a hierarchical structure that supports queries like:
- "What herbicides control ryegrass in wheat at 3-leaf stage?"
- "What's the withholding period before grazing?"
- "What rotation options avoid Group A resistance?"
- "Can I tank mix Product X with glyphosate?"

### Proposed Schema Architecture

#### Layer 1: Product Identity
```
Product {product_number PK, product_name, formulation_type, registrant}
  └─ CONTAINS → ActiveIngredient {name, concentration_g_L, concentration_percent}
  └─ HAS_MOA → ModeOfAction {group PK, description, resistance_risk}
  └─ HAS_REGISTRATION → Registration {apvma_number, approval_date, states[]}
```

#### Layer 2: Registered Use (CENTRAL - enables agronomic queries)
```
RegisteredUse {use_id PK} - The key entity linking product to agronomic context
  ├─ FOR_CROP → Crop {name, type: cereal|legume|oilseed|pasture}
  ├─ CONTROLS → Weed {common_name, scientific_name, lifecycle: annual|perennial}
  │     └─ relationship props: {efficacy: S|MS|MR|R, max_growth_stage, critical_comments}
  ├─ IN_STATE → State {code, name}
  ├─ HAS_RATE → ApplicationRate {rate_per_ha, water_rate, method: boom|aerial|spot}
  ├─ AT_TIMING → GrowthStage {crop_stage, weed_stage, timing_window}
  └─ WITH_RESTRICTION → Restriction {type, value, unit}
       └─ Types: withholding_grazing, withholding_harvest, re_cropping, buffer_zone
```

#### Layer 3: Compatibility & Rotation
```
Product ─[COMPATIBLE_WITH {confidence, source}]→ Product
Product ─[INCOMPATIBLE_WITH {reason, source}]→ Product
ModeOfAction ─[ROTATE_WITH]→ ModeOfAction  # Resistance management
```

#### Layer 4: Document RAG (semantic search layer)
```
Product ─[HAS_LABEL]→ LabelDocument {source_file, version, effective_date}
  └─ HAS_SECTION → Section {type: directions|safety|compatibility|storage, page_range}
       └─ HAS_CHUNK → Chunk {chunk_id PK, text, embedding[768], sequence}
            └─ MENTIONS → Entity (Weed|Crop|Product)  # Entity linking
            └─ NEXT → Chunk  # Reading order
```

### Schema Benefits
| Query Type | Current Schema | Proposed Schema |
|------------|----------------|-----------------|
| "Ryegrass in wheat at 3-leaf" | ❌ Can't filter by growth stage | ✅ RegisteredUse → AT_TIMING |
| "Withholding before grazing" | ❌ Not captured | ✅ RegisteredUse → WITH_RESTRICTION |
| "Tank mix compatible" | ❌ No compatibility data | ✅ Product → COMPATIBLE_WITH |
| "MOA rotation options" | ⚠️ Manual | ✅ ModeOfAction → ROTATE_WITH |
| "Semantic search labels" | ✅ Chunk search | ✅ Chunk search + entity context |

### Implementation Tasks
- [ ] **Design**: Finalize RegisteredUse entity structure and relationship props
- [ ] **Extract**: Update ingestion to parse growth stages, withholding periods, restrictions from label text
- [ ] **Migrate**: Create migration script to transform existing Chunk data to new schema
- [ ] **Loader**: Update chunk_loader.py to populate RegisteredUse relationships
- [ ] **Queries**: Add agronomic query functions (find_use_for_weed_in_crop, get_withholding_periods, etc.)
- [ ] **Compatibility**: Ingest Apparent compatibility chart into Product→COMPATIBLE_WITH relationships

---

## Extraction Pipeline
- [ ] **Decide the canonical extraction schema first** (see `roadmap.md` § Immediate Next Steps #1). The two existing runs are incompatible:
  - `data/extracted/` — 51/386 in `HerbicideLabel` schema (`ingestion.extractor`); remaining 335. This is the only schema `load-graph` reads.
  - `data/extracted-from-md/` — 160/386 in `usage_scenarios` schema (`scripts/markdown_to_graph.py`); remaining 226. No loader.
  - Recommended: skip both and extract straight into the Phase 3 `RegisteredUse` schema with `neo4j-graphrag` SimpleKGPipeline.
- [ ] Once decided, resume extraction in batches within Gemini quota (`--limit 50 --delay 1.0`) and commit outputs under `data/`.
- [ ] Investigate markdown files with insufficient content and decide whether to re-parse their source PDFs or drop them (no `_extraction_summary.json` exists on disk any more — regenerate it from the chosen extractor's run).
- [x] Remove the empty duplicate `data/parsed-clean` directory outside the repo root (done 2026-09-16).
- [x] Commit `data/parsed-clean`, `data/extracted`, `data/extracted-from-md` to git (done 2026-09-16; `data/README.md` documents each dir).

## Data Quality
- [ ] Spot-check newly generated JSON in `data/extracted` to confirm crop/weed coverage and rate fidelity before bulk loading.
- [ ] Update `_extraction_summary.json` after each extraction batch to track progress and remaining pending files.
- [ ] Backfill missing `rate_per_ha` details by refining extractor prompts or post-processing heuristics.

## Compatibility Matrix
- [ ] Digitize the Apparent compatibility chart into structured compatibility/incompatibility pairs with legend color mapping.
- [ ] Link compatibility outcomes back into herbicide JSON (e.g., `compatible_products` / `incompatible_products`).

## GraphRAG Integration
- [ ] Ingest the expanded JSON set into Neo4j once extraction is complete, refreshing constraints and indexes as needed.
- [ ] Implement hybrid retrieval combining Neo4j vector indexes (`db.index.vector.queryNodes`) with Cypher lookups for GraphRAG queries.
- [ ] Document the hybrid retriever flow (vector + structured query) alongside guardrail entry points for LangGraph orchestration.
