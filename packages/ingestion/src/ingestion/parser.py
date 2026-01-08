"""
LlamaParse-powered PDF parser tailored for WeedAI herbicide labels.

The module streams PDFs through LlamaCloud to obtain high fidelity markdown that
preserves tables and layout, then enriches the output with domain metadata
required by downstream GraphRAG loaders.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Dict, Optional, Sequence

from dotenv import load_dotenv

try:
    from llama_parse import LlamaParse
except ImportError as exc:  # pragma: no cover - surfaced during installation issues
    raise ImportError("llama-parse is required. Install via `uv add llama-parse --package packages/ingestion`.") from exc


# ---------------------------------------------------------------------------
# Repository paths
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).parent.parent.parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
LABELS_DIR = DATA_DIR / "labels"
PARSED_DIR = DATA_DIR / "parsed"
METADATA_FILE = PARSED_DIR / "parsing_metadata.json"
DOTENV_PATH = ROOT_DIR / ".env"

PARSED_DIR.mkdir(parents=True, exist_ok=True)
load_dotenv(dotenv_path=DOTENV_PATH, override=False)


# ---------------------------------------------------------------------------
# LlamaParse configuration
# ---------------------------------------------------------------------------

PARSING_INSTRUCTION = """
You are parsing Australian herbicide labels for ingestion into a knowledge graph.

Extract ALL agronomic content with the following priorities:
1. Preserve Directions for Use tables exactly, including merged table headers.
2. Capture Active constituent, Herbicide mode of action group, APVMA approval number.
3. Normalize crop, weed, and rate columns; retain growth stage descriptions verbatim.
4. Include all critical comments, re-entry periods, withholding periods, and plant-back information.
5. Ignore storage, packaging, transport, headers and footers and minor regulatory boilerplate unless it affects field usage.

Return the document as clean markdown preserving hierarchy, bullet lists, and tables.
""".strip()


def create_parser(
    *,
    api_key: Optional[str] = None,
    language: str = "en",
    result_type: str = "markdown",
    premium: bool = True,
    continuous: bool = True,
    gpt4o: bool = False,
    verbose: bool = False,
) -> LlamaParse:
    """Instantiate a configured LlamaParse client."""

    key = api_key or os.getenv("LLAMA_CLOUD_API_KEY")
    if not key:
        raise ValueError("LLAMA_CLOUD_API_KEY is required to use LlamaParse")

    kwargs: Dict[str, object] = {
        "api_key": key.strip().strip('"'),
        "result_type": result_type,
        "language": language,
        "parsing_instruction": PARSING_INSTRUCTION,
        "num_workers": 1,
        "verbose": verbose,
    }

    if premium:
        kwargs["premium_mode"] = True
    if continuous:
        kwargs["continuous_mode"] = True
    if gpt4o:
        kwargs["gpt4o_mode"] = True

    return LlamaParse(**kwargs)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _document_text(document) -> str:
    """Safely extract text from a LlamaParse document."""

    if hasattr(document, "text") and document.text:
        return document.text
    if hasattr(document, "get_content"):
        content = document.get_content()
        if content:
            return content
    return str(document)


def _ensure_mapping(candidate) -> Dict[str, object]:
    if isinstance(candidate, dict):
        return candidate
    return {}


def _infer_page_count(documents: Sequence) -> int:
    """Infer the number of pages from parser metadata when available."""

    candidates = []
    for doc in documents:
        metadata = _ensure_mapping(getattr(doc, "metadata", None))
        extra = _ensure_mapping(getattr(doc, "extra_info", None))
        for payload in (metadata, extra):
            for key in ("num_pages", "page_count", "pages", "total_pages"):
                value = payload.get(key)
                if isinstance(value, int) and value > 0:
                    candidates.append(value)
            page_labels = payload.get("page_labels")
            if isinstance(page_labels, (list, tuple)) and page_labels:
                candidates.append(len(page_labels))
    if candidates:
        return max(candidates)
    return max(len(documents), 0)


def extract_product_metadata(text: str, filename: str) -> Dict[str, object]:
    """Extract key metadata fields used by downstream loaders."""

    metadata: Dict[str, object] = {
        "product_number": filename.replace("ELBL", "").replace(".pdf", ""),
        "source_file": filename,
    }

    name_match = re.search(r"Product Name:\s*\n?\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    if name_match:
        metadata["product_name"] = name_match.group(1).strip()

    apvma_match = re.search(r"APVMA Approval No:\s*\n?\s*(\d+(?:\s*/\s*\d+)?)", text, re.IGNORECASE)
    if apvma_match:
        metadata["apvma_number"] = apvma_match.group(1).strip()

    active_match = re.search(
        r"Active Constituent[s]?:\s*\n?\s*(.+?)(?:\n\n|\nMode|\nStatement|\nNet)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if active_match:
        metadata["active_constituent"] = active_match.group(1).strip().replace("\n", " ")

    group_match = re.search(r"GROUP\s+([A-Z0-9]+)\s+HERBICIDE", text, re.IGNORECASE)
    if group_match:
        metadata["mode_of_action_group"] = group_match.group(1)

    return metadata


def _build_frontmatter(metadata: Dict[str, object]) -> str:
    """Render YAML frontmatter for parsed documents."""

    lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, str) and (":" in value or "\n" in value or '"' in value):
            safe = value.replace('"', '\"')
            lines.append(f"{key}: \"{safe}\"")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---\n\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def parse_pdf(
    parser: LlamaParse,
    pdf_path: Path,
    output_path: Path,
    *,
    force: bool = False,
) -> Dict[str, object]:
    """Parse a single herbicide label with LlamaParse."""

    pdf_path = Path(pdf_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result: Dict[str, object] = {
        "success": False,
        "skipped": False,
        "error": None,
        "pages": 0,
        "metadata": {},
    }

    if output_path.exists() and not force:
        result["success"] = True
        result["skipped"] = True
        return result

    try:
        if not hasattr(parser, "aload_data"):
            raise TypeError("parser must expose an `aload_data` coroutine")

        documents = await parser.aload_data(str(pdf_path))
        if not documents:
            raise ValueError("LlamaParse returned no documents")

        combined_text = "\n\n".join(_document_text(doc) for doc in documents)
        if not combined_text.strip():
            raise ValueError("Parsed output is empty")

        metadata = extract_product_metadata(combined_text, pdf_path.name)
        metadata["pages"] = _infer_page_count(documents)
        metadata["parser"] = "llama-parse"
        result["metadata"] = metadata
        result["pages"] = metadata["pages"]

        frontmatter = _build_frontmatter(metadata)
        output_path.write_text(frontmatter + combined_text, encoding="utf-8")

        result["success"] = True
        return result

    except Exception as exc:  # pragma: no cover - tested via unit mocks
        result["error"] = str(exc)
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        return result


def load_metadata() -> Dict[str, object]:
    """Load existing parsing metadata."""

    if METADATA_FILE.exists():
        return json.loads(METADATA_FILE.read_text(encoding="utf-8"))
    return {"parsed": {}, "failed": []}


def save_metadata(metadata: Dict[str, object]) -> None:
    """Persist parsing metadata to disk."""

    METADATA_FILE.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


async def parse_directory(
    parser: LlamaParse,
    *,
    force: bool = False,
) -> Dict[str, int]:
    """Parse every PDF in the labels directory sequentially."""

    pdf_files = sorted(LABELS_DIR.glob("*.pdf"))
    metadata_store = load_metadata()

    stats = {"parsed": 0, "skipped": 0, "failed": 0}

    for pdf_path in pdf_files:
        output_path = PARSED_DIR / f"{pdf_path.stem}.md"
        result = await parse_pdf(parser, pdf_path, output_path, force=force)

        if result["skipped"]:
            stats["skipped"] += 1
            continue

        if result["success"]:
            stats["parsed"] += 1
            metadata_store.setdefault("parsed", {})[pdf_path.stem] = {
                "pages": result["pages"],
                "output": output_path.name,
                **result.get("metadata", {}),
            }
            failed = metadata_store.setdefault("failed", [])
            if pdf_path.stem in failed:
                failed.remove(pdf_path.stem)
        else:
            stats["failed"] += 1
            failed = metadata_store.setdefault("failed", [])
            if pdf_path.stem not in failed:
                failed.append(pdf_path.stem)

    save_metadata(metadata_store)
    return stats


async def parse_single(
    pdf_name: str,
    *,
    force: bool = False,
    parser: Optional[LlamaParse] = None,
) -> Dict[str, object]:
    """Parse a single PDF by name (helper for notebooks/tests)."""

    name = pdf_name if pdf_name.endswith(".pdf") else f"{pdf_name}.pdf"
    pdf_path = LABELS_DIR / name
    if not pdf_path.exists():
        return {"success": False, "error": f"PDF not found: {pdf_path}"}

    output_path = PARSED_DIR / f"{pdf_path.stem}.md"
    client = parser or create_parser()
    return await parse_pdf(client, pdf_path, output_path, force=force)


def _format_stats(stats: Dict[str, int]) -> str:
    return (
        "\n" + "=" * 60 +
        "\nPARSING COMPLETE\n" + "=" * 60 +
        f"\nParsed:   {stats['parsed']}" +
        f"\nSkipped:  {stats['skipped']}" +
        f"\nFailed:   {stats['failed']}\n"
    )


def main() -> None:
    """CLI entrypoint for batch parsing."""

    import argparse

    parser = argparse.ArgumentParser("WeedAI LlamaParse pipeline")
    parser.add_argument("--single", "-s", type=str, help="Parse a single PDF by stem or filename")
    parser.add_argument("--force", "-f", action="store_true", help="Re-parse even if markdown exists")
    parser.add_argument("--api-key", type=str, help="Override LLAMA_CLOUD_API_KEY")
    parser.add_argument("--language", type=str, default="en", help="Document language hint")
    parser.add_argument("--no-premium", action="store_true", help="Disable premium mode")
    parser.add_argument("--no-continuous", action="store_true", help="Disable continuous mode")
    parser.add_argument("--gpt4o", action="store_true", help="Enable GPT-4o markdown mode")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging from LlamaParse")

    args = parser.parse_args()

    client = create_parser(
        api_key=args.api_key,
        language=args.language,
        premium=not args.no_premium,
        continuous=not args.no_continuous,
        gpt4o=args.gpt4o,
        verbose=args.verbose,
    )

    if args.single:
        name = args.single

        async def run_single() -> None:
            result = await parse_single(name, force=args.force, parser=client)
            if result.get("success"):
                print(f"✓ Parsed {name} -> {PARSED_DIR / f'{Path(name).stem}.md'}")
            elif result.get("skipped"):
                print(f"⊘ Skipped existing markdown for {name}")
            else:
                print(f"✗ Failed {name}: {result.get('error')}")

        asyncio.run(run_single())
        return

    async def run_batch() -> None:
        stats = await parse_directory(client, force=args.force)
        print(_format_stats(stats))
        print(f"Output directory: {PARSED_DIR}")
        print(f"Metadata saved to: {METADATA_FILE}")

    asyncio.run(run_batch())


if __name__ == "__main__":
    main()
