# Alignment notes — September 2026

**Date:** 2026-09-25
**Author:** Rodrigo Pires, for review with Gustavo Alckmin
**Status:** Proposed. Nothing here is decided until Gustavo agrees. The open points are in
[Decision points](#decision-points).
**Reads with:** `AGENTIC_WEED_MANAGEMENT_DEVELOPMENT_PLAN.md` (Gustavo, 2026-09-21), `roadmap.md`,
`TODOS.md`

This note records how the development plan, the repo docs and the two code repos line up, what is
stale, and the proposed direction. It does not change the plan. The plan is included verbatim.

---

## 1. The docs had drifted from each other

Before this branch:

- The plan was not in the repo.
- `roadmap.md` "Immediate Next Steps" ordered the work as LLM extraction with `neo4j-graphrag`
  SimpleKGPipeline, then LangGraph. The plan orders it contracts, then the deterministic core, then
  the agent last. `TODOS.md` carried both orders.
- `roadmap.md` Phase 6, `CLAUDE.md`, `Brainstorming.md` Phase 4 and the `wiki/` pages routed
  simulation through a Java "sidecar" subprocess. The plan replaces this with an adapter over the
  Python port, `WeedSeedWizard-py`. Any agent working in the repo was still told to build the
  sidecar.
- SimpleKGPipeline does not give page, section or row citations by default. The plan requires a
  citation on every record.

This branch brings the plan in, marks the sidecar references as superseded, and marks the build
order as under review (section 4).

## 2. WeedSeedWizard-py is further along than the plan says

The plan read `WeedSeedWizard-py` `main` as it was in June 2026 (`f9bc6d7`). `dev` has since been
merged to `main` (PR #1, `16d06ba`, 2026-09-25). On current `main`:

- Plants, spray, grazing, sowing and tillage events are ported, with tests against the Java source.
- Weed output matches the Java source to `9.47e-15` relative across the four regional default
  scenarios. The shipped v7.1.7 model code and the 2021 source agree to `4.16e-13`.
- Invalid input is rejected at load. `Scenario.run()` returns a typed, versioned `RunResult` (v1).
  The API no longer drops scenario fields.
- Evidence: `docs/port_validation_summary.md` in that repo.

Against the plan's WSW readiness list (§4.3):

| # | Item | State on `main` |
|---|---|---|
| 1 | Pin a commit and expose version, equation version and parity status in code | **Open.** `model_version` is the hardcoded `"0.1.0"`. Pin a commit for now |
| 2 | Complete or reject event mapping | Done for the events above. The dropped-field defect is fixed and unsupported XML content is rejected. Worth checking against what the adapter will send |
| 3 | Java-golden fixtures for the four regional scenarios | Done |
| 4 | Tolerances by variable | Done, measured |
| 5 | Mark only covered species and events as supported | **Open.** 13 of 49 catalogue species have measured dynamics. There is no machine-readable list yet |
| 6 | Typed upstream result | Done (`RunResult` v1) |

Soil and weather outputs are checked against the Java source only, because the desktop
application exports neither.

One link is unowned. A label gives product, rate and weed stage. A WSW spray event uses a fixed
kill proportion from its spray-type catalogue, and spray efficacy does not interact with weather or
plant stage in the model. Nothing in the plan maps one to the other. This matters only if the agent
runs WSW on strategies built from label content (decision point 5).

## 3. The existing extracted label data cannot become cited records

Measured on 2026-09-24 against the tracked data:

| Plan requirement | `data/extracted/` (`HerbicideLabel`) | `data/extracted-from-md/` (`usage_scenarios`) |
|---|---|---|
| Files / use entries | 50 files (roadmap says 51) / 364 entries | 160 / 1,404 |
| Citation to page, section or row | Source filename only | Source filename only |
| Timing or growth stage | `application_timing` 55% | `growth_stage_weed` and `growth_stage_crop` 0% |
| Original rate text kept | `rate_per_ha` string 99% | `rate_value` 100%, `rate_full_text` 55% |
| Withholding per use | One `withholding_period` string per product | Inside `constraints`, 42% filled |
| Encoding | 14 of 50 files are not UTF-8 | Clean |
| Ryegrass in wheat, WA or all states (first slice) | 2 entries | 4 entries |

No existing record has a citation, and most lack timing, so this is re-extraction, not migration.

A second finding, measured 2026-09-25 and not yet quality-checked: the tracked
`data/parsed-clean/` markdown has tables in 133 of 386 labels. `pdf2md` (from `pdf-inspector`) on
the same PDFs produces tables in 357. For example, the "Directions for Use" section of
`31209ELBL` is empty in `parsed-clean`, and `pdf2md` returns 152 table rows for that label. Only 49
cleaned files mention ryegrass, against 201 from `pdf2md`. If this holds up, the text layer
under both extraction runs was missing most directions-for-use tables. The extraction trial
(`experiments/2026-09-pdf-inspector-trial/`) tests this before anything depends on it.

## 4. Proposed direction

**Purpose of the label work (proposed by Rodrigo).** Label content is cited context for the
agent's responses. The agent retrieves label facts and quotes them with their source. It is not a
recommender that decides legal eligibility and ranks strategies.

If agreed:

- Keep the plan's citation, retrieval-order and fail-closed rules (§3.2 to §3.4). They apply
  because the agent will quote label facts.
- Defer plan Phases 4, 7 and 8 and the Pareto and five-alternative machinery (§5.4 to §5.8). The
  purpose does not need them yet.
- Re-extract labels into one schema. Each record carries a page or section citation, per-use timing
  and weed and crop stage, per-use withholding and plant-back, and the original rate text alongside
  parsed values. Retire both partial schemas once the new one is validated.
- Choose the extraction route by measurement. The trial compares `pdf-inspector` against the
  current text layer on the WA wheat and annual ryegrass labels. The agent will also read HTML and
  web sources, so general extraction tooling would be reused beyond labels.
- Replace the Java sidecar with an adapter over `WeedSeedWizard-py`, pinned to a commit, as the
  plan already says.

## Decision points

For Gustavo and Rodrigo together:

1. **Scope.** Is the goal label content as cited agent context, with the optimiser deferred?
2. **One source of truth.** This branch puts the plan in the repo. Keep it at the root or move it
   under `docs/`? See `docs/REPO_CLEANUP_PROPOSAL.md`.
3. **Extraction route.** Decide after the trial whether extraction stays on a structured text layer
   (Docling or `pdf-inspector`) or moves to SimpleKGPipeline, and which model and quota to use.
4. **Pilot set and reviewer.** The trial uses WA wheat and annual ryegrass labels rather than
   `test_subsample_30.txt`. Who checks extraction accuracy against the PDFs?
5. **Label to WSW spray mapping.** Will the agent run WSW on label-derived strategies? If so, who
   maps product and rate to a WSW spray kill proportion, and on what evidence?
6. **WSW-py interface.** Pin a commit or a release? Is anything needed beyond version and parity
   status in code, and a supported species and events list?
7. **Repo ownership.** Should WeedAI stay on a personal public account, given it builds on a
   DPIRD-FSI model and may become a service?
8. **Response wording.** What the agent says when it quotes label content: the disclaimer, and when
   it must defer to an agronomist. Settle before anything goes online.

## Housekeeping found while checking

- The GitHub `dev` branch was deleted on 2026-01-12. Any local `origin/dev` ref, and the agent
  skeleton and RAGAS package that existed only there, are not in the repo.
- `src/agent/` and `tests/` exist on some machines as `__pycache__` only. They are untracked.
