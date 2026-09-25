# pdf-inspector extraction trial

**Started:** 2026-09-25 (Rodrigo, branch `pdf-inspector`)
**Question:** Which text layer should label re-extraction build on? The choice is between the
tracked `data/parsed-clean` markdown and `pdf-inspector` (`pdf2md`, `detect-pdf`).
**Why now:** Re-extraction into one citable schema is proposed (`docs/ALIGNMENT_2026-09.md` §3 and
§4). If the text layer drops directions-for-use tables or page numbers, no extractor on top of it
can produce cited records.
**Status:** Structural measurement done on the pilot. Manual check against the PDFs not started.

## Pilot

- **Criteria:** the `pdf2md` text names annual ryegrass, wheat, and WA or all states. That is the
  first vertical slice in the plan (§7.1). 87 of 386 labels qualify (`candidates.txt`).
- **Sample:** 30 labels drawn with `random.Random(20260925).sample`, listed in `pilot.txt`. This
  replaces `test_subsample_30.txt` for this purpose.
- **Excluded:** 13 labels have no text layer. `detect-pdf` classifies them as scanned and `pdf2md`
  exits 2 (`results/no_text_layer.txt`). They need OCR whichever route is chosen, and are a
  separate item.
- **Matching is on text.** A label that names a term only to exclude it still qualifies. The manual
  check catches that.

## First results (2026-09-25, `results/summary.md`)

| Measure (30 pilot labels) | pdf2md | parsed-clean |
|---|---|---|
| Any table rows | 30/30 | 10/30 |
| Median table rows | 63 | 0 |
| Page markers, needed for a page citation | 30/30 | 0/30 |
| Mentions critical comments | 30/30 | 4/30 |
| "Directions for Use" heading with an empty body | n/a | 23/30 |

These are structural measures only. They show that `pdf2md` keeps the tables and page boundaries
that `parsed-clean` loses. **They do not show that the tables are read correctly.** Merged cells,
multi-line rows and columns split across pages are the known risks for table extraction.

## Next steps

1. **Manual check.** `results/manual_check.csv` lists five pilot labels. For each one, open the PDF
   and `outputs/pilot/<label>.md`, and record one directions-for-use row per wheat and annual
   ryegrass use: page, section, crop, weed, states, rate text, stages, withholding. Then answer two
   questions. Does the `pdf2md` row match the PDF exactly? Does `parsed-clean` have the row at all?
   Decision point 4 in the alignment note names who reviews.
2. **Decide the text layer.** If `pdf2md` rows match on the manual check, it becomes the text layer.
   If they don't, compare it with Docling (`data/docling/`, regenerated with
   `python -m ingestion.docling_parser`) on the same five labels before deciding.
3. **Extract five labels into `schema_draft.py`'s `UseRecord`,** by hand or by a rule on the
   tables. Check the schema holds what the labels actually say before an LLM extractor is written.
4. **Record the outcome** in `roadmap.md` and close or extend this trial.

## Run

Needs `pdf2md` and `detect-pdf` from `pdf-inspector` (`cargo install pdf-inspector`), on PATH or in
`~/.cargo/bin`. It also needs the label PDFs in `data/labels/`.

```sh
uv run experiments/2026-09-pdf-inspector-trial/trial.py select   # convert all 386, write candidates.txt and pilot.txt (~40 s)
uv run experiments/2026-09-pdf-inspector-trial/trial.py run      # convert and measure the pilot, write results/
uv run experiments/2026-09-pdf-inspector-trial/schema_draft.py   # print the draft record's JSON schema
```

`select` redraws the pilot, so run it only to change the criteria. `outputs/` holds the converted
markdown and is not tracked. Regenerate it with `run`.

## Files

| File | Tracked | What |
|---|---|---|
| `trial.py` | yes | Selection, conversion and measurement |
| `schema_draft.py` | yes | Draft citable `UseRecord`, for review. Open questions are marked `# REVIEW:` |
| `candidates.txt`, `pilot.txt` | yes | The qualifying labels, and the 30-label pilot |
| `results/metrics.csv`, `results/summary.md` | yes | Per-label and aggregate measures |
| `results/no_text_layer.txt` | yes | Labels that need OCR |
| `results/manual_check.csv` | yes | Reviewer sheet, to be filled in |
| `outputs/` | no | Converted markdown, `all/` from `select` and `pilot/` from `run` |
