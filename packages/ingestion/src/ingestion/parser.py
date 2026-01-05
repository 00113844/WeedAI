"""
PDF Parser for Herbicide Labels using PyMuPDF4LLM.

This module parses APVMA herbicide label PDFs into structured markdown,
optimized for downstream knowledge graph extraction. Uses local processing
(no cloud API required).
"""

import json
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import pymupdf4llm
import pymupdf

# Configuration
DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / 'data'
LABELS_DIR = DATA_DIR / 'labels'
PARSED_DIR = DATA_DIR / 'parsed'
METADATA_FILE = PARSED_DIR / 'parsing_metadata.json'

# Ensure output directory exists
PARSED_DIR.mkdir(parents=True, exist_ok=True)


def extract_product_metadata(text: str, filename: str) -> dict:
    """
    Extract key metadata from the parsed text.
    
    Returns dict with product_name, apvma_number, active_constituent, mode_of_action
    """
    metadata = {
        'product_number': filename.replace('ELBL', '').replace('.pdf', ''),
        'source_file': filename,
    }
    
    # Product name - usually first line or after "Product Name:"
    name_match = re.search(r'Product Name:\s*\n?\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
    if name_match:
        metadata['product_name'] = name_match.group(1).strip()
    
    # APVMA Approval Number
    apvma_match = re.search(r'APVMA Approval No:\s*\n?\s*(\d+(?:\s*/\s*\d+)?)', text, re.IGNORECASE)
    if apvma_match:
        metadata['apvma_number'] = apvma_match.group(1).strip()
    
    # Active Constituent
    active_match = re.search(
        r'Active Constituent[s]?:\s*\n?\s*(.+?)(?:\n\n|\nMode|\nStatement|\nNet)',
        text, 
        re.IGNORECASE | re.DOTALL
    )
    if active_match:
        metadata['active_constituent'] = active_match.group(1).strip().replace('\n', ' ')
    
    # Mode of Action Group
    group_match = re.search(r'GROUP\s+([A-Z0-9]+)\s+HERBICIDE', text, re.IGNORECASE)
    if group_match:
        metadata['mode_of_action_group'] = group_match.group(1)
    
    return metadata


def parse_pdf(pdf_path: Path, output_path: Path, force: bool = False) -> dict:
    """
    Parse a single PDF using PyMuPDF4LLM and save as markdown.
    
    Args:
        pdf_path: Path to the PDF file
        output_path: Path for the output markdown file
        force: If True, re-parse even if output exists
    
    Returns:
        dict with 'success', 'skipped', 'error', 'pages', 'metadata' keys
    """
    result = {'success': False, 'skipped': False, 'error': None, 'pages': 0, 'metadata': {}}
    
    try:
        # Check if already parsed
        if output_path.exists() and not force:
            result['skipped'] = True
            result['success'] = True
            return result
        
        # Get page count
        doc = pymupdf.open(str(pdf_path))
        result['pages'] = len(doc)
        doc.close()
        
        # Extract markdown with table support
        md_text = pymupdf4llm.to_markdown(
            str(pdf_path),
            page_chunks=False,
            write_images=False,
        )
        
        # Extract metadata
        metadata = extract_product_metadata(md_text, pdf_path.name)
        metadata['pages'] = result['pages']
        result['metadata'] = metadata
        
        # Create YAML frontmatter
        frontmatter_lines = ['---']
        for key, value in metadata.items():
            # Escape quotes in values
            if isinstance(value, str) and ('"' in value or ':' in value or '\n' in value):
                value = f'"{value}"'
            frontmatter_lines.append(f'{key}: {value}')
        frontmatter_lines.append('---\n\n')
        frontmatter = '\n'.join(frontmatter_lines)
        
        # Save to markdown file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(frontmatter + md_text)
        
        result['success'] = True
        return result
        
    except Exception as e:
        result['error'] = str(e)
        return result


def load_metadata() -> dict:
    """Load existing parsing metadata."""
    if METADATA_FILE.exists():
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    return {'parsed': {}, 'failed': []}


def save_metadata(metadata: dict):
    """Save parsing metadata for tracking."""
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)


def main(force: bool = False, max_workers: int = 1):
    """
    Parse all PDFs in the labels directory.
    
    Args:
        force: If True, re-parse all files (ignore existing)
        max_workers: Number of parallel workers (use 1 for PyMuPDF stability)
    """
    print("=" * 60)
    print("HERBICIDE LABEL PARSER (PyMuPDF4LLM)")
    print("=" * 60)
    
    # Get list of PDF files
    pdf_files = sorted(LABELS_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files to parse.")
    print(f"Output directory: {PARSED_DIR}")
    print()
    
    # Load existing metadata
    metadata = load_metadata()
    
    # Process files
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    # Sequential processing (PyMuPDF has threading issues)
    for pdf_path in tqdm(pdf_files, desc="Parsing"):
        output_path = PARSED_DIR / f"{pdf_path.stem}.md"
        try:
            result = parse_pdf(pdf_path, output_path, force)
            
            if result['skipped']:
                skip_count += 1
            elif result['success']:
                success_count += 1
                metadata['parsed'][pdf_path.stem] = {
                    'pages': result['pages'],
                    'output': f"{pdf_path.stem}.md",
                    **result.get('metadata', {})
                }
                # Remove from failed if previously failed
                if pdf_path.stem in metadata['failed']:
                    metadata['failed'].remove(pdf_path.stem)
            else:
                fail_count += 1
                if pdf_path.stem not in metadata['failed']:
                    metadata['failed'].append(pdf_path.stem)
                tqdm.write(f"✗ Failed {pdf_path.name}: {result['error']}")
                
        except Exception as e:
            fail_count += 1
            tqdm.write(f"✗ Exception for {pdf_path.name}: {e}")
    
    # Save metadata
    save_metadata(metadata)
    
    # Final summary
    print("\n" + "=" * 60)
    print("PARSING COMPLETE")
    print("=" * 60)
    print(f"Successfully parsed: {success_count}")
    print(f"Skipped (existing):  {skip_count}")
    print(f"Failed:              {fail_count}")
    print(f"\nOutput directory: {PARSED_DIR}")
    print(f"Metadata saved to: {METADATA_FILE}")


def parse_single(pdf_name: str, force: bool = False) -> dict:
    """
    Parse a single PDF by name (utility function for testing).
    
    Args:
        pdf_name: PDF filename (with or without extension)
        force: If True, re-parse even if output exists
    
    Returns:
        Parsing result dict
    
    Usage: 
        from ingestion.parser import parse_single
        result = parse_single("31209ELBL")
    """
    # Normalize filename
    if not pdf_name.endswith('.pdf'):
        pdf_name = f"{pdf_name}.pdf"
    
    pdf_path = LABELS_DIR / pdf_name
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return {'success': False, 'error': 'File not found'}
    
    output_path = PARSED_DIR / f"{pdf_path.stem}.md"
    print(f"Parsing {pdf_path.name}...")
    
    result = parse_pdf(pdf_path, output_path, force=force)
    
    if result['success']:
        if result['skipped']:
            print(f"⊘ Skipped (already exists): {output_path}")
        else:
            print(f"✓ Saved to {output_path}")
            print(f"  Pages: {result['pages']}")
            if result.get('metadata', {}).get('product_name'):
                print(f"  Product: {result['metadata']['product_name']}")
            if result.get('metadata', {}).get('active_constituent'):
                print(f"  Active: {result['metadata']['active_constituent'][:60]}...")
    else:
        print(f"✗ Failed: {result['error']}")
    
    return result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Parse herbicide label PDFs to markdown")
    parser.add_argument('--force', '-f', action='store_true', help='Re-parse all files')
    parser.add_argument('--single', '-s', type=str, help='Parse a single PDF by name')
    parser.add_argument('--workers', '-w', type=int, default=4, help='Number of parallel workers')
    
    args = parser.parse_args()
    
    if args.single:
        parse_single(args.single, force=args.force)
    else:
        main(force=args.force, max_workers=args.workers)
