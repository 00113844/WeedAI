# WeedAI Changelog

All notable changes and progress in this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### 2026-09-16 - Data versioned, docs reconciled, agentic setup

#### Added
- `data/parsed-clean/` (386 cleaned markdown), `data/extracted/` (51 `HerbicideLabel` JSON) and `data/extracted-from-md/` (160 `usage_scenarios` JSON) are now tracked in git.
- `data/README.md` — table of every `data/` subdirectory: producer, count, tracked or not, schema.
- `CLAUDE.md` § "Working in this repo (agentic sessions)" — repo root, which venv, git/push conventions, which docs to update each session.
- `roadmap.md` § "Known repo debt" — tracked PDFs, duplicate venvs, missing workspace root, unavailable `nemo-guardrails` pin, macOS-only test script, wiki duplication.
- Claude Code project memory (outside the repo, under `~/.claude/projects/`) capturing the above so future sessions start warm.

#### Changed
- `.gitignore`: `data/` → `data/*` with explicit allow-list for the three tracked subdirectories. PDFs, `parsed/`, `docling/` remain untracked.
- `origin` remote switched from SSH to HTTPS (`https://github.com/00113844/WeedAI.git`) with `gh` as credential helper — SSH keys are not configured on this Windows machine.
- `roadmap.md`: refreshed counts (parsed-clean 386 not 388; extraction 51 + 160 not 22), removed the phantom `pyproject.toml` workspace root, marked guardrails as a stub, replaced Immediate Next Steps with a list that starts at the real blocker (schema decision), added a 2026-09-16 diary entry.
- `TODOS.md`: extraction items rewritten around the schema decision; "302 remaining" corrected to 335 / 226 depending on path; duplicate-directory item closed.

#### Fixed
- `CLAUDE.md` no longer references files that do not exist (`packages/guardrails/guardrail.py`, `config/`, `actions/`, root `pyproject.toml`) and now lists every real module and CLI entry point (`chunk-docling`, `load-chunks`, `scripts/markdown_to_graph.py`, …).

#### Notes
- The two extraction outputs use **incompatible schemas**; `graph.loader` only reads `HerbicideLabel`. Choosing the canonical schema is now Immediate Next Step #1.
- Working Python environment is `../.venv` (3.12, has `ingestion`, `graph`, `docling`, all entry points). `packages/ingestion/.venv` (3.11) is stale.
- Pushed straight to `main` per project owner's decision on 2026-09-16.

### 2026-01-12 - Environment Setup & Subsample Test Preparation

#### Environment State Discovered
- 386 PDF herbicide labels present in `data/labels/`
- Base weedai package installed, but component packages (ingestion, graph, guardrails) not yet installed
- Pipeline directories not created (parsed, parsed-clean, extracted)
- Neo4j credentials in `.env` are placeholder values
- No extraction has been performed yet

#### Completed Actions

**1. Package Installation**
- ✅ Installed `packages/ingestion` (67 dependencies including PyMuPDF, Gemini, LlamaParse)
- ✅ Installed `packages/graph` (Neo4j driver 6.0.3, pytz)
- ⚠️ Skipped `packages/guardrails` (dependency conflict: nemo-guardrails==0.10.0 unavailable)
  - Not critical for core pipeline testing
  - Can be addressed later for safety/compliance features

**2. Infrastructure Setup**
- ✅ Created pipeline directories: `data/parsed/`, `data/parsed-clean/`, `data/extracted/`
- ✅ Generated 30-PDF test subsample list: `test_subsample_30.txt`
- ✅ Created comprehensive Neo4j setup guide with installation options (Homebrew, Docker, Desktop)

**3. Documentation Created**
- ✅ `CHANGELOG.md` - This file, for tracking all work
- ✅ `SUBSAMPLE_TEST.md` - Comprehensive testing guide with step-by-step instructions
- ✅ `test_subsample.sh` - Automated test script for running full pipeline on 30 PDFs
- ✅ Neo4j setup guide - Delivered via sub-agent with macOS-specific instructions

**4. Test Subsample Selection**
Selected first 30 PDFs alphabetically from `data/labels/`:
```
31209ELBL, 31253ELBL, 31464ELBL, ..., 56421ELBL
```

#### Test Script Components

The `test_subsample.sh` script automates 4 pipeline steps:

1. **Parse PDFs → Markdown** (local PyMuPDF parser, no API costs)
   - Uses `ingestion.local_parser` module
   - Extracts text and tables with metadata
   - ~30 seconds for 30 PDFs

2. **Clean Markdown** (remove headers/footers/noise)
   - Uses `ingestion.cleaner` module
   - Prepares documents for extraction
   - ~5 seconds

3. **Extract JSON with Gemini** (rate-limited)
   - Uses `ingestion.extractor` with `--limit 30 --delay 1.0`
   - Structured extraction via Pydantic schemas
   - ~60 seconds for 30 PDFs (includes rate limiting)

4. **Load into Neo4j** (schema + data)
   - `init-schema` creates constraints/indexes
   - `load-graph` ingests JSON into graph
   - `init-schema --stats` shows node counts
   - ~10 seconds

**Total estimated time:** ~2 minutes for 30-PDF subsample test

#### Pending Actions (User-Dependent)

1. **Neo4j Setup** - User handling independently
   - Install Neo4j (Homebrew recommended: `brew install neo4j`)
   - Start Neo4j: `neo4j console`
   - Set initial password via browser: `http://localhost:7474`
   - Update `.env` with credentials

2. **Run Subsample Test** - After Neo4j is ready
   ```bash
   ./test_subsample.sh
   ```

3. **Verify Results**
   - Check Neo4j Browser for data
   - Review extraction summary: `data/_extraction_summary.json`
   - Validate graph statistics

#### Assumptions & Conditions

**Assumptions stated:**
- Neo4j will be installed and accessible at `bolt://localhost:7687`
- GEMINI_API_KEY in `.env` is valid and has quota available
- Sufficient disk space (~50MB for 30-PDF outputs)
- macOS environment with Homebrew available

**Under what conditions does this work?**
- Local parser: Works offline, no API dependencies, handles most PDF layouts
- Gemini extraction: Requires valid API key, respects rate limits via `--delay`
- Neo4j loading: Requires running Neo4j instance with correct credentials
- Pipeline steps: Each step can be run independently or via automated script

**Edge cases handled:**
- Script continues if individual PDFs fail to parse (warnings displayed)
- Rate limiting prevents Gemini API quota exhaustion
- Directories created if they don't exist
- Existing files skipped to avoid reprocessing

#### Known Issues

1. **Guardrails package:** Cannot install due to nemo-guardrails==0.10.0 unavailability
   - **Impact:** None for core pipeline (parsing, extraction, graph loading)
   - **Status:** Deferred until package dependency is resolved

2. **TODOS.md outdated:** References 302 markdown files that don't exist
   - **Reason:** Likely from previous work that was reset/cleaned
   - **Action:** TODOS.md should be updated after subsample test completes

#### Cost Estimates

- **Local parsing:** $0 (PyMuPDF is local)
- **Gemini extraction (30 PDFs):** ~$0.05-0.10 (gemini-2.5-flash-lite)
- **Full dataset (386 PDFs):** ~$0.60-1.20
- **Storage:** ~350MB total for all outputs

#### Notes
- Following project philosophy: State assumptions, verify correctness, handle edge cases, document conditions
- Local parser (`ingestion.local_parser`) preferred over LlamaParse for testing to minimize API costs
- Parser may not perfectly extract all tables - this is expected; extraction can still succeed
- Test script is idempotent - can be run multiple times safely
- Git status shows untracked files: AGENTS.md, CLAUDE.md, GEMINI.md, CHANGELOG.md, SUBSAMPLE_TEST.md, test_subsample.sh, test_subsample_30.txt

---

## Previous Work (from git history)

### 2026-01-10
- Added Docling-based PDF parser for structured extraction of text and tables
- Updated TODOS and roadmap with new tasks

### 2026-01-09
- Refactored PDF parsing to utilize LlamaParse
- Enhanced metadata extraction and error handling
- Moved guardrails files to packages folder (root cleanup)

### 2026-01-07
- Merged pull request #13 from worktree

---

## Template for Future Entries

### YYYY-MM-DD - [Brief Description]

#### Added
- New features or capabilities

#### Changed
- Changes to existing functionality

#### Fixed
- Bug fixes

#### Removed
- Removed features or files

#### Notes
- Context, assumptions, or conditions under which changes work
