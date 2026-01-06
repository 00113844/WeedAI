# WeedAI Monorepo

Domain-specific GraphRAG pipeline for Australian herbicide labels. Processes PDFs → Markdown → Cleaned Markdown → Structured JSON → Neo4j graph.

## Repository Layout
- `packages/ingestion/`: PDF parsing, cleaning, and Gemini-based extraction.
  - Parsing to Markdown: [`ingestion.parser`](packages/ingestion/src/ingestion/parser.py)
  - Local PyMuPDF parser: [`ingestion.local_parser`](packages/ingestion/src/ingestion/local_parser.py)
  - Cleaning Markdown: [`ingestion.cleaner`](packages/ingestion/src/ingestion/cleaner.py)
  - Gemini JSON extraction: [`ingestion.extractor`](packages/ingestion/src/ingestion/extractor.py)
  - Gemini PDF parsing to JSON: [`ingestion.gemini_parser`](packages/ingestion/src/ingestion/gemini_parser.py)
  - CSV/APVMA scrapers: [`ingestion.csv_scraper`](packages/ingestion/src/ingestion/csv_scraper.py), [`ingestion.scraper`](packages/ingestion/src/ingestion/scraper.py)
  - Tests: [`tests/test_parser.py`](packages/ingestion/tests/test_parser.py)
- `packages/graph/`: Neo4j schema, loader, and queries.
  - Schema/init: [`graph.schema`](packages/graph/src/graph/schema.py)
  - Loader: [`graph.loader`](packages/graph/src/graph/loader.py)
  - Queries: [`graph.queries`](packages/graph/src/graph/queries.py)
  - Package export: [`graph.__init__`](packages/graph/src/graph/__init__.py)
- `data/labels/`: Source PDFs (not committed here).
- `data/parsed/`: Parsed Markdown outputs.
- `data/extracted/`: Extracted JSON outputs (after Gemini).

## Setup
1. Python 3.11+, install deps per component (using `uv` or pip):
   ```sh
   uv pip install -e packages/ingestion
   uv pip install -e packages/graph
   ```
2. Environment:
   - `.env` (root): Gemini + Neo4j creds (see `packages/graph/README.md` for Neo4j vars; Gemini key read in ingestion modules).

## Ingestion Workflow
1. **Parse PDFs → Markdown (local, PyMuPDF4LLM)**  
   ```sh
   # all PDFs
   python -m ingestion.parser
   # single file
   python -m ingestion.parser --single 31209ELBL
   ```
2. **Clean Markdown**  
   ```sh
   python -m ingestion.cleaner data/parsed --output data/parsed-clean
   ```
3. **Extract JSON from Markdown (Gemini)**  
   ```sh
   python -m ingestion.extractor data/parsed-clean --output data/extracted
   ```
4. **(Optional) Direct Gemini PDF → JSON**  
   ```sh
   python -m ingestion.gemini_parser data/labels --output data/extracted-pdf
   ```

## Graph Loading
1. Initialize schema & load JSON:
   ```sh
   uv pip install -e packages/graph
   load-graph data/extracted
   ```
   Behind the scenes: schema setup [`graph.schema`](packages/graph/src/graph/schema.py), load [`graph.loader`](packages/graph/src/graph/loader.py).

## Testing
- Unit tests (no live APIs):  
  ```sh
  cd packages/ingestion
  pytest tests/ -v -m "not integration"
  ```
- Integration (requires LLAMA_CLOUD_API_KEY for live parsing):  
  ```sh
  pytest tests/ -v -m integration
  ```

## Key Prompts & Models
- Parsing instruction constant validated in [`tests/test_parser.py`](packages/ingestion/tests/test_parser.py) for required terms.
- Extraction prompt defined in [`ingestion.extractor`](packages/ingestion/src/ingestion/extractor.py) (`EXTRACTION_PROMPT`).
- Gemini models default: `gemini-2.5-flash-lite` for markdown extraction, `gemini-2.5-flash` for PDF parsing.

## Data Paths (defaults)
- Labels: `data/labels`
- Parsed Markdown: `data/parsed`
- Extracted JSON: `data/extracted`

## CLI Entrypoints (per module)
- Parser: `python -m ingestion.parser` (Markdown)
- Cleaner: `python -m ingestion.cleaner`
- Extractor: `python -m ingestion.extractor`
- Gemini PDF Parser: `python -m ingestion.gemini_parser`
- Graph Loader: `load-graph ...` (installed via `packages/graph`)