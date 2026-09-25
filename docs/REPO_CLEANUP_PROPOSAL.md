# Repo clean-up and structure — proposal

**Date:** 2026-09-25
**Author:** Rodrigo Pires, for decision with Gustavo Alckmin
**Status:** Proposal. Nothing has been moved or deleted. Each item has a recommendation; tick or
change it, then it gets implemented in one pass.

Items are grouped by what they cost to get wrong. Section A is safe and small. Section B changes
where things live. Section C changes history or data and needs the most care.

---

## A. Small fixes

| # | Item | Evidence | Recommendation |
|---|---|---|---|
| A1 | `_wiki_temp` is a broken submodule | Tracked as a gitlink (mode `160000`, commit `d5fcf29`) with no `.gitmodules`, so it cannot be cloned or updated. `wiki/` duplicates the same pages | Remove the gitlink. Keep `wiki/` as the in-repo copy, or drop `wiki/` and use the GitHub wiki only (A2) |
| A2 | Three places describe the same things | `README.md`, `CLAUDE.md`, `roadmap.md`, `wiki/` (7 pages) and `data/README.md` all describe the pipeline and layout, and they drifted (see `docs/ALIGNMENT_2026-09.md` §1) | Keep `README.md` (entry point), `CLAUDE.md` (agent rules), `roadmap.md` (status) and `data/README.md` (data table). Retire `wiki/`, or regenerate it from these rather than editing it by hand |
| A3 | `.claude/settings.local.json` is tracked | It holds one person's local tool permissions. Claude Code treats `*.local.json` as per-user | Untrack it and add `.claude/*.local.json` to `.gitignore` |
| A4 | `Neo4j-43d11dd8-Created-2026-01-05.txt` is tracked | It holds only a comment line in every commit, so no credentials were exposed. It is the file name Neo4j uses for downloaded credentials | Remove it and add `Neo4j-*.txt` to `.gitignore`, so a real credentials file can never be committed by accident |
| A5 | `AGENTS.md` and `GEMINI.md` are symlinks to `CLAUDE.md` | Tracked as mode `120000`. On Windows without symlink support, git checks them out as one-line text files containing `CLAUDE.md` | Keep them if they resolve on both machines. Otherwise replace each with a one-line pointer file |
| A6 | `packages/guardrails` pins `nemo-guardrails==0.10.0` | The version is not on PyPI, and the package has no source, only 7 design docs | Move the design docs to `docs/design/guardrails/` and delete the stub package until Phase 5 of the plan needs it |

## B. Layout

The root holds 16 tracked entries, including 7 docs and 3 one-off test files. Proposed layout,
extending what the plan (§1.2) already proposes:

```text
WeedAI/
├── README.md, CLAUDE.md (+ AGENTS.md, GEMINI.md), CHANGELOG.md, roadmap.md, TODOS.md
├── pyproject.toml              # B1: root uv workspace
├── docs/
│   ├── AGENTIC_WEED_MANAGEMENT_DEVELOPMENT_PLAN.md   # B2
│   ├── ALIGNMENT_2026-09.md, REPO_CLEANUP_PROPOSAL.md
│   ├── design/guardrails/      # A6
│   └── archive/Brainstorming.md, SUBSAMPLE_TEST.md   # B3
├── packages/
│   ├── ingestion/              # B4: parsers consolidated after the trial
│   └── graph/
├── experiments/                # dated trials; promoted into packages/ only if they win
├── scripts/                    # evaluate_docling.py, merge_docling_blocks.py, test_rag.py, test_subsample.sh
└── data/                       # C1, C2
```

| # | Item | Recommendation |
|---|---|---|
| B1 | No root `pyproject.toml` | Create the uv workspace the plan (§1.3) and the roadmap both call for, with `packages/*` as members. One `uv sync` then installs everything on either machine |
| B2 | Plan at the root | Move it to `docs/` once both of us have read it in place, and update the references in `TODOS.md` and `roadmap.md` in the same change |
| B3 | Root clutter | Move `test_rag.py` and `test_subsample.sh` to `scripts/`. `test_subsample_30.txt` goes with them, or is replaced by the trial's pilot list. `SUBSAMPLE_TEST.md` (hard-coded macOS paths and `brew`) and `Brainstorming.md` go to `docs/archive/` |
| B4 | Six ways to turn a PDF into text | `parser` (PyMuPDF4LLM), `local_parser` (PyMuPDF), `docling_parser`, `gemini_parser` (direct PDF to JSON), `extractor` (Gemini on markdown) and `scripts/markdown_to_graph.py`. After the trial, keep one text layer and one extractor and delete the rest. Until then, change nothing |

## C. History and data

| # | Item | Evidence | Options | Recommendation |
|---|---|---|---|---|
| C1 | 386 label PDFs tracked in git | 169 MB in `data/labels/`, committed before `*.pdf` was ignored. Every clone pulls them. History keeps them whatever we do | (a) keep as is; (b) untrack (`git rm --cached`) and document a download step (`ingestion.scraper`); (c) Git LFS | (b), once the scraper is confirmed to re-download the same 386 files. The trial needs the PDFs locally, so do this after it |
| C2 | Two retired extraction sets tracked | `data/extracted/` (50 files) and `data/extracted-from-md/` (160) carry no citations and cannot be migrated (`docs/ALIGNMENT_2026-09.md` §3) | (a) keep; (b) delete after re-extraction and tag the last commit that has them | (b), after the new schema is validated on the pilot |
| C3 | `packages/ingestion/search-results.csv` | 12 MB, read by `csv_scraper.py` as the APVMA search export | (a) keep; (b) move to `data/` with a note on how it was produced | (b) |

## Not proposed

- Rewriting git history to remove the PDFs. It needs a force-push and breaks existing clones, for
  a size problem that C1 already stops growing.
- Any change to `packages/graph` before the use-record schema is agreed.
