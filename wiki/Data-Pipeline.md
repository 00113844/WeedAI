# Data Pipeline

## Steps
1) Parse PDFs to Markdown (offline, PyMuPDF4LLM)
```sh
python -m ingestion.parser              # all labels in data/labels
python -m ingestion.parser --single 31209ELBL  # one label
```
2) Clean Markdown (remove headers/footers/safety noise)
```sh
python -m ingestion.cleaner data/parsed --output data/parsed-clean
```
3) Extract structured JSON with Gemini (Markdown -> JSON)
```sh
python -m ingestion.extractor data/parsed-clean --output data/extracted
```
4) Optional: Parse PDFs directly to JSON with Gemini
```sh
python -m ingestion.gemini_parser data/labels --output data/extracted-pdf
```

## Inputs/outputs
- Input PDFs: `data/labels`
- Parsed Markdown: `data/parsed`
- Cleaned Markdown: `data/parsed-clean` (choose your output dir)
- Extracted JSON: `data/extracted` (or `data/extracted-pdf` for direct PDF -> JSON)

## Environment
- `GEMINI_API_KEY` required for extractor and gemini_parser
- For integration tests using LlamaParse: `LLAMA_CLOUD_API_KEY`

## Tips
- Run extraction in batches if you hit API quota; outputs are per-file JSON.
- Keep raw PDFs immutable; re-run parsing/cleaning is deterministic.
- Validate a few JSON samples before bulk graph loading.
