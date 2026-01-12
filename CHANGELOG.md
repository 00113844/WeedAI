# WeedAI Changelog

All notable changes and progress in this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

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
