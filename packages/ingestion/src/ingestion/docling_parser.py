"""Docling-based PDF parser for extracting text blocks and tables."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List, Optional

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import DocItem, DocItemLabel


def _collect_pdfs(path: Path) -> List[Path]:
    if path.is_file() and path.suffix.lower() == ".pdf":
        return [path]
    if path.is_dir():
        return sorted(p for p in path.rglob("*.pdf"))
    raise FileNotFoundError(f"No PDF found at {path}")


def _bbox_from_item(item: DocItem) -> Optional[dict]:
    provenance = getattr(item, "prov", None) or []
    for entry in provenance:
        bbox = getattr(entry, "bbox", None)
        if bbox is None:
            continue
        return {
            "x0": getattr(bbox, "x0", None),
            "y0": getattr(bbox, "y0", None),
            "x1": getattr(bbox, "x1", None),
            "y1": getattr(bbox, "y1", None),
            "page": getattr(entry, "page", None),
        }
    return None


def _serialize_tables(document) -> Iterable[dict]:
    for idx, table in enumerate(document.tables, start=1):
        dataframe = table.export_to_dataframe() if hasattr(table, "export_to_dataframe") else None
        rows = dataframe.fillna("").values.tolist() if dataframe is not None else []
        markdown = table.export_to_markdown(doc=document) if hasattr(table, "export_to_markdown") else None
        yield {
            "id": getattr(table, "id", None) or f"table-{idx}",
            "title": getattr(table, "title", None),
            "row_count": len(rows),
            "column_count": len(rows[0]) if rows else 0,
            "rows": rows,
            "markdown": markdown,
            "bbox": _bbox_from_item(table),
        }


def _serialize_text_items(document) -> Iterable[dict]:
    tracked_labels = {
        DocItemLabel.SECTION_HEADER,
        DocItemLabel.PARAGRAPH,
        DocItemLabel.TEXT,
        DocItemLabel.LIST_ITEM,
    }
    for item in document.iterate_items():
        if getattr(item, "label", None) not in tracked_labels:
            continue
        content = getattr(item, "text", "").strip()
        if not content:
            continue
        yield {
            "label": getattr(item.label, "name", str(item.label)),
            "text": content,
            "bbox": _bbox_from_item(item),
        }


def convert_pdf(pdf_path: Path, converter: DocumentConverter) -> dict:
    result = converter.convert(str(pdf_path))
    document = result.document
    metadata = {
        "page_count": getattr(result.input, "page_count", None),
        "filesize": getattr(result.input, "filesize", None),
        "format": getattr(result.input, "format", None),
    }
    return {
        "source_path": str(pdf_path),
        "metadata": metadata,
        "text_items": list(_serialize_text_items(document)),
        "tables": list(_serialize_tables(document)),
    }


def build_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions(do_table_structure=True)
    pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE
    format_options = {
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
    return DocumentConverter(format_options=format_options)


def run(
    input_path: Path,
    output_dir: Optional[Path],
    *,
    limit: Optional[int] = None,
    skip_existing: bool = False,
) -> List[Path]:
    pdfs = _collect_pdfs(input_path)
    if not pdfs:
        raise FileNotFoundError(f"No PDFs found under {input_path}")
    if skip_existing and output_dir is not None:
        pdfs = [pdf for pdf in pdfs if not (output_dir / (pdf.stem + ".docling.json")).exists()]
    if limit is not None:
        pdfs = pdfs[:limit]
    converter = build_converter()
    output_paths: List[Path] = []
    for pdf in pdfs:
        if output_dir is None:
            print(f"Processing {pdf.name}")
            payload = convert_pdf(pdf, converter)
            print(json.dumps(payload, indent=2))
            continue
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / (pdf.stem + ".docling.json")
        if skip_existing and out_path.exists():
            print(f"Skipping existing output for {pdf.name}")
            continue
        print(f"Processing {pdf.name}")
        payload = convert_pdf(pdf, converter)
        out_path.write_text(json.dumps(payload, indent=2))
        output_paths.append(out_path)
    return output_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert PDFs to structured JSON using Docling.")
    parser.add_argument("input", type=Path, help="PDF file or directory containing PDFs")
    parser.add_argument("--output", type=Path, help="Directory for JSON outputs")
    parser.add_argument("--limit", type=int, help="Maximum number of PDFs to process")
    parser.add_argument("--skip-existing", action="store_true", help="Skip PDFs with existing Docling outputs")
    args = parser.parse_args()
    run(args.input, args.output, limit=args.limit, skip_existing=args.skip_existing)


if __name__ == "__main__":
    main()
