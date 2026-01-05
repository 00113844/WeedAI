"""
Gemini-based structured extractor for parsed herbicide label markdown files.

Reads the already-parsed .md files and uses Gemini to extract structured
data into a clean JSON schema optimized for GraphRAG.
"""

import json
import asyncio
import time
import signal
from pathlib import Path
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import os

from google import genai
from google.genai import types


# Load environment variables
load_dotenv()


class APITimeoutError(Exception):
    """Raised when API call times out."""
    pass


# ============== PYDANTIC SCHEMA FOR HERBICIDE DATA ==============

class WeedControlEntry(BaseModel):
    """A single weed control entry from the Directions for Use table."""
    crop: str = Field(description="The crop this herbicide is registered for")
    application_timing: Optional[str] = Field(default=None, description="Pre-emergence, post-emergence, or other timing")
    weed_common_name: str = Field(description="Common name of the weed controlled")
    weed_scientific_name: Optional[str] = Field(default=None, description="Scientific name if provided")
    states: list[str] = Field(description="Australian states where registered (NSW, VIC, QLD, SA, WA, TAS, NT, ACT)")
    rate_per_ha: str = Field(description="Application rate per hectare")
    critical_comments: Optional[str] = Field(default=None, description="Important application notes")
    control_level: str = Field(default="control", description="control, suppression, or partial")


class HerbicideLabel(BaseModel):
    """Structured representation of an APVMA herbicide label."""
    # Product identification
    product_number: str = Field(description="APVMA product number")
    product_name: str = Field(description="Commercial product name")
    
    # Active constituent
    active_constituent: str = Field(description="Active ingredient with concentration")
    chemical_group: Optional[str] = Field(default=None, description="Chemical group name")
    mode_of_action_group: str = Field(description="Herbicide mode of action group letter (A-Z)")
    
    # Registered uses - THE KEY DATA FOR GRAPHRAG
    registered_crops: list[str] = Field(description="All crops this herbicide is registered for")
    registered_weeds: list[str] = Field(description="All weeds this herbicide controls (common names)")
    weed_control_entries: list[WeedControlEntry] = Field(description="Detailed weed control entries")
    
    # Application
    application_methods: list[str] = Field(default_factory=list, description="Ground spray, aerial, etc.")
    
    # Restrictions
    state_restrictions: list[str] = Field(default_factory=list, description="States where use is restricted")
    withholding_period: Optional[str] = Field(default=None, description="Withholding period")
    
    # Compatibility
    compatible_products: list[str] = Field(default_factory=list, description="Tank mix compatible products")


# ============== GEMINI CLIENT ==============

def get_client() -> genai.Client:
    """Initialize Gemini client with API key."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")
    return genai.Client(api_key=api_key.strip('"'))


EXTRACTION_PROMPT = """You are an expert agricultural data extractor specializing in Australian herbicide labels.

Analyze this parsed herbicide label markdown and extract ALL relevant information into the structured schema.

CRITICAL EXTRACTION RULES:
1. **product_number**: Extract the 5-digit APVMA number from frontmatter or content
2. **product_name**: The commercial name (e.g., "SPINNAKER", "ESTERCIDE 800")
3. **active_constituent**: Full text including concentration (e.g., "240 g/L IMAZETHAPYR")
4. **mode_of_action_group**: Single letter A-Z from "GROUP X HERBICIDE" text
5. **registered_crops**: List ALL crops from the Directions table (wheat, barley, chickpeas, etc.)
6. **registered_weeds**: List ALL weed common names mentioned
7. **weed_control_entries**: Create ONE entry per crop+weed combination found in tables

FOR WEED CONTROL ENTRIES:
- Extract EACH weed separately (don't combine multiple weeds in one entry)
- Scientific names are in parentheses or italics: _Raphanus raphanistrum_
- States should be abbreviated: NSW, VIC, QLD, SA, WA, TAS, NT, ACT
- If states say "all states" or similar, list all 8 states
- control_level: "control" unless "suppression" or "partial" is mentioned

If data is missing or the document appears empty, return minimal valid data with empty lists.

MARKDOWN CONTENT TO EXTRACT:
"""


def _call_gemini(client, model, content, prompt):
    """Internal function to call Gemini API (for timeout wrapper)."""
    response = client.models.generate_content(
        model=model,
        contents=prompt + "\n\n" + content,
        config=types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=HerbicideLabel,
            temperature=0.1,
            http_options={'timeout': 60000},  # 60 second HTTP timeout
        )
    )
    if response.parsed:
        return response.parsed.model_dump()
    else:
        return json.loads(response.text)


def extract_from_markdown(
    markdown_content: str,
    client: genai.Client,
    model: str = "gemini-2.5-flash-lite",
    timeout_seconds: int = 90
) -> dict:
    """
    Extract structured data from markdown using Gemini with timeout.
    
    Args:
        markdown_content: The markdown text to process
        client: Gemini client instance
        model: Model to use
        timeout_seconds: Maximum seconds to wait for API response
    
    Returns:
        Dictionary with extracted herbicide data
    
    Raises:
        APITimeoutError: If the API call takes longer than timeout_seconds
    """
    # Truncate very long content to avoid timeouts (keep first 15000 chars)
    if len(markdown_content) > 15000:
        markdown_content = markdown_content[:15000] + "\n\n[... content truncated ...]"
    
    # Use ThreadPoolExecutor for timeout handling
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_call_gemini, client, model, markdown_content, EXTRACTION_PROMPT)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError:
            raise APITimeoutError(f"API call timed out after {timeout_seconds} seconds")


def process_single_file(
    md_path: Path,
    output_path: Path,
    client: genai.Client,
    model: str = "gemini-2.5-flash-lite"
) -> dict:
    """Process a single markdown file."""
    content = md_path.read_text(encoding='utf-8')
    
    # Skip very short files (likely empty or failed parses)
    if len(content.strip()) < 100:
        return {
            'status': 'skipped',
            'reason': 'content too short',
            'file': md_path.name
        }
    
    try:
        data = extract_from_markdown(content, client, model)
        
        # Add metadata
        data['_metadata'] = {
            'source_file': md_path.name,
            'extracted_at': datetime.now().isoformat(),
            'model': model
        }
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save JSON
        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        
        return {
            'status': 'success',
            'file': md_path.name,
            'crops': len(data.get('registered_crops', [])),
            'weeds': len(data.get('registered_weeds', [])),
            'entries': len(data.get('weed_control_entries', []))
        }
    
    except APITimeoutError as e:
        return {
            'status': 'timeout',
            'file': md_path.name,
            'error': str(e)
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'file': md_path.name,
            'error': str(e)
        }


def process_directory(
    input_dir: Path,
    output_dir: Path,
    model: str = "gemini-2.0-flash",
    delay: float = 0.5,
    limit: int = None
) -> dict:
    """
    Process all markdown files in a directory.
    
    Args:
        input_dir: Directory containing .md files
        output_dir: Directory for JSON output
        model: Gemini model to use
        delay: Delay between API calls (rate limiting)
        limit: Maximum files to process (None = all)
    
    Returns:
        Summary statistics
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get markdown files (exclude metadata files)
    md_files = [f for f in input_dir.glob("*.md") 
                if not f.name.startswith('_') 
                and 'cleaned' not in f.name
                and 'test' not in f.name]
    
    if limit:
        md_files = md_files[:limit]
    
    client = get_client()
    
    results = {
        'success': [],
        'error': [],
        'skipped': [],
        'timeout': []
    }
    
    total = len(md_files)
    
    for i, md_path in enumerate(md_files, 1):
        output_path = output_dir / f"{md_path.stem}.json"
        
        # Skip if already processed
        if output_path.exists():
            results['skipped'].append(md_path.name)
            continue
        
        print(f"[{i}/{total}] Processing: {md_path.name}")
        
        result = process_single_file(md_path, output_path, client, model)
        
        if result['status'] == 'success':
            results['success'].append(result)
            print(f"  ✓ Extracted: {result['crops']} crops, {result['weeds']} weeds, {result['entries']} entries")
        elif result['status'] == 'skipped':
            results['skipped'].append(result)
            print(f"  ○ Skipped: {result.get('reason', 'unknown')}")
        elif result['status'] == 'timeout':
            results['timeout'].append(result)
            print(f"  ⏱ Timeout: {result.get('error', 'API too slow')}")
        else:
            results['error'].append(result)
            print(f"  ✗ Error: {result.get('error', 'unknown')}")
        
        # Rate limiting
        if i < total:
            time.sleep(delay)
    
    # Summary
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_files': total,
        'succeeded': len(results['success']),
        'errors': len(results['error']),
        'timeouts': len(results['timeout']),
        'skipped': len(results['skipped']),
        'model': model,
        'error_details': results['error'],
        'timeout_files': [r['file'] for r in results['timeout']]
    }
    
    # Save summary
    summary_path = output_dir / '_extraction_summary.json'
    summary_path.write_text(json.dumps(summary, indent=2))
    
    return summary


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Extract structured data from parsed herbicide markdown files using Gemini'
    )
    parser.add_argument(
        'input',
        type=Path,
        help='Input markdown file or directory'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Output JSON file or directory'
    )
    parser.add_argument(
        '--model',
        default='gemini-2.5-flash-lite',
        help='Gemini model (default: gemini-2.5-flash-lite)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='Delay between API calls in seconds (default: 0.5)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Maximum files to process (default: all)'
    )
    
    args = parser.parse_args()
    
    if args.input.is_file():
        # Single file
        output = args.output or args.input.with_suffix('.json')
        client = get_client()
        
        print(f"Processing: {args.input}")
        result = process_single_file(args.input, output, client, args.model)
        
        if result['status'] == 'success':
            print(f"\n✓ Success!")
            print(f"  Output: {output}")
            print(f"  Crops: {result['crops']}")
            print(f"  Weeds: {result['weeds']}")
            print(f"  Entries: {result['entries']}")
        else:
            print(f"\n✗ {result['status']}: {result.get('error', result.get('reason', 'unknown'))}")
    
    else:
        # Directory
        output_dir = args.output or (args.input.parent / 'extracted')
        print(f"Processing directory: {args.input}")
        print(f"Output directory: {output_dir}")
        print(f"Model: {args.model}")
        print(f"Delay: {args.delay}s")
        if args.limit:
            print(f"Limit: {args.limit} files")
        print()
        
        summary = process_directory(
            args.input,
            output_dir,
            model=args.model,
            delay=args.delay,
            limit=args.limit
        )
        
        print(f"\n{'='*50}")
        print(f"EXTRACTION COMPLETE")
        print(f"{'='*50}")
        print(f"Total files: {summary['total_files']}")
        print(f"Succeeded: {summary['succeeded']}")
        print(f"Errors: {summary['errors']}")
        print(f"Timeouts: {summary['timeouts']}")
        print(f"Skipped: {summary['skipped']}")
        
        if summary['timeout_files']:
            print(f"\nTimeout files (can retry later):")
            for f in summary['timeout_files']:
                print(f"  - {f}")


if __name__ == '__main__':
    main()
