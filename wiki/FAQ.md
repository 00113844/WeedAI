# FAQ / Troubleshooting

**Gemini quota exceeded**
- Retry later or batch files; extraction is per-file JSON, so partial runs are fine.

**Neo4j auth or connectivity fails**
- Verify `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` in `.env` and that the database is running.

**Parsing dropped content**
- Re-run `ingestion.parser` and review the Markdown; adjust cleaner settings if headers/footers removed too aggressively.

**Where do PDFs live?**
- Store under `data/labels`; do not commit PDFs.

**How do I run one file end-to-end?**
```sh
python -m ingestion.parser --single 31209ELBL
python -m ingestion.cleaner data/parsed --output data/parsed-clean
python -m ingestion.extractor data/parsed-clean --output data/extracted
load-graph data/extracted
```
