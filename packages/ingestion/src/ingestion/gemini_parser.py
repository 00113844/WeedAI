"""
Graph-optimized Gemini parser for herbicide label PDFs.

Extracts structured, graph-ready data (crops, weeds, constraints, rates) for Neo4j/GraphRAG.
"""

import json
import asyncio
import time
import os
from pathlib import Path
from typing import Optional, Literal, List
from datetime import datetime

from pydantic import BaseModel, Field
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from google import genai
from google.genai import types
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, InternalServerError


# Load environment variables
load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / '.env')


# ==========================================
# 1. GRAPH-OPTIMIZED SCHEMA
# ==========================================

StateEnum = Literal['NSW', 'VIC', 'QLD', 'SA', 'WA', 'TAS', 'NT', 'ACT', 'All States']
ConstraintType = Literal['Weather', 'Timing', 'Equipment', 'TankMix', 'Safety', 'Rate', 'Soil']


class Constraint(BaseModel):
    """Atomic restriction from critical comments."""
    type: ConstraintType = Field(description="Constraint category")
    description: str = Field(description="Specific restriction")


class WeedControlEdge(BaseModel):
    """CONTROLS relationship between crop and weed with rate/constraints."""

    crop: str = Field(description="Standardized crop name")
    weed_common_name: str = Field(description="Standardized weed common name")
    weed_scientific_name: Optional[str] = Field(default=None, description="Scientific name if available")

    states: List[StateEnum] = Field(description="States where this use is registered")

    rate_value: float = Field(description="Numeric rate value (use max if range)")
    rate_unit: str = Field(description="Rate unit (e.g., L/ha, mL/ha, g/ha)")
    rate_full_text: str = Field(description="Original rate text")

    growth_stage_weed: Optional[str] = Field(default=None, description="Max weed size/stage")
    growth_stage_crop: Optional[str] = Field(default=None, description="Crop stage restrictions")
    constraints: List[Constraint] = Field(default_factory=list, description="Structured constraints")


class HerbicideLabel(BaseModel):
    """Root node container for graph ingestion."""

    product_name: str
    apvma_number: str
    active_constituents: List[str]
    moa_number: Optional[str] = Field(default=None, description="HRAC global numeric MoA code (preferred)")
    moa_legacy_letter: Optional[str] = Field(default=None, description="Legacy MoA letter (for transition)")

    identified_crops: List[str] = Field(description="Unique crops mentioned")
    identified_weeds: List[str] = Field(description="Unique weeds mentioned")

    usage_scenarios: List[WeedControlEdge] = Field(description="Edges Crop->Weed with rate/constraints")


# ==========================================
# 2. GEMINI CLIENT & PROMPT
# ==========================================


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")
    return genai.Client(api_key=api_key.strip().strip('"'))


GRAPH_EXTRACTION_PROMPT = """
You are a Data Engineer converting Herbicide Labels into a Knowledge Graph.

Extract the entire "Directions for Use" table into structured JSON.

CRITICAL RULES FOR GRAPH DATA:
1) Row Expansion: If a crop header covers multiple weed rows, repeat the crop for every weed row.
2) Entity Normalization: Split lists (e.g., "Wheat, Barley, Oats") into separate entries; standardize names ("Wheat (Spring)" -> "Wheat").
3) Rate Parsing: Split "1.5 L/ha" into value=1.5 and unit="L/ha". If a range is present ("1.0 - 1.5 L/ha"), use the MAX value.
4) Constraint Extraction: Do NOT dump critical comments. Break into atomic constraints with types: Weather, Timing, Equipment, TankMix, Safety, Rate, Soil.
   Example: "Apply at 3-leaf stage. Do not spray if rain is likely." ->
   Constraint(type="Timing", description="Apply at 3-leaf stage")
   Constraint(type="Weather", description="Do not spray if rain is likely")
5) States: Convert "All States" to the full list [NSW, VIC, QLD, SA, WA, TAS, NT, ACT].
6) Mode of Action: Return the global HRAC numeric MoA code in `moa_number`. If the label only shows the legacy letter, put it in `moa_legacy_letter` and leave `moa_number` blank.

Return the JSON adhering strictly to the provided schema. Temperature = 0.0 for deterministic extraction.
"""


# ==========================================
# 3. RETRY LOGIC (Exponential Backoff)
# ==========================================


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type((ResourceExhausted, ServiceUnavailable, InternalServerError))
)
def generate_with_retry(client, model, contents, config):
    return client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )


# ==========================================
# 4. PARSING LOGIC
# ==========================================


async def parse_pdf_graph_ready(
    pdf_path: Path,
    client: genai.Client,
    model: str = "gemini-2.5-flash"
) -> dict:
    """Upload PDF, extract graph-ready JSON, and clean up the uploaded file."""

    uploaded_file = client.files.upload(
        file=str(pdf_path),
        config=types.UploadFileConfig(
            display_name=pdf_path.name,
            mime_type='application/pdf'
        )
    )

    while uploaded_file.state == 'PROCESSING':
        await asyncio.sleep(1)
        uploaded_file = client.files.get(name=uploaded_file.name)

    if uploaded_file.state != 'ACTIVE':
        raise RuntimeError(f"File upload failed with state: {uploaded_file.state}")

    try:
        response = await asyncio.to_thread(
            generate_with_retry,
            client,
            model,
            [uploaded_file, GRAPH_EXTRACTION_PROMPT],
            types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema=HerbicideLabel,
                temperature=0.0,
            ),
        )

        if response.parsed:
            data = response.parsed.model_dump()
        else:
            data = json.loads(response.text)

        if not data.get('usage_scenarios'):
            print(f"  ⚠️ No usage_scenarios extracted for {pdf_path.name}")

        return data

    finally:
        try:
            client.files.delete(name=uploaded_file.name)
        except Exception:
            pass


async def parse_all_pdfs(
    input_dir: Path,
    output_dir: Path,
    model: str = "gemini-2.5-flash",
    max_concurrent: int = 2,
    delay_between: float = 2.5
) -> dict:
    """Process all PDFs in a directory with concurrency and backoff."""

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = list(input_dir.glob("*.pdf"))
    client = get_client()

    results = {
        'succeeded': [],
        'failed': [],
        'skipped': []
    }

    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_one(pdf_path: Path) -> None:
        output_path = output_dir / f"{pdf_path.stem}.json"

        if output_path.exists():
            results['skipped'].append(pdf_path.name)
            return

        async with semaphore:
            try:
                print(f"Processing: {pdf_path.name}")
                data = await parse_pdf_graph_ready(pdf_path, client, model)

                data['_meta'] = {
                    'source_file': pdf_path.name,
                    'parsed_at': datetime.now().isoformat(),
                    'model': model,
                }

                output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
                results['succeeded'].append(pdf_path.name)
                print(f"  ✓ Saved: {output_path.name}")

            except Exception as e:
                print(f"  ✗ Error: {pdf_path.name} - {e}")
                results['failed'].append({'file': pdf_path.name, 'error': str(e)})

            await asyncio.sleep(delay_between)

    tasks = [process_one(pdf) for pdf in pdf_files]
    await asyncio.gather(*tasks)

    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_files': len(pdf_files),
        'succeeded': len(results['succeeded']),
        'failed': len(results['failed']),
        'skipped': len(results['skipped']),
        'model': model,
        'failed_files': results['failed'],
    }

    (output_dir / 'extraction_summary.json').write_text(json.dumps(summary, indent=2))
    return summary


def parse_single(pdf_path: str, output_path: str = None, model: str = "gemini-2.5-flash") -> dict:
    pdf_path = Path(pdf_path)
    client = get_client()
    data = asyncio.run(parse_pdf_graph_ready(pdf_path, client, model))

    data['_meta'] = {
        'source_file': pdf_path.name,
        'parsed_at': datetime.now().isoformat(),
        'model': model,
    }

    if output_path:
        Path(output_path).write_text(json.dumps(data, indent=2, ensure_ascii=False))

    return data


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Parse herbicide label PDFs into graph-ready JSON using Gemini')
    parser.add_argument('input', type=Path, help='Input PDF file or directory')
    parser.add_argument('-o', '--output', type=Path, help='Output JSON file or directory')
    parser.add_argument('--model', default='gemini-2.5-flash', help='Gemini model to use (default: gemini-2.5-flash)')
    parser.add_argument('--max-concurrent', type=int, default=2, help='Maximum concurrent requests (default: 2)')
    parser.add_argument('--delay', type=float, default=2.5, help='Delay between requests in seconds (default: 2.5)')

    args = parser.parse_args()

    if args.input.is_file():
        output = args.output or args.input.with_suffix('.json')
        print(f"Parsing: {args.input}")
        data = parse_single(str(args.input), str(output), model=args.model)
        print(f"Output: {output}")
        print(f"Usage scenarios: {len(data.get('usage_scenarios', []))}")
    else:
        output_dir = args.output or args.input.parent / 'extracted'
        print(f"Processing directory: {args.input}")
        summary = asyncio.run(parse_all_pdfs(
            args.input,
            output_dir,
            model=args.model,
            max_concurrent=args.max_concurrent,
            delay_between=args.delay,
        ))
        print("\nComplete!")
        print(f"Succeeded: {summary['succeeded']}")
        print(f"Failed: {summary['failed']}")
        print(f"Skipped: {summary['skipped']}")


if __name__ == '__main__':
    main()
