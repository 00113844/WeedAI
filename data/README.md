# data/

Pipeline artefacts for the 386 APVMA herbicide labels. Only the small, derived
text outputs are tracked; everything else is regenerated locally.

| Directory / file | Produced by | Files | Tracked | Notes |
|---|---|---|---|---|
| `labels/` | APVMA download (`ingestion.scraper`) | 386 PDF, 169 MB | yes (legacy) | Committed before `.gitignore` excluded PDFs; left as-is. New PDFs are ignored. |
| `parsed/` | `python -m ingestion.parser` (PyMuPDF4LLM) | 386 md + `parsing_metadata.json`, 15 MB | no | Raw markdown with YAML frontmatter. |
| `parsed-clean/` | `python -m ingestion.cleaner data/parsed --output data/parsed-clean` | 386 md, 3.3 MB | **yes** | Headers/footers/safety boilerplate removed. Input to both extraction paths below. |
| `docling/` | `python -m ingestion.docling_parser` | 386 `*.docling.json` + `processing_labels.ipynb`, 27 MB | no | Structure-aware JSON with tables; input to `graph.chunker`. |
| `docling_quality_report.json` | `scripts/evaluate_docling.py` | 1 | no | Per-file snippet/quality summary of the docling run. |
| `extracted/` | `python -m ingestion.extractor data/parsed-clean --output data/extracted` | 51 json | **yes** | `HerbicideLabel` schema (`product_number`, `weed_control_entries`, `registered_crops`, …). **This is the schema `graph.loader` / `load-graph` consumes.** |
| `extracted-from-md/` | `packages/ingestion/scripts/markdown_to_graph.py` | 160 json | **yes** | `gemini_parser` schema (`apvma_number`, `usage_scenarios`, `moa_number`, `moa_legacy_letter`). No graph loader reads this yet. |
| `extracted-pdf/`, `extracted-pdf.json` | `python -m ingestion.gemini_parser data/labels` | 0 / 1 | no | Direct PDF→JSON experiment; superseded by the two paths above. |
| `compatability_chemicals/` | manual | 1 PDF + `incompatible_chemicals.json` | no | Apparent tank-mix compatibility chart, partially digitised (see `TODOS.md`). |

The two `extracted*` directories use **incompatible schemas**; which one becomes
canonical is the open decision in `roadmap.md` § Immediate Next Steps.
