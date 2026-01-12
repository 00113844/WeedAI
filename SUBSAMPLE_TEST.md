# WeedAI 30-PDF Subsample Test Guide

This guide walks through testing the complete WeedAI ingestion pipeline with a 30-PDF subsample before processing all 386 herbicide labels.

## Purpose

Test the entire pipeline (PDF → Markdown → Cleaned Markdown → JSON → Neo4j) on a small subsample to verify:
- All packages are correctly installed
- Neo4j connection is working
- Parsing extracts meaningful content
- Gemini extraction produces valid JSON
- Graph loading creates expected nodes and relationships

## Prerequisites

### 1. Packages Installed
```bash
uv pip install -e packages/ingestion
uv pip install -e packages/graph
```

**Status:** ✅ Completed
- ingestion package: ✅ Installed (67 dependencies)
- graph package: ✅ Installed (neo4j driver + pytz)
- guardrails package: ⚠️ Skipped (dependency issue with nemo-guardrails==0.10.0)

### 2. Neo4j Running

**Setup guide created:** See the comprehensive Neo4j setup guide provided by the agent.

**Recommended approach:** Homebrew installation
```bash
brew install neo4j
neo4j console  # Start in foreground to see logs
```

**Verify:**
- Neo4j Browser accessible at `http://localhost:7474`
- Default credentials: username=`neo4j`, password=`neo4j`
- Change password on first login (remember for .env)

### 3. Environment Variables Configured

Update `.env` file in repo root:
```bash
# Required for testing
GEMINI_API_KEY="your-actual-key-here"           # ✅ Already set

# Required after Neo4j setup
NEO4J_URI="bolt://localhost:7687"               # Update from placeholder
NEO4J_USERNAME="neo4j"                          # Default is correct
NEO4J_PASSWORD="your-neo4j-password-here"       # Set during Neo4j first login
NEO4J_DATABASE="neo4j"                          # Default is correct

# Optional (not needed for subsample test)
LLAMA_CLOUD_API_KEY=""                          # Not used (we use local parser)
LANGSMITH_API_KEY=""                            # Not needed for test
```

### 4. Data Directories Created

**Status:** ✅ Completed
```bash
data/parsed/          # For parsed markdown files
data/parsed-clean/    # For cleaned markdown
data/extracted/       # For extracted JSON
```

## Test Subsample

30 PDFs selected from `data/labels/` (first 30 alphabetically):

File: `test_subsample_30.txt` contains:
```
31209ELBL
31253ELBL
31464ELBL
... (27 more)
56421ELBL
```

## Running the Test

### Automated Script (Recommended)

Run all 4 steps with a single command:
```bash
./test_subsample.sh
```

This script:
1. ✅ Parses 30 PDFs to Markdown (local PyMuPDF, no API costs)
2. ✅ Cleans Markdown (removes headers/footers/noise)
3. ✅ Extracts JSON with Gemini (rate-limited: 30 files, 1s delay)
4. ✅ Loads into Neo4j (schema init + graph loading)

**Assumptions:**
- Neo4j is running and accessible at `bolt://localhost:7687`
- Valid GEMINI_API_KEY is set in `.env`
- Neo4j credentials in `.env` are correct
- Sufficient disk space for output files (~50MB for 30 PDFs)

**Conditions for success:**
- All 30 PDFs parse without crashing (warnings OK)
- Gemini extraction respects rate limits
- Neo4j schema initializes without errors
- Graph loading creates nodes and relationships

### Manual Step-by-Step (Alternative)

If you want to run each step manually to inspect outputs:

#### Step 1: Parse PDFs to Markdown
```bash
cd /Users/dpird-mac/Documents/DPIRD/Git/WeedAI

# Parse each PDF from the subsample list
while read pdf_name; do
    python -m ingestion.local_parser "$pdf_name"
done < test_subsample_30.txt
```

**Output:** 30 markdown files in `data/parsed/`

**Verify:**
```bash
ls data/parsed/*.md | wc -l  # Should show 30
head -50 data/parsed/31209ELBL.md  # Check first file has content
```

#### Step 2: Clean Markdown
```bash
python -m ingestion.cleaner data/parsed --output data/parsed-clean
```

**Output:** Cleaned markdown in `data/parsed-clean/`

**Verify:**
```bash
ls data/parsed-clean/*.md | wc -l  # Should match parsed count
diff data/parsed/31209ELBL.md data/parsed-clean/31209ELBL.md  # See what was removed
```

#### Step 3: Extract JSON with Gemini
```bash
python -m ingestion.extractor data/parsed-clean --output data/extracted --limit 30 --delay 1.0
```

**Parameters:**
- `--limit 30`: Process max 30 files (for subsample)
- `--delay 1.0`: Wait 1 second between API calls (respect quotas)

**Output:**
- JSON files in `data/extracted/`
- Summary in `data/_extraction_summary.json`

**Verify:**
```bash
ls data/extracted/*.json | wc -l  # Should show up to 30
cat data/_extraction_summary.json | head -50  # Check summary
python -m json.tool data/extracted/31209ELBL.json | head -50  # Validate JSON
```

#### Step 4: Load into Neo4j
```bash
# Initialize schema (constraints, indexes, reference data)
init-schema

# Load the extracted JSON
load-graph data/extracted

# Check statistics
init-schema --stats
```

**Output:** Nodes and relationships in Neo4j

**Verify:**
```bash
# In Neo4j Browser (http://localhost:7474):
MATCH (h:Herbicide) RETURN h LIMIT 10
MATCH (c:Crop) RETURN c.name, count(*) as herbicide_count
MATCH (w:Weed) RETURN w.name LIMIT 20
MATCH (h:Herbicide)-[r:CONTROLS]->(w:Weed) RETURN h.product_name, w.name, r.rate LIMIT 10
```

## Expected Outcomes

### Success Indicators
- ✅ All 30 PDFs parse (some may have warnings, that's OK)
- ✅ Cleaned markdown files created for all parsed PDFs
- ✅ JSON extraction completes (may skip some files with insufficient content)
- ✅ Neo4j schema initializes without errors
- ✅ Graph contains nodes: Herbicide, Crop, Weed, ActiveConstituent, ModeOfAction, State
- ✅ Relationships exist: CONTAINS, CONTROLS, REGISTERED_FOR, HAS_MODE_OF_ACTION, REGISTERED_IN

### Common Issues & Solutions

#### Issue: "LLAMA_CLOUD_API_KEY is required"
**Solution:** Use local parser instead: `python -m ingestion.local_parser`
- The automated script already uses local_parser
- Local parser uses PyMuPDF, no API costs

#### Issue: "Connection refused" (Neo4j)
**Solution:**
```bash
# Check Neo4j is running
neo4j status

# If not running, start it
neo4j console  # or: neo4j start

# Verify port 7687 is open
lsof -i :7687
```

#### Issue: Gemini API quota exceeded
**Solution:** Increase delay between requests
```bash
python -m ingestion.extractor data/parsed-clean --output data/extracted --limit 30 --delay 2.0
```

#### Issue: Some PDFs fail to parse
**Expected:** Not all PDFs parse perfectly (table extraction, complex layouts)
- Check `parsing_metadata.json` for failed files
- Review error messages to understand pattern
- This is normal - extraction may still work with imperfect markdown

#### Issue: Guardrails package won't install
**Status:** Known issue (nemo-guardrails==0.10.0 not available)
**Impact:** None for subsample test (guardrails are for safety/compliance checks, not core pipeline)
**Solution:** Skip guardrails for now, focus on ingestion + graph

## Interpreting Results

### Parsing Success Rate
```bash
cat data/parsed/parsing_metadata.json | python -m json.tool | grep -A 5 '"parsed"'
```
- **100% success:** Excellent, all PDFs parsed cleanly
- **90-99% success:** Good, most PDFs parsed (expected given PDF complexity)
- **<90% success:** Investigate common failure patterns

### Extraction Quality
```bash
cat data/_extraction_summary.json
```
Look for:
- `total_processed`: Should match number of cleaned markdown files
- `successful`: Number of valid JSON outputs
- `insufficient_content`: Files that didn't have enough data to extract

Check a sample extracted JSON:
```bash
python -m json.tool data/extracted/31209ELBL.json | less
```

Verify it has:
- `product_name`
- `apvma_number`
- `active_constituents[]`
- `crops[]`
- `weeds[]` with control details
- `mode_of_action_groups[]`

### Graph Statistics
```bash
init-schema --stats
```

Expected ranges (for 30 PDFs):
- Herbicides: 25-30 (some may fail extraction)
- Crops: 20-50 (depends on label diversity)
- Weeds: 50-150 (high variability in weed lists)
- ActiveConstituents: 20-40
- ModeOfAction: 5-15 (limited number of herbicide groups)
- States: 6-8 (Australian states/territories)
- Relationships: 200-1000+ (depends on weed control entries)

## Next Steps After Successful Test

1. **Verify Data Quality**
   ```bash
   # Open Neo4j Browser
   open http://localhost:7474

   # Run exploratory queries
   MATCH (h:Herbicide)-[:CONTROLS]->(w:Weed)
   RETURN h.product_name, collect(DISTINCT w.name) as weeds
   LIMIT 5
   ```

2. **Process Remaining PDFs**
   ```bash
   # Parse remaining files
   python -m ingestion.local_parser  # Parses all PDFs not already done

   # Clean all parsed files
   python -m ingestion.cleaner data/parsed --output data/parsed-clean

   # Extract in batches (respect Gemini API quotas)
   python -m ingestion.extractor data/parsed-clean --output data/extracted --limit 50 --delay 1.0

   # Reload graph with full dataset
   init-schema --clear  # Optional: clear and start fresh
   load-graph data/extracted
   ```

3. **Update CHANGELOG.md**
   Document the test results, any issues encountered, and decisions made.

4. **Continue with TODO Items**
   See `TODOS.md` for next pipeline tasks:
   - Spot-check JSON quality
   - Implement GraphRAG retrieval
   - Digitize compatibility matrix

## Cost Estimates

### API Costs (Gemini)
- **Local parsing:** $0 (uses PyMuPDF)
- **Gemini extraction:** ~$0.05-0.10 per 30 PDFs (gemini-2.5-flash-lite)
- **Full dataset (386 PDFs):** ~$0.60-1.20 total

### Time Estimates
- **Parsing (local):** ~30 seconds for 30 PDFs
- **Cleaning:** ~5 seconds
- **Gemini extraction:** ~60 seconds for 30 PDFs (with 1s delay)
- **Graph loading:** ~10 seconds
- **Total for subsample:** ~2 minutes

### Storage
- **Source PDFs:** ~200MB (386 files)
- **Parsed markdown:** ~50MB
- **Cleaned markdown:** ~40MB
- **Extracted JSON:** ~10MB
- **Neo4j database:** ~50MB
- **Total:** ~350MB

## Notes

- The local parser (PyMuPDF) is used instead of LlamaParse to avoid API costs during testing
- Parser may not extract tables perfectly - this is expected and extraction can still work
- Gemini extraction uses structured output with Pydantic schemas for consistency
- Neo4j schema includes constraints to prevent duplicate nodes
- Rate limiting (`--delay`) is critical to avoid quota errors with Gemini API

## Philosophy Alignment

This test follows the stated project philosophy:

✅ **State assumptions before code:**
- Assumes Neo4j is running and accessible
- Assumes valid API keys in .env
- Assumes sufficient disk space for outputs

✅ **Verify correctness:**
- Each step produces verifiable output
- Statistics and counts provided for validation
- Sample inspection commands included

✅ **Handle edge cases:**
- Script continues on single file failures
- Rate limiting prevents API quota errors
- Checks for existing files to avoid reprocessing

✅ **Document conditions:**
- Prerequisites clearly stated
- Success criteria defined
- Failure modes documented with solutions
