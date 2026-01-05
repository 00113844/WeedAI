"""
Gemini-based structured parser for herbicide label PDFs.

Uses Google's Gemini API with structured output to extract
herbicide data directly from PDFs into a JSON schema optimized for GraphRAG.
"""

import json
import asyncio
import time
from pathlib import Path
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

from google import genai
from google.genai import types


# Load environment variables
load_dotenv()


# ============== PYDANTIC SCHEMA FOR HERBICIDE DATA ==============

class WeedControlEntry(BaseModel):
    """A single weed control entry from the Directions for Use table."""
    crop: str = Field(description="The crop this herbicide is registered for (e.g., 'wheat', 'chickpeas', 'faba beans')")
    application_timing: str = Field(description="Pre-emergence, post-emergence, or other timing (e.g., 'Pre-emergence', 'Post-emergence', 'Pre-plant')")
    weed_common_name: str = Field(description="Common name of the weed controlled (e.g., 'wild radish', 'annual ryegrass')")
    weed_scientific_name: Optional[str] = Field(default=None, description="Scientific name of the weed if provided (e.g., 'Raphanus raphanistrum')")
    states: list[str] = Field(description="Australian states where this use is registered (e.g., ['NSW', 'VIC', 'SA'])")
    rate_per_ha: str = Field(description="Application rate per hectare (e.g., '200mL', '1.0-1.5L')")
    critical_comments: Optional[str] = Field(default=None, description="Important application notes or conditions")
    control_level: Optional[str] = Field(default=None, description="Level of control: 'control', 'suppression', or 'partial control'")


class HerbicideLabel(BaseModel):
    """Structured representation of an APVMA herbicide label."""
    # Product identification
    product_number: str = Field(description="APVMA product number (e.g., '45835')")
    product_name: str = Field(description="Commercial product name (e.g., 'SPINNAKER')")
    
    # Active constituent
    active_constituent: str = Field(description="Active ingredient with concentration (e.g., '240 g/L IMAZETHAPYR')")
    chemical_group: str = Field(description="Chemical group name (e.g., 'Imidazolinone', 'Phenoxy')")
    mode_of_action_group: str = Field(description="Herbicide mode of action group letter (e.g., 'B', 'I', 'M')")
    mode_of_action_description: Optional[str] = Field(default=None, description="Description of mode of action (e.g., 'inhibition of acetolactate synthase (ALS)')")
    
    # Registered uses
    registered_crops: list[str] = Field(description="List of all crops this herbicide is registered for")
    weed_control_entries: list[WeedControlEntry] = Field(description="Detailed weed control entries from the Directions for Use table")
    
    # Application information
    application_methods: list[str] = Field(default_factory=list, description="Application methods (e.g., ['ground boom spray', 'aerial application'])")
    water_rate: Optional[str] = Field(default=None, description="Water volume for application (e.g., '50-100 L/ha')")
    
    # Restrictions
    restraints: list[str] = Field(default_factory=list, description="Key restraints and restrictions")
    withholding_period: Optional[str] = Field(default=None, description="Withholding period for grazing/harvest")
    
    # Compatibility
    compatible_products: list[str] = Field(default_factory=list, description="Products compatible for tank mixing")
    incompatible_products: list[str] = Field(default_factory=list, description="Products NOT to be tank mixed with")


# ============== GEMINI CLIENT ==============

def get_client() -> genai.Client:
    """Initialize Gemini client with API key."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")
    return genai.Client(api_key=api_key.strip('"'))


EXTRACTION_PROMPT = """You are an expert agricultural scientist specializing in herbicide labels.

Analyze this APVMA (Australian Pesticides and Veterinary Medicines Authority) herbicide label PDF and extract all relevant information into the structured schema provided.

IMPORTANT INSTRUCTIONS:
1. Extract ALL weed control entries from the "Directions for Use" table - each crop/weed combination should be a separate entry
2. For weeds, separate common name and scientific name (in parentheses/italics)
3. States should be normalized to abbreviations: NSW, VIC, QLD, SA, WA, TAS, NT, ACT
4. The product_number is usually a 5-digit number like "45835"
5. Mode of action groups are single letters (A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P, Q, R, S, Z)
6. If control_level is not specified, assume "control" unless words like "suppression" or "partial" are mentioned
7. Extract application timing (pre-emergence, post-emergence) from the crop column or context
8. Be thorough - extract every single weed and crop combination from the table

Focus on extracting information useful for herbicide selection:
- What weeds does this control?
- In what crops is it registered?
- What is the mode of action (for resistance management)?
- What are the application rates and timing?
"""


async def parse_pdf_with_gemini(
    pdf_path: Path,
    client: genai.Client,
    model: str = "gemini-2.5-flash"
) -> dict:
    """
    Parse a single PDF using Gemini's vision capabilities and structured output.
    
    Args:
        pdf_path: Path to the PDF file
        client: Gemini client instance
        model: Model to use (default: gemini-2.5-flash)
    
    Returns:
        Dictionary with parsed herbicide data
    """
    # Upload the PDF file
    uploaded_file = client.files.upload(
        file=str(pdf_path),
        config=types.UploadFileConfig(
            display_name=pdf_path.name,
            mime_type='application/pdf'
        )
    )
    
    # Wait for file to be processed
    while uploaded_file.state == 'PROCESSING':
        time.sleep(1)
        uploaded_file = client.files.get(name=uploaded_file.name)
    
    if uploaded_file.state != 'ACTIVE':
        raise RuntimeError(f"File upload failed with state: {uploaded_file.state}")
    
    # Generate structured content
    response = client.models.generate_content(
        model=model,
        contents=[
            uploaded_file,
            EXTRACTION_PROMPT
        ],
        config=types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=HerbicideLabel,
            temperature=0.1,  # Low temperature for consistent extraction
        )
    )
    
    # Clean up uploaded file
    try:
        client.files.delete(name=uploaded_file.name)
    except Exception:
        pass  # Ignore cleanup errors
    
    # Parse response
    if response.parsed:
        return response.parsed.model_dump()
    else:
        return json.loads(response.text)


async def parse_all_pdfs(
    input_dir: Path,
    output_dir: Path,
    model: str = "gemini-2.5-flash",
    max_concurrent: int = 5,
    delay_between: float = 1.0
) -> dict:
    """
    Parse all PDFs in a directory using Gemini.
    
    Args:
        input_dir: Directory containing PDF files
        output_dir: Directory for JSON output
        model: Gemini model to use
        max_concurrent: Maximum concurrent requests (be mindful of rate limits)
        delay_between: Delay between requests in seconds
    
    Returns:
        Summary statistics
    """
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
        
        # Skip if already processed
        if output_path.exists():
            results['skipped'].append(pdf_path.name)
            return
        
        async with semaphore:
            try:
                print(f"Processing: {pdf_path.name}")
                data = await parse_pdf_with_gemini(pdf_path, client, model)
                
                # Add metadata
                data['_metadata'] = {
                    'source_file': pdf_path.name,
                    'parsed_at': datetime.now().isoformat(),
                    'model': model
                }
                
                # Save JSON
                output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
                results['succeeded'].append(pdf_path.name)
                print(f"  ✓ Saved: {output_path.name}")
                
            except Exception as e:
                print(f"  ✗ Error: {pdf_path.name} - {e}")
                results['failed'].append({'file': pdf_path.name, 'error': str(e)})
            
            # Rate limiting delay
            await asyncio.sleep(delay_between)
    
    # Process all files
    tasks = [process_one(pdf) for pdf in pdf_files]
    await asyncio.gather(*tasks)
    
    # Summary
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_files': len(pdf_files),
        'succeeded': len(results['succeeded']),
        'failed': len(results['failed']),
        'skipped': len(results['skipped']),
        'model': model,
        'failed_files': results['failed']
    }
    
    # Save summary
    summary_path = output_dir / 'extraction_summary.json'
    summary_path.write_text(json.dumps(summary, indent=2))
    
    return summary


def parse_single(pdf_path: str, output_path: str = None) -> dict:
    """
    Synchronous wrapper to parse a single PDF.
    
    Args:
        pdf_path: Path to PDF file
        output_path: Optional path for JSON output
    
    Returns:
        Parsed herbicide data
    """
    pdf_path = Path(pdf_path)
    client = get_client()
    
    # Run async function
    data = asyncio.run(parse_pdf_with_gemini(pdf_path, client))
    
    # Add metadata
    data['_metadata'] = {
        'source_file': pdf_path.name,
        'parsed_at': datetime.now().isoformat(),
        'model': 'gemini-2.5-flash'
    }
    
    if output_path:
        Path(output_path).write_text(json.dumps(data, indent=2, ensure_ascii=False))
    
    return data


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Parse herbicide label PDFs using Gemini API'
    )
    parser.add_argument(
        'input',
        type=Path,
        help='Input PDF file or directory'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Output JSON file or directory'
    )
    parser.add_argument(
        '--model',
        default='gemini-2.5-flash',
        help='Gemini model to use (default: gemini-2.5-flash)'
    )
    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=3,
        help='Maximum concurrent requests (default: 3)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=2.0,
        help='Delay between requests in seconds (default: 2.0)'
    )
    
    args = parser.parse_args()
    
    if args.input.is_file():
        # Single file
        output = args.output or args.input.with_suffix('.json')
        print(f"Parsing: {args.input}")
        data = parse_single(str(args.input), str(output))
        print(f"Output: {output}")
        print(f"Extracted {len(data.get('weed_control_entries', []))} weed control entries")
        print(f"Registered crops: {data.get('registered_crops', [])}")
    else:
        # Directory
        output_dir = args.output or args.input.parent / 'extracted'
        print(f"Processing directory: {args.input}")
        summary = asyncio.run(parse_all_pdfs(
            args.input,
            output_dir,
            model=args.model,
            max_concurrent=args.max_concurrent,
            delay_between=args.delay
        ))
        print(f"\nComplete!")
        print(f"Succeeded: {summary['succeeded']}")
        print(f"Failed: {summary['failed']}")
        print(f"Skipped: {summary['skipped']}")


if __name__ == '__main__':
    main()
