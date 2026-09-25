# Agentic Herbicide and Weed Management Decision Support System

> Development plan for a local-first research and teaching system that can later be deployed as an online decision-support service.
>
> Status: proposed architecture  
> Date: 2026-09-21  
> Scope: WeedAI + WeedSeedWizard-py + APVMA-derived herbicide knowledge; RIM-Online is an optional future comparator

## Executive summary

Build the system as a set of deterministic, versioned domain services with an agent at the outside, not as an agent that contains the agronomy. The language model may translate a grower question into typed data, choose among approved tools, and explain results. It must not invent product rates, relax label constraints, or substitute narrative reasoning for model execution.

The recommended architecture extends the current WeedAI repository rather than replacing it:

- preserve `packages/ingestion` and `packages/graph`;
- add a root `uv` workspace and small packages for domain contracts, knowledge access, simulation adapters, optimization, and orchestration;
- make one canonical `RegisteredUse` contract the boundary between label extraction, retrieval, optimization, and recommendations;
- use Weed Seed Wizard as the primary simulation engine behind a framework-neutral `Protocol` and Pydantic request/response envelopes;
- use exact structured label facts for eligibility, rate, timing, state, crop, withholding and plant-back checks; use semantic retrieval only to find supporting passages;
- use a deterministic recommendation pipeline with a human-review gate for high-risk or incomplete cases;
- keep local and online deployments behaviorally identical by changing adapters and infrastructure, not domain logic.

### Current-state findings that change the sequence

1. WeedAI already has 386 cleaned labels, two partial but incompatible extraction schemas, a Neo4j graph package, and preliminary retrieval tools. The immediate knowledge task is schema convergence and data-quality validation, not a new ingestion pipeline.
2. `WeedSeedWizard-py` has a useful Pydantic scenario format, CLI and minimal FastAPI surface, but the port is still incomplete. Weather/soil and early seed work exist; full plants, management-event handling and end-to-end Java parity are not yet complete. Its adapter must publish capabilities and refuse unsupported decision runs.
3. Weed Seed Wizard is therefore the primary and sufficient engine for the first system. RIM-Online may be integrated later as an optional annual-ryegrass economic comparator, but it is not on the critical path and its absence must not block the local pilot or online migration.
4. WSW results require a `validation_status` and model provenance. Results marked `experimental`, `partial`, `parity_pending` or `unsupported` may be displayed in a research view but must not drive an agronomic recommendation.

## Architectural principles

1. **Labels are legal constraints, not prose suggestions.** Candidate generation starts from registered uses and fails closed when a required label field is missing.
2. **Models are versioned evidence.** Every result records repository, commit, model/equation version, parameter version, run mode and input hash.
3. **One canonical domain language.** WSW, label extraction, the optimizer and the UI exchange common models rather than each other's internal dictionaries. This boundary also permits an optional future engine without redesign.
4. **Pure core, impure edges.** Domain validation, scoring and strategy construction are deterministic. File access, databases, subprocesses, HTTP and LLM calls sit behind ports.
5. **The agent cannot bypass policy.** Tool access is narrower than internal service access, and the final recommendation validator runs after the agent.
6. **Local first does not mean throwaway.** The local CLI and online API call the same application services and produce the same versioned JSON contracts.
7. **Scientific parity before product polish.** A visually plausible output is not an acceptance criterion for WSW.
8. **Uncertainty is first-class.** Unknown weed identity, resistance status, efficacy, weather or prices are represented explicitly and propagated into results.

---

# 1. System Architecture & Project Scaffolding

## 1.1 Logical architecture

```text
Student examples / CLI / future web UI
                  |
            Application API
                  |
       Question intake + validation
                  |
          Deterministic agent graph
     parse -> retrieve -> simulate -> optimize
                  |
       recommendation verification gate
              /                 \
     Herbicide KB           WSW adapter
     structured +           primary multi-species
     cited evidence         seedbank engine
              \                 /
             canonical domain models
                       |
          optional future RIM comparator
                  |
       audit log + reproducible run store
```

The optimizer owns candidate ranking. The agent owns workflow coordination and explanation. The models own simulation. The knowledge engine owns label facts and citations.

## 1.2 Proposed repository layout

```text
WeedAI/
├── pyproject.toml                    # uv workspace; shared Python/tool settings
├── uv.lock                           # one reproducible workspace lock
├── AGENTIC_WEED_MANAGEMENT_DEVELOPMENT_PLAN.md
├── .specify/                         # Spec-Kit project rules and constitution
├── specs/
│   ├── 001-domain-contracts/
│   ├── 002-herbicide-registered-use/
│   ├── 003-wsw-adapter/
│   ├── 004-rim-adapter/
│   ├── 005-recommendation-engine/
│   └── 006-agent-workflow/
├── apps/
│   ├── cli/                          # local batch runs and student exercises
│   ├── api/                          # FastAPI; thin application boundary
│   ├── worker/                       # online simulation/optimization jobs
│   └── web/                          # later browser interface
├── packages/
│   ├── domain/                       # zero infrastructure dependencies
│   │   └── src/weedai_domain/
│   │       ├── models/               # Pydantic contracts requested below
│   │       ├── enums.py
│   │       ├── units.py
│   │       ├── errors.py
│   │       └── policies.py
│   ├── simulations/
│   │   └── src/weedai_simulations/
│   │       ├── tools/
│   │       │   ├── base.py           # SimulationTool protocol
│   │       │   ├── wsw/
│   │       │   │   ├── adapter.py
│   │       │   │   ├── mapping.py
│   │       │   │   ├── parser.py
│   │       │   │   └── capabilities.py
│   │       │   └── rim/
│   │       │       ├── adapter.py
│   │       │       ├── mapping.py
│   │       │       ├── parser.py
│   │       │       └── capabilities.py
│   │       ├── cache.py
│   │       └── provenance.py
│   ├── knowledge/
│   │   └── src/weedai_knowledge/
│   │       ├── wiki/                 # front matter, Markdown, validation
│   │       ├── registered_use/       # canonical label projection
│   │       ├── retrieval/            # structured, lexical, vector, graph
│   │       ├── citations.py
│   │       └── stores/               # in-memory test + Neo4j implementations
│   ├── optimization/
│   │   └── src/weedai_optimization/
│   │       ├── optimizers/
│   │       │   ├── candidate_generator.py
│   │       │   ├── constraint_filter.py
│   │       │   ├── evaluator.py
│   │       │   ├── pareto.py
│   │       │   └── alternatives.py
│   │       ├── objectives.py
│   │       ├── resistance.py
│   │       └── uncertainty.py
│   ├── agents/
│   │   └── src/weedai_agents/
│   │       ├── agents/
│   │       │   ├── intake.py
│   │       │   ├── planner.py
│   │       │   ├── evidence.py
│   │       │   ├── simulation.py
│   │       │   └── explainer.py
│   │       ├── graph.py
│   │       ├── state.py
│   │       ├── tools.py              # thin framework-specific façades only
│   │       └── prompts/
│   ├── evaluation/
│   │   └── src/weedai_evaluation/    # golden cases, safety and RAG evaluation
│   ├── ingestion/                    # existing; gradually emit canonical records
│   ├── graph/                        # existing Neo4j implementation
│   ├── guardrails/                   # existing stub; implement after core policy
│   └── core/                         # shared config, logging, DB/run repositories
├── data/
│   ├── source/                       # immutable label inputs and checksums
│   ├── parsed-clean/                 # current cleaned Markdown
│   ├── canonical/                    # validated RegisteredUse JSONL/Parquet
│   ├── indexes/                      # reproducible local indexes; usually ignored
│   └── reference/                    # weed aliases, crops, MoA mappings, units
├── examples/
│   ├── reference/                    # maintainer-approved example cases
│   └── student/                      # one directory per submitted scenario
├── tests/
│   ├── contract/
│   ├── integration/
│   ├── end_to_end/
│   ├── safety/
│   └── fixtures/
└── deployments/
    ├── local/                        # compose/profile for local infrastructure
    └── online/                       # container and infrastructure definitions
```

### Why separate packages

The package boundaries enforce this dependency direction:

```text
apps -> agents -> optimization -> simulations/knowledge -> domain
                  knowledge -----------------------------> domain
                  simulations ---------------------------> domain
```

`domain` imports no database, agent framework or external model. `simulations` does not import LangChain/LangGraph. `knowledge` does not know how a recommendation is scored. This lets the team replace the agent framework, database or deployment mechanism without rewriting agronomic contracts.

## 1.3 Python and dependency management

Use Python 3.12 for the WeedAI workspace after confirming WSW tests cleanly on it. Retain `>=3.11` compatibility for libraries where practical. Adopt `uv` because the repository already uses it and a workspace provides one lockfile while preserving per-package `pyproject.toml` files.

Root configuration shape:

```toml
[project]
name = "weedai-workspace"
version = "0.1.0"
requires-python = ">=3.12,<3.13"

[tool.uv.workspace]
members = ["apps/*", "packages/*"]

[dependency-groups]
dev = [
  "pytest>=8",
  "pytest-xdist",
  "pytest-cov",
  "hypothesis",
  "ruff",
  "mypy",
]

[tool.pytest.ini_options]
testpaths = ["tests", "packages/*/tests", "apps/*/tests"]
markers = [
  "contract: versioned boundary tests",
  "parity: scientific reference comparisons",
  "integration: database or subprocess tests",
  "online: external service tests",
]
```

Each package declares only its own runtime dependencies. Internal dependencies use workspace sources. Do not install WSW from an unpinned branch in decision-grade environments; use a commit SHA or a released package version. Apply the same rule if RIM is added later.

## 1.4 Application services

Define use cases independently of CLI/API/UI:

- `ValidateCase`: parse files, normalize aliases, identify missing fields and return a validation report.
- `RunBaseline`: execute the applicable validated model(s) without changing the submitted plan.
- `GenerateCandidates`: retrieve legally eligible registered uses and non-chemical tactics.
- `EvaluateStrategies`: run simulation batches, uncertainty analysis and objective calculation.
- `RecommendStrategy`: select a Pareto set, verify constraints and create a recommendation record.
- `ExplainRecommendation`: generate a plain-language view only from the verified record and cited evidence.
- `CompareCases`: support student and researcher comparisons without invoking an LLM.

## 1.5 Local and online profiles

| Concern | Local teaching/research | Online service |
|---|---|---|
| Entry point | CLI and optional local FastAPI | versioned REST API + web UI |
| Model execution | in-process or isolated subprocess | worker queue; one container/image per model version |
| Knowledge store | in-memory test store or local Neo4j | managed Neo4j/Postgres-backed store |
| Files | repository examples and user-selected paths | object storage IDs; never arbitrary server paths |
| Run state | JSON artifacts under `.runs/` | database + object storage |
| Auth | none on localhost | institution identity, roles, audit identity |
| LLM | optional; system usable without it | provider adapter with data policy and quotas |
| Caching | content-addressed local cache | shared content-addressed cache |

Online migration must not introduce new domain models. It replaces `RunRepository`, `KnowledgeStore`, `SimulationExecutor`, `ObjectStore` and `Checkpointer` implementations.

## 1.6 Agent framework choice

Use LangGraph for the first production orchestration because the workflow needs explicit state, conditional routing, durable checkpoints and human-review interrupts. Keep it behind `packages/agents` and call framework-neutral application services. This preserves the option to use a native function-calling loop or another framework later without changing model, knowledge or optimization packages.

Do not begin with a society of conversational specialist agents. One constrained graph with typed nodes is easier to test and audit. Split a node into a separate agent only when it has an independent context, tool set, evaluation suite and failure boundary.

---

# 2. Spec-Kit & Data Contracts

## 2.1 Spec-driven workflow

Adopt Spec-Kit in the existing repository, not as a re-generation exercise. Create one root constitution and a bounded spec for each contract or integration slice.

The project constitution should require:

1. label constraints are hard constraints and include citations;
2. no scientific model is recommendation-grade without approved parity fixtures;
3. public data contracts are versioned and backward compatibility is tested;
4. every recommendation is reproducible from stored inputs, model versions and knowledge snapshot;
5. the system fails closed on missing crop, weed, state, timing, rate or resistance data;
6. high-risk output requires an agronomist/reviewer acknowledgement;
7. LLM output is never the sole source of a rate, legal eligibility or simulated metric.

Each `specs/NNN-feature/` should contain:

```text
spec.md           # user stories, requirements, acceptance scenarios, exclusions
plan.md           # architecture and reuse of existing code
research.md       # source repositories, model limitations, agronomic references
data-model.md     # Pydantic and persistence models
contracts/        # JSON Schema/OpenAPI/examples
quickstart.md     # executable local example
tasks.md          # small ordered implementation units
```

First specs:

- `001-domain-contracts`: quantities, paddock, weeds, resistance, events, provenance and result envelopes;
- `002-registered-use`: canonical label schema and extraction migration;
- `003-wsw-adapter`: WSW inputs, capabilities, execution, parity status and output mapping;
- `005-recommendation-engine`: constraints, objectives, alternatives and audit record;
- `006-agent-workflow`: state machine, tool policy, interrupts and rendering.

Create `004-rim-adapter` only if the optional comparator is later approved; it is not part of the MVP specification set.

## 2.2 Contract conventions

Every external payload uses an envelope:

```python
class ContractEnvelope[T](BaseModel):
    schema_name: str
    schema_version: str
    payload: T
    created_at: datetime
    source: SourceReference | None = None
```

Rules:

- semantic versions for public contracts;
- `extra="forbid"` at model boundaries;
- ISO 8601 dates and datetimes;
- `Decimal` for prices and application quantities; floats are acceptable for scientific arrays when the underlying model uses floating point;
- explicit units, never encoded only in field names;
- stable identifiers separate from human names;
- discriminated unions for events and tactics;
- `unknown` is a valid explicit state; empty strings are not;
- JSON Schema snapshots committed under `contracts/` and checked in CI;
- additive fields only within a minor version; renamed/removed/semantic changes require a major version and migration.

## 2.3 Core Pydantic models

The following is an architectural contract sketch rather than final implementation code.

```python
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

class Quantity(ContractModel):
    value: Decimal
    unit: Literal[
        "L/ha", "mL/ha", "g/ha", "kg/ha", "mm", "t/ha",
        "plants/m2", "seeds/m2", "AUD/ha", "day"
    ]

class ValueRange(ContractModel):
    minimum: Quantity
    maximum: Quantity

class SourceCitation(ContractModel):
    source_id: str
    document_sha256: str
    apvma_product_number: str | None = None
    label_version: str | None = None
    section: str
    page: int | None = None
    table: str | None = None
    row_key: str | None = None
    excerpt: str | None = Field(default=None, max_length=500)

class CropSeason(ContractModel):
    year: int
    crop_id: str
    sowing_date: date | None
    harvest_date: date | None
    cultivar: str | None = None
    target_yield: Quantity | None = None

class WeedObservation(ContractModel):
    weed_id: str
    common_name: str
    scientific_name: str | None = None
    density: Quantity | None = None
    growth_stage: str | None = None
    observed_on: date | None = None
    confidence: Literal["confirmed", "probable", "uncertain"] = "uncertain"

class ResistanceAssertion(ContractModel):
    weed_id: str
    moa_group: str
    status: Literal[
        "confirmed_resistant", "suspected_resistant", "susceptible", "unknown"
    ]
    evidence: Literal["lab_test", "field_failure", "history", "grower_report", "none"]
    observed_on: date | None = None
    notes: str | None = None

class PaddockState(ContractModel):
    paddock_id: str
    name: str
    state_code: Literal["WA", "SA", "VIC", "NSW", "QLD", "TAS", "NT", "ACT"]
    area_ha: Decimal
    soil_type_id: str | None = None
    weather_source_id: str | None = None
    crop_history: list[CropSeason]
    weed_spectrum: list[WeedObservation]
    resistance_profile: list[ResistanceAssertion]
```

Management events are a discriminated union:

```python
class EventBase(ContractModel):
    event_id: str
    event_date: date
    source: Literal["observed", "planned", "generated"]

class HerbicideApplication(EventBase):
    event_type: Literal["herbicide_application"]
    product_id: str
    registered_use_id: str
    rate: Quantity
    target_weeds: list[str]
    application_method: str
    crop_stage: str | None = None
    weed_stage: str | None = None

class MechanicalControl(EventBase):
    event_type: Literal["mechanical_control"]
    tactic: Literal["tillage", "mouldboard", "crop_topping", "windrow_burning"]
    efficacy_override: Decimal | None = None

class HarvestWeedSeedControl(EventBase):
    event_type: Literal["harvest_weed_seed_control"]
    tactic: Literal["impact_mill", "chaff_cart", "narrow_windrow", "chaff_lining"]

ManagementEvent = Annotated[
    HerbicideApplication | MechanicalControl | HarvestWeedSeedControl,
    Field(discriminator="event_type"),
]
```

Extend the union with sowing, crop establishment, grazing, irrigation, harvest, seed reset and observation events as model support lands.

## 2.4 Simulation contracts

```python
class ModelProvenance(ContractModel):
    model_name: Literal["weed-seed-wizard", "rim"]
    model_version: str
    repository_url: str
    commit_sha: str
    equation_version: str | None
    parameter_version: str | None
    run_mode: str
    validation_status: Literal[
        "verified", "experimental", "partial", "parity_pending", "unsupported"
    ]
    input_sha256: str

class TimePoint(ContractModel):
    date: date | None = None
    year: int | None = None
    weed_id: str
    plants_m2: float | None = None
    seeds_m2: float | None = None

class EconomicOutcome(ContractModel):
    year: int
    gross_margin_aud_ha: Decimal | None
    weed_control_cost_aud_ha: Decimal | None
    yield_t_ha: Decimal | None

class SimulationResult(ContractModel):
    run_id: str
    provenance: ModelProvenance
    status: Literal["succeeded", "failed", "rejected", "timed_out"]
    population: list[TimePoint]
    economics: list[EconomicOutcome]
    summary: dict[str, Decimal | float | int | str | None]
    warnings: list[str]
    unsupported_features: list[str]
```

Do not force detailed WSW output into a lossy optimizer-only shape. Store both:

- a stable common projection (`SimulationResult`) used by the optimizer;
- a model-specific `raw_result` artifact addressed by checksum for diagnostics and future remapping.

## 2.5 Herbicide knowledge contracts

```python
class ActiveIngredient(ContractModel):
    name: str
    concentration_value: Decimal | None
    concentration_unit: str | None

class TimingWindow(ContractModel):
    phase: Literal["pre_sowing", "pre_emergent", "post_emergent", "fallow", "harvest"]
    crop_stage_min: str | None = None
    crop_stage_max: str | None = None
    weed_stage_min: str | None = None
    weed_stage_max: str | None = None
    free_text: str | None = None

class Restriction(ContractModel):
    restriction_type: Literal[
        "grazing_withholding", "harvest_withholding", "plant_back",
        "state", "weather", "soil", "buffer", "application_count", "other"
    ]
    value: Decimal | None = None
    unit: str | None = None
    text: str
    citation: SourceCitation

class RegisteredUse(ContractModel):
    registered_use_id: str
    product_id: str
    apvma_product_number: str
    crop_id: str
    weed_id: str
    state_codes: list[str]
    control_level: Literal["control", "suppression", "partial", "not_stated"]
    rate: Quantity | ValueRange
    timing: TimingWindow
    method: str | None
    restrictions: list[Restriction]
    citations: list[SourceCitation]
    review_status: Literal["machine_extracted", "reviewed", "rejected"]
```

`RegisteredUse` is the central contract. A product may have hundreds of uses; rate, timing and restrictions belong to the use, not to the product or weed globally.

## 2.6 Recommendation contracts

```python
class ObjectiveScore(ContractModel):
    objective: str
    value: Decimal
    direction: Literal["minimize", "maximize"]
    normalized_value: Decimal | None = None

class StrategyCandidate(ContractModel):
    strategy_id: str
    events: list[ManagementEvent]
    label_evidence: list[SourceCitation]
    simulation_runs: list[str]
    scores: list[ObjectiveScore]
    hard_constraint_passed: bool
    violations: list[str]
    uncertainty_notes: list[str]

class Recommendation(ContractModel):
    recommendation_id: str
    case_id: str
    knowledge_snapshot_id: str
    selected: StrategyCandidate | None
    alternatives: list[StrategyCandidate]
    status: Literal[
        "recommendation_ready", "information_required", "no_legal_option",
        "simulation_unverified", "review_required"
    ]
    assumptions: list[str]
    warnings: list[str]
    required_follow_up: list[str]
    requires_professional_review: bool = True
```

The generated prose is a view of `Recommendation`; it is not the stored recommendation itself.

## 2.7 WSW parser specification and optional RIM import

Parsing is a five-stage pipeline:

```text
sniff format -> parse losslessly -> validate source schema -> map to canonical
             -> cross-field/domain validation -> MappingReport
```

`MappingReport` records source file, detected format/version, warnings, defaulted fields, aliases applied, discarded fields, unresolved fields and output checksum.

| Source | Accepted inputs | Parser behavior | Critical validation |
|---|---|---|---|
| WSW JSON | current `ScenarioSchemaV1` (`schema_version=0.1`) | validate with upstream schema where available; resolve local relative weather/catalog paths only in trusted local mode | date order, weather coverage, 12 monthly germination values, four suppression values, species referenced consistently |
| WSW legacy | scenario XML + explicit weather file | use upstream legacy loader in compatibility tests; map top-level dates and supported modules; preserve unparsed XML sections | reject management events the Python port cannot yet execute; never silently drop them |
| WSW weather | CSV | copy/ingest to a content-addressed asset and use an asset ID in canonical payloads | required columns, date uniqueness/order, units, missing values, requested date coverage |
| Optional RIM import | `.rim.json`, `.profile.json`, `.strategy.json` | deferred compatibility adapter; preserve original payload and map only after an explicit RIM integration decision | must not be required by any MVP or student case |

Defaulting policy:

- source-native defaults may be applied only by the upstream parser and must be listed in `MappingReport`;
- agronomic facts such as weed identity, resistance, state and growth stage are never guessed;
- an agent-proposed normalization requires user confirmation when it changes meaning;
- online services accept asset IDs or uploaded content, not file paths.

## 2.8 Student example format

Each exercise is a self-contained, reproducible case:

```text
examples/student/<case-id>/
├── case.yaml                 # metadata, learning objective, expected model scope
├── paddock.json              # canonical PaddockState
├── history.json              # canonical management events
├── wsw/                      # optional native WSW files
├── rim/                      # optional native RIM files
├── question.md               # grower/student goal
└── expected/
    ├── validation.json       # committed validation outcome
    └── assertions.yaml       # qualitative/numeric acceptance checks
```

Do not commit personal grower identifiers. Assign synthetic case IDs and add a data-use declaration to `case.yaml`.

---

# 3. Herbicide Wiki Knowledge Engine

## 3.1 Source-of-truth model

Use three layers:

1. **Immutable source document**: official label, checksum and source metadata.
2. **Human-readable Markdown**: faithful, sectioned transcription used for review and citations.
3. **Canonical structured projection**: product, active ingredients and `RegisteredUse` records used for filtering and optimization.

Never hand-maintain the same rate in both front matter and body. Generate structured records from the reviewed Markdown/source and validate cross-links by checksum.

## 3.2 Markdown format

One primary Markdown file per label approval/version:

```markdown
---
schema: weedai.herbicide-label
schema_version: "1.0.0"
document_id: apvma-31209-124744
apvma_product_number: "31209"
approval_number: "31209/124744"
product_name: NUFARM ESTERCIDE 800 HERBICIDE
registrant: Nufarm Limited
label_version: "124744"
effective_from: null
source_url: https://...
source_sha256: "..."
parsed_at: 2026-09-21T00:00:00Z
review_status: machine_extracted
reviewed_by: null
supersedes: null
---

# Product identity

## Active constituents

## Mode of action and resistance warning

## Directions for use

### Registered use: wheat / target weed / WA

| Field | Label text |
|---|---|
| Rate | ... |
| Timing | ... |
| Critical comments | ... |

## Withholding periods

## Restraints and restrictions

## Compatibility

## Source anchors
```

The canonical records should store source anchors back to heading, page/table/row where available. Markdown headings become stable section IDs; avoid chunks that mix directions, withholding and general instructions.

## 3.3 Canonical indexing pipeline

```text
label/Markdown
  -> schema and checksum validation
  -> table/section-aware extraction
  -> entity normalization (crop, weed, active, unit, MoA)
  -> RegisteredUse expansion (one crop x weed x rate/timing context)
  -> deterministic validation and duplicate detection
  -> reviewer queue for ambiguous or missing fields
  -> structured graph load + evidence chunk load
  -> index manifest and snapshot ID
```

Validation gates:

- product/approval IDs match the document;
- every `RegisteredUse` has at least one citation;
- numeric rate preserves original text and unit;
- a rate range is not collapsed without retaining both endpoints;
- state expansion is auditable;
- withholding type is separated into grazing/harvest/other;
- legacy and current MoA classifications are stored separately with an explicit mapping version;
- no blank rate is accepted as recommendation-eligible;
- contradictions between label sections create a review item;
- superseded/expired sources are excluded from default candidate generation.

## 3.4 Retrieval design

Use hybrid retrieval, but in a strict order:

1. **Structured filtering**: weed, crop, state, registration status, timing, growth stage, resistance exclusions and restriction compatibility.
2. **Graph expansion**: product → active → MoA → registered use → restrictions/citations.
3. **Lexical retrieval**: exact product names, weed aliases, APVMA numbers, phrases and table terms.
4. **Vector retrieval**: find semantically related evidence passages and explanatory context.
5. **Reranking and citation assembly**: prefer reviewed current labels and exact direction/withholding sections.

Vector similarity must never establish legal eligibility or a rate. A vector hit without a matching `RegisteredUse` can answer an informational question with a caveat, but cannot enter the optimizer.

## 3.5 Store interface

```python
class KnowledgeStore(Protocol):
    def eligible_uses(self, query: RegisteredUseQuery) -> list[RegisteredUse]: ...
    def get_product(self, product_id: str) -> Product: ...
    def get_evidence(self, citations: list[SourceCitation]) -> list[EvidenceChunk]: ...
    def semantic_search(self, query: str, filters: EvidenceFilters) -> list[EvidenceChunk]: ...
    def snapshot(self) -> KnowledgeSnapshot: ...
```

Implementations:

- `InMemoryKnowledgeStore` for unit tests and small teaching cases;
- `Neo4jKnowledgeStore` that evolves the existing graph package;
- optional future database implementation without changing callers.

The existing flat `Herbicide -> CONTROLS -> Weed` relationships should be migrated to the `RegisteredUse` hub rather than extended with more relationship properties.

## 3.6 Retrieval quality evaluation

Create a reviewed benchmark of at least 100 agronomic questions covering:

- weed + crop + state + timing;
- withholding and plant-back;
- rate ranges and critical comments;
- product/active/MoA aliases;
- suppression versus control;
- resistance exclusions;
- intentionally unanswerable questions.

Measure structured filter recall, citation correctness, answer support, stale-source leakage and abstention quality. A recommendation test fails if any product/rate claim lacks a valid source citation.

---

# 4. Tool Wrapper Implementations

## 4.1 Framework-neutral tool contract

```python
from typing import Protocol, TypeVar, Generic

InputT = TypeVar("InputT", bound=ContractModel)
OutputT = TypeVar("OutputT", bound=SimulationResult)

class ToolCapabilities(ContractModel):
    tool_name: str
    supported_species: list[str]
    supported_events: list[str]
    supports_economics: bool
    supports_batch: bool
    validation_status: str
    limitations: list[str]

class SimulationTool(Protocol, Generic[InputT, OutputT]):
    def capabilities(self) -> ToolCapabilities: ...
    def validate(self, request: InputT) -> ValidationReport: ...
    def simulate(self, request: InputT) -> OutputT: ...
    def simulate_batch(self, requests: list[InputT]) -> list[OutputT]: ...
```

Wrappers return objects, not prose. LangGraph/LangChain/native function-calling façades are thin functions around application services and live in `packages/agents`, not in the scientific adapters.

## 4.2 Common execution pattern

```python
class CachedSimulationRunner:
    def run(self, tool: SimulationTool, request: ContractModel) -> SimulationResult:
        report = tool.validate(request)
        if not report.is_valid:
            return rejected_result(report)

        capabilities = tool.capabilities()
        enforce_supported_request(request, capabilities)

        key = sha256_json({
            "request": request.model_dump(mode="json"),
            "tool": capabilities,
        })
        if cached := self.cache.get(key):
            return cached

        result = self.executor.execute(tool, request, timeout=self.timeout)
        verified = validate_result_contract(result)
        self.run_repository.save(request, verified)
        self.cache.put(key, verified)
        return verified
```

Production concerns:

- isolated working directory per run;
- no mutation of upstream package globals;
- explicit timeout and memory limits;
- stdout/stderr captured as diagnostic artifacts;
- content-addressed input assets;
- deterministic seeds where stochastic behavior is added;
- stable error taxonomy (`INVALID_INPUT`, `UNSUPPORTED`, `MODEL_FAILURE`, `TIMEOUT`, `PARITY_NOT_APPROVED`);
- never cache across model/parameter/knowledge versions.

## 4.3 WSW adapter

### Native boundary

Use the upstream public library entry point where possible:

```python
config = load_scenario_json(native_scenario_path)
raw = build_scenario_from_config(config).run()
```

The current upstream result includes scenario metadata, event counts, time series, event logs, module summaries and a canonical parity projection. Preserve that result unchanged as an artifact, then map supported series into `SimulationResult`.

### Adapter behavior

```python
class WeedSeedWizardAdapter(SimulationTool[WswRunRequest, SimulationResult]):
    def capabilities(self) -> ToolCapabilities:
        return capabilities_from_pinned_build()

    def validate(self, request: WswRunRequest) -> ValidationReport:
        native = map_canonical_to_wsw(request)
        upstream = ScenarioSchemaV1.model_validate(native)
        return validate_wsw_assets_and_features(upstream, self.capabilities())

    def simulate(self, request: WswRunRequest) -> SimulationResult:
        require_recommendation_grade(self.capabilities(), request.purpose)
        native = map_canonical_to_wsw(request)
        raw = self.backend.simulate(native)
        return map_wsw_result(raw, provenance=self.provenance)
```

### Required readiness work

1. Pin an upstream commit and expose `model_version`, `equation_version` and parity status programmatically.
2. Complete or explicitly reject mapping for management events. The present API construction path does not map all seed/plant/event configuration fields even where the schema contains them.
3. Establish Java-golden fixtures for the four regional scenarios and module-level fixtures.
4. Define tolerances by variable and time scale; document intentional deviations.
5. Mark only covered species/events as supported.
6. Add an upstream typed result schema so the adapter does not depend on arbitrary nested dictionaries.

Until these gates pass, WSW is suitable for pipeline development, teaching about model structure and experimental comparisons—not recommendation-grade agronomic ranking.

## 4.4 Optional RIM adapter — not on the critical path

### Native boundary

RIM already separates scenario loading from Streamlit:

```python
scenario = rim.scenario.from_payload(payload, name=case_id)
problems = utils.validation.problems(scenario.strategy, scenario.custom_options)
raw = verified_engine.simulate(scenario)
```

Do not bind the WeedAI adapter permanently to `tools.run_scenario` or pandas `DataFrame` objects. Add a small stable upstream library API that accepts/returns Pydantic or JSON-compatible models.

### Required upstream decision

If RIM is later integrated, first make one function the approved RIM engine:

```python
rim.api.simulate(request: RimSimulationRequest) -> RimSimulationResult
```

That function must use the Excel-evidence-backed `rim.calcs` implementation (including yield and economics) and pass approved workbook fixtures. Rewire the CLI and Streamlit UI to call it. Deprecate or clearly label the older `rim.engine.simulate_strategy` path.

### Adapter behavior

```python
class RimAdapter(SimulationTool[RimRunRequest, SimulationResult]):
    def validate(self, request: RimRunRequest) -> ValidationReport:
        scenario = load_or_map_rim_scenario(request)
        problems = rim_api.validate(scenario)
        return map_rim_validation(problems, strict=True)

    def simulate(self, request: RimRunRequest) -> SimulationResult:
        require_verified_rim_engine(self.backend.provenance())
        scenario = load_or_map_rim_scenario(request)
        raw = self.backend.simulate(scenario)
        return map_rim_result(raw, provenance=self.provenance)
```

### Model scope

RIM is an annual-ryegrass bioeconomic strategy model. It is not required for the primary architecture. If added later, report it as a separate ryegrass/economic comparison and never allow it to replace or silently modify WSW results.

## 4.5 In-process, subprocess and HTTP backends

Provide three interchangeable executors:

- `InProcessBackend`: fastest for tests, only when dependency versions are compatible and upstream code is re-entrant;
- `SubprocessBackend`: recommended local default; isolates environments and communicates using JSON over stdin/stdout or files in a run directory;
- `HttpBackend`: online sidecar/worker service with the same JSON contracts.

The agent sees no difference between them.

## 4.6 Tool exposure to the agent

Expose task-level tools, not low-level database or model internals:

- `validate_case(case) -> ValidationReport`
- `find_registered_uses(query) -> list[RegisteredUseSummary]`
- `run_baseline(case_id) -> SimulationPortfolio`
- `evaluate_strategies(case_id, candidates) -> EvaluationPortfolio`
- `build_recommendation(case_id, evaluation_id) -> Recommendation`
- `get_evidence(citation_ids) -> list[EvidenceChunk]`

Do not expose arbitrary Cypher, arbitrary file paths, raw shell execution or a generic `run_model(payload)` function to the language model.

---

# 5. Optimization & Recommendation Subsystem

## 5.1 Separation of eligibility, prediction and preference

The subsystem has three distinct stages:

1. **Eligibility:** can the tactic legally and operationally be used?
2. **Prediction:** what does the verified WSW engine predict under the strategy and uncertainty scenarios?
3. **Preference:** which trade-offs suit the grower's stated goals?

An objective score can never compensate for a hard-constraint failure.

## 5.2 Candidate generation

Inputs:

- paddock/crop/weed/resistance state;
- baseline plan and operational constraints;
- eligible `RegisteredUse` records;
- non-chemical tactics supported by each model;
- optimization horizon and grower objectives.

Generate tactics only from controlled vocabularies and reviewed knowledge. For herbicides:

- use label rate points or bounded ranges exactly as represented;
- generate only compatible crop/weed/state/timing combinations;
- remove confirmed-resistant MoA groups;
- treat suspected resistance as a risk/uncertainty scenario or exclude under conservative policy;
- honor maximum applications, withholding, plant-back, buffers and harvest constraints;
- check product/active duplication across mixtures and sequences;
- retain source citations on every generated application.

For integrated weed management, include crop competition, sowing timing, harvest weed-seed control, grazing and tillage only when the selected model and case support them.

## 5.3 Hard constraints

Examples:

- registered crop, weed and jurisdiction;
- rate within a current label use;
- application within crop/weed timing window;
- resistance policy;
- withholding and plant-back periods;
- maximum application count and sequence restrictions;
- incompatible products/tactics;
- equipment and operational availability;
- model capability and validated scope;
- budget ceiling when declared non-negotiable.

Hard constraints are implemented as deterministic predicates with machine-readable violation codes and citations.

## 5.4 Objectives

Keep raw objectives and return a Pareto frontier. Suggested objectives:

- minimize terminal seedbank;
- minimize seedbank area-under-curve;
- maximize discounted gross margin or nominal annuity;
- minimize probability of weed-control failure;
- minimize resistance-selection pressure;
- minimize weed-control cost;
- maximize tactic diversity;
- minimize operational complexity and passes;
- preserve yield and rotation feasibility.

Example objective vector:

```text
f(strategy) = [
  terminal_seedbank,
  seedbank_auc,
  -discounted_gross_margin,
  resistance_risk,
  failure_probability,
  operation_count
]
```

Do not hide trade-offs in one universal weighted score. If a single selection is required, store the grower/user weights and normalization version in the recommendation audit record.

## 5.5 Resistance risk

Start with a transparent rules-based index, reviewed by domain experts. Components may include:

- consecutive exposures to the same MoA for the same target weed;
- number of effective MoA groups in the sequence;
- reliance on one tactic as a share of predicted control;
- known/suspected resistance assertions;
- sublethal or suppression-only use;
- absence of non-chemical tactics;
- repeated active ingredients despite product-name changes.

Return the components as well as the total. Do not claim the index predicts resistance evolution until it has been calibrated and validated.

### Efficacy parameterization

Keep legal label claims separate from numerical simulation efficacy. A label statement such as “control” or “suppression” does not, by itself, justify an invented percentage kill.

Represent numerical efficacy as a versioned assumption with:

- weed, growth stage, tactic/product/active and MoA;
- susceptible efficacy distribution or range;
- resistant-biotype efficacy distribution or range;
- environment and application-quality modifiers;
- evidence type (`model_parameter`, `field_trial`, `expert_scenario`, `student_assumption`);
- source and review status.

Confirmed resistance selects the resistant scenario and normally excludes the affected MoA from recommendation candidates. Suspected resistance triggers conservative and sensitivity scenarios. Unknown resistance is reported as uncertainty; the system must not silently assume susceptibility. Student-supplied efficacy values remain scenario assumptions and cannot be promoted into the shared reference table without review.

## 5.6 Simulation feedback loop

```text
baseline plan
  -> simulate and establish shortfall
  -> generate eligible edits
  -> cheap deterministic pre-filter
  -> simulate surviving candidates in batches
  -> compute objectives and uncertainty
  -> keep non-dominated candidates
  -> expand promising neighborhoods
  -> stop on budget/convergence
  -> verify and present alternatives
```

For MVP-sized spaces, use enumerated templates and beam search. This is explainable and easier to test than a black-box optimizer. Later options:

- NSGA-II for larger discrete multi-objective spaces;
- Bayesian optimization/Optuna for expensive parameter searches;
- scenario sampling/Monte Carlo for uncertain efficacy, prices and weather;
- robust optimization using worst acceptable quantile or regret.

Never optimize a continuous herbicide rate outside label-supported values. The optimizer's search grammar should make illegal states unrepresentable where possible.

## 5.7 Primary-engine policy

Use WSW as the sole primary biological engine:

- WSW supplies multi-species, weather/soil and within-season seedbank dynamics where the relevant modules/events are verified;
- the knowledge engine supplies legal/label constraints and identifies unsupported species or interventions;
- a transparent cost calculator may total product and operation costs, but it must not be presented as a RIM bioeconomic simulation;
- if the WSW port does not yet expose verified yield or income outputs, the MVP ranks biological outcomes and reports costs separately rather than inventing profitability.

RIM may later be added as a secondary comparison through the same `SimulationTool` contract. It must remain optional, its objectives must retain RIM provenance, and its output must never be averaged with WSW. Disagreement is reported, not reconciled by choosing the favorable value.

## 5.8 Shortfall and alternative generation

Configurable shortfall rules may include:

- terminal seedbank above target;
- population increasing in two or more consecutive seasons;
- gross margin below the declared floor;
- high resistance-risk index;
- excessive dependence on a single MoA;
- low robustness across efficacy/weather scenarios;
- no current-label evidence for part of the plan.

When a plan falls short, generate named alternatives:

1. `lowest_seedbank`;
2. `best_economic_return`;
3. `resistance_conservative`;
4. `lowest_cost_that_meets_target`;
5. `robust_under_uncertainty`.

Legal constraints are never relaxed. Soft constraints are relaxed only in a declared order, for example operational preference → cost preference → crop-sequence preference, and every relaxation appears in the output.

## 5.9 Recommendation verification

Before release, a deterministic verifier re-checks:

- every herbicide event points to a current eligible `RegisteredUse`;
- the rate/unit/timing match the cited record;
- restrictions do not conflict with the plan;
- simulations used verified model versions and the same candidate hash;
- objective values reconcile with stored raw results;
- resistance warnings are present;
- all claims in the structured recommendation have evidence;
- cases with missing information are `information_required`, not guessed.

High-risk conditions trigger `review_required`: suspected/confirmed resistance, mixtures, off-normal weather assumptions, missing growth stage, source ambiguity, model disagreement or any experimental model status.

## 5.10 Agent workflow

Use a constrained state graph rather than an open-ended autonomous conversation:

```text
START
  -> parse_intent
  -> validate_case
  -> [missing data?] request_information
  -> retrieve_registered_uses
  -> run_baseline
  -> [model unverified?] research_only_response
  -> generate_candidates
  -> evaluate_candidates
  -> verify_recommendation
  -> [high risk?] human_review_interrupt
  -> explain_with_citations
  -> END
```

Recommended state fields:

- `case_id`, normalized goal and user constraints;
- validation report and unresolved questions;
- knowledge snapshot ID and eligible use IDs;
- baseline/candidate run IDs;
- optimization result ID;
- verified recommendation ID;
- review decision and final presentation.

The LLM is permitted to:

- extract tentative structured fields from a question;
- ask for missing information;
- choose the next approved application service;
- summarize verified results and evidence.

It is not permitted to:

- create products/rates/timing from memory;
- edit a failed candidate into compliance in prose;
- call unverified scientific engines for recommendation-grade output;
- suppress warnings or reviewer gates;
- claim causality beyond model scope.

---

# 6. Phased Implementation Roadmap

## Phase 0 — Decisions, specifications and baselines (1–2 weeks)

**Objective:** agree on scientific and contract boundaries before adding orchestration.

Deliverables:

- Spec-Kit constitution and the WSW-first MVP specs drafted;
- architecture decision records for canonical schema, WSW execution mode, storage and agent framework;
- pin the current WSW commit;
- inventory current WeedAI extraction fields and quality;
- define 20 reference cases, including deliberately invalid/unanswerable cases;
- establish `validation_status` policy.

Exit criteria:

- domain owner approves `RegisteredUse` and recommendation safety policy;
- the WSW owner and domain owner agree on the exact recommendation-grade parity gate;
- no unresolved ambiguity about which component owns each contract.

## Phase 1 — Workspace and canonical data pipeline (2–3 weeks)

**Objective:** create the modular foundation and make examples validate without an agent.

Deliverables:

- root `uv` workspace and packages `domain`, `simulations`, `knowledge`, `optimization`, `agents`, `evaluation`;
- Pydantic v1 contracts and committed JSON Schemas;
- parser sniffing, mapping reports and validation CLI;
- WSW JSON/XML/weather parser fixtures;
- student example directory format and at least five canonical examples;
- CI for Ruff, mypy, unit, property and contract tests.

Exit criteria:

- `weedai case validate examples/...` produces stable JSON reports;
- malformed, unsupported and ambiguous cases fail with useful codes;
- public contract snapshots are reviewed and versioned.

## Phase 2 — WSW wrapper and scientific gate (3–8 weeks; dependent on the upstream port)

**Objective:** expose safe, repeatable model execution independently of the agent.

WSW track:

- implement canonical-to-WSW mapping and result projection;
- add capability reporting and unsupported-event rejection;
- run upstream unit/parity suites at the pinned SHA;
- complete agreed Java-golden coverage before setting `verified`.

Shared deliverables:

- in-process and subprocess backends;
- timeouts, content-addressed cache and run provenance;
- baseline and batch execution CLI;
- contract tests executed against upstream repositories.

Exit criteria:

- identical canonical requests produce identical hashes/results on clean machines;
- adapter mappings are covered by golden fixtures;
- unsupported features are rejected rather than ignored;
- recommendation mode accepts only `verified` model versions.

Optional follow-on, outside the MVP critical path: implement the RIM adapter only after its public engine is parity-approved. No phase exit criterion depends on RIM.

## Phase 3 — Canonical herbicide knowledge and retrieval (3–5 weeks)

**Objective:** replace incompatible partial extraction schemas with one reviewed `RegisteredUse` pipeline.

Deliverables:

- canonical extraction schema and migration/normalization tools;
- 30-label quality pilot using the existing subsample;
- reviewer workflow and QA report for rate, timing, crop, weed, state and withholding accuracy;
- Neo4j `RegisteredUse` schema and loader;
- structured/lexical/vector hybrid retrieval with citation assembly;
- 100-question retrieval benchmark.

Scale only after the pilot meets thresholds. Re-extract the 386 labels directly into the canonical schema rather than migrating both old schemas twice.

Exit criteria:

- 100% of recommendation-eligible uses have citations and nonblank rate/timing context;
- no stale/superseded source is returned by default;
- benchmark meets agreed structured recall and citation correctness;
- intentionally unsupported questions reliably abstain.

## Phase 4 — Deterministic recommendation MVP (2–4 weeks)

**Objective:** produce recommendations without an LLM.

Deliverables:

- eligibility filters and violation codes;
- tactic templates and candidate generator;
- baseline simulation plus batch evaluation;
- transparent resistance-risk components;
- Pareto frontier and five named alternatives;
- deterministic recommendation verifier;
- CLI report with structured citations, assumptions and warnings.

Exit criteria:

- reference cases produce stable, reviewed candidate sets;
- illegal rate/timing/resistance combinations cannot reach output;
- every product claim is supported by a current citation;
- all numeric outcomes reconcile to stored runs.

## Phase 5 — Agent loop and guarded explanation (2–3 weeks)

**Objective:** add natural-language intake and explanation around the deterministic core.

Deliverables:

- constrained state graph and checkpointer;
- typed tool façades over application services;
- missing-information and human-review interrupts;
- prompt-injection-resistant evidence handling;
- structured-output generation and deterministic post-validation;
- agent evaluation set for routing, tool selection, abstention and citation use.

Exit criteria:

- agent cannot bypass a failed validation or invoke arbitrary code/data queries;
- recommendations match deterministic service output;
- no unsupported rate/product claim in the evaluation set;
- research-only outputs are clearly separated from recommendation-grade outputs.

## Phase 6 — Local student pilot (3–4 weeks)

**Objective:** run realistic examples on local machines and learn where contracts fail.

Deliverables:

- cross-platform installation and one-command local start;
- 20–30 curated student cases and marking/analysis export;
- model and knowledge snapshot bundle;
- usability logging without personal data;
- facilitator guide and known-limitations page;
- issue triage and dataset correction workflow.

Pilot measures:

- setup completion rate and time;
- input validation error distribution;
- model run time and failure rate;
- citation verification rate;
- agronomist agreement on eligibility and warnings;
- student ability to explain strategy trade-offs rather than merely accept a ranking.

Exit criteria:

- at least 90% of supported cases run from a clean Windows environment;
- zero silent field drops;
- every high-risk case is interrupted or clearly marked;
- pilot defects are converted into contract, fixture or safety tests.

## Phase 7 — Robust optimization and uncertainty (3–6 weeks)

**Objective:** move beyond template comparison once the deterministic pipeline is trusted.

Deliverables:

- beam search or NSGA-II over discrete approved actions;
- configurable grower objectives and constraint priorities;
- efficacy/price/weather scenario sets;
- robust/Pareto strategy comparison;
- model-disagreement reporting;
- performance budgets and batch parallelism.

Exit criteria:

- optimizer improves at least one objective without violating constraints on benchmark cases;
- exhaustive small-case comparisons validate search correctness;
- repeated runs are reproducible;
- uncertainty changes are visible and explained.

## Phase 8 — Online service (4–8 weeks)

**Objective:** deploy the same services securely and operate them reliably.

Deliverables:

- FastAPI v1 endpoints generated from domain contracts;
- authentication, roles and agronomist-review workflow;
- object storage and upload scanning;
- worker queue with a pinned WSW container image;
- persistent run/audit repositories;
- rate limits, quotas, tracing and cost controls;
- web UI for case entry, comparison, evidence and export;
- backup, migration, rollback and incident runbooks.

Exit criteria:

- online/local contract conformance tests pass;
- no arbitrary path or code execution surface;
- every response is traceable to knowledge/model/input versions;
- load, failure-recovery, security and privacy tests pass;
- domain owner approves the public limitations and review language.

## 6.1 Indicative dependency path

```text
contracts
   +--> WSW verified adapter -----+--> deterministic recommender --> agent --> pilot
   +--> RegisteredUse knowledge --+                                  |
                                                                       +--> robust optimizer
                                                                       +--> online service

   optional later: RIM adapter --> separate comparison portfolio
```

The agent can be prototyped with mocked tools, but it must not become the critical path. Upstream scientific parity and label quality are the likely schedule drivers.

## 6.2 Workstreams and ownership

| Workstream | Primary responsibility | Required review |
|---|---|---|
| Domain/contracts | canonical types, versioning, mapping | Python lead + agronomist |
| WSW | upstream parity, capabilities, adapter | WSW model owner |
| Optional RIM | later comparator only; no MVP dependency | RIM model owner/economist |
| Knowledge | label extraction, review, retrieval | label/agronomy reviewer |
| Optimization | constraints, objectives, search | agronomist + modelling lead |
| Agent/API | workflow, UX, deployment | software lead + safety reviewer |
| Evaluation | fixtures, benchmarks, regression | independent reviewer where possible |

## 6.3 Testing pyramid

1. **Unit tests:** validators, mappings, objective functions, predicates.
2. **Property tests:** quantity conversions, ranges, event ordering, serialization round trips.
3. **Contract tests:** JSON Schema snapshots and consumer/provider tests against the WSW pin.
4. **Golden/parity tests:** Java WSW outputs, never generated by code under test. Add Excel RIM fixtures only if the optional adapter is later adopted.
5. **Knowledge QA:** row-level source comparison and citation validity.
6. **Retrieval tests:** answerable/unanswerable benchmark and stale-source checks.
7. **Optimization tests:** exhaustive oracle on small spaces; invariant that all outputs pass hard constraints.
8. **Agent evaluations:** correct routing, no fabricated facts, abstention, prompt injection, review interrupts.
9. **End-to-end cases:** file/question to verified recommendation and audit export.
10. **Operational tests:** timeouts, worker death, cache isolation, migrations, load and recovery.

## 6.4 Definition of done for any recommendation feature

A feature is not done until:

- its contract and acceptance scenarios are committed;
- deterministic behavior works without an LLM;
- source and model provenance are stored;
- unsupported and missing-data cases are tested;
- safety and domain review are complete;
- CLI/API output is reproducible;
- observability and user-facing limitations are present;
- the roadmap and knowledge/model compatibility matrix are updated.

---

# 7. Recommended Immediate Backlog

1. Approve this architecture and create ADRs for package boundaries and `RegisteredUse`.
2. Initialize the root `uv` workspace without moving existing packages yet.
3. Implement `packages/domain` and freeze `RegisteredUse`, `PaddockState`, `SimulationResult`, `Recommendation` v1 schemas.
4. Convert the existing 30-label subsample into canonical `RegisteredUse` records and perform manual QA before any full re-extraction.
5. Add WSW capability/provenance reporting upstream.
6. Agree on the minimum Java-parity WSW species/events required for the first supported student cases.
7. Build parser/adapter contract tests against the pinned WSW SHA.
8. Implement a deterministic local `case validate`, `case baseline` and `case compare` CLI.
9. Add the agent only after the deterministic recommendation record exists.
10. Reassess whether RIM adds enough independent economic value to justify an optional adapter after the WSW-first pilot.

## 7.1 First vertical slice

The smallest credible end-to-end slice is:

- one state (WA);
- annual ryegrass in wheat;
- reviewed current-label subset with complete rate/timing/withholding data;
- one verified WSW scenario and several multi-season management strategies;
- deterministic comparison of baseline, low-cost, resistance-conservative and lowest-seedbank plans;
- citations and an explicit professional-review requirement;
- no agent required for the first acceptance test.

After that slice passes, broaden WSW crops, weeds, states and intervention types as verified capabilities become available. RIM is a separate later decision, not the next required phase.

## References used for the plan

- WeedAI repository state and current `roadmap.md`, `CLAUDE.md`, ingestion/graph code and label artifacts.
- [WeedSeedWizard-py](https://github.com/DPIRD-FSI/WeedSeedWizard-py) current main branch, including scenario schema, CLI/API and port plan.
- [RIM-Online](https://github.com/00113844/RIM-Online) current main branch, including scenario formats, CLI, architecture and parity modules.
- [DPIRD Weed Seed Wizard overview](https://www.dpird.wa.gov.au/online-tools/weed-seed-wizard/).
- [AHRI weed integrated management models](https://www.ahri.uwa.edu.au/herbicide-resistance/our-research/wim-weed-management-models/).
- [GitHub Spec-Kit](https://github.com/github/spec-kit) and its existing-project guidance.
- [uv workspace documentation](https://docs.astral.sh/uv/concepts/projects/workspaces/).
