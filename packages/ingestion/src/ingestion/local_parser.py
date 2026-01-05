"""
Local PDF Parser for Herbicide Labels using PyMuPDF.

This module parses APVMA herbicide label PDFs into structured markdown locally,
without requiring cloud API credits. Optimized for downstream knowledge graph extraction.
"""

import os
import json
import re
from pathlib import Path
from tqdm import tqdm
import pymupdf

# Configuration
DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / 'data'
LABELS_DIR = DATA_DIR / 'labels'
PARSED_DIR = DATA_DIR / 'parsed'
METADATA_FILE = PARSED_DIR / 'parsing_metadata.json'

# Ensure output directory exists
PARSED_DIR.mkdir(parents=True, exist_ok=True)


def extract_tables_from_page(page: pymupdf.Page) -> list[dict]:
    """
    Extract tables from a PDF page using PyMuPDF's table detection.
    
    Returns list of tables with headers and rows.
    """
    tables = []
    try:
        tab_finder = page.find_tables()
        for table in tab_finder:
            extracted = table.extract()
            if extracted and len(extracted) > 1:
                tables.append({
                    'headers': extracted[0],
                    'rows': extracted[1:]
                })
    except Exception:
        pass  # Table extraction not always available
    return tables


def table_to_markdown(table: dict) -> str:
    """Convert extracted table dict to markdown format."""
    if not table.get('headers') or not table.get('rows'):
        return ""
    
    headers = table['headers']
    rows = table['rows']
    
    # Clean headers
    headers = [str(h).strip() if h else "" for h in headers]
    
    # Build markdown table
    md = "| " + " | ".join(headers) + " |\n"
    md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
    
    for row in rows:
        cleaned_row = [str(cell).strip().replace('\n', ' ') if cell else "" for cell in row]
        md += "| " + " | ".join(cleaned_row) + " |\n"
    
    return md


def clean_text(text: str) -> str:
    """Clean extracted text for better readability."""
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Fix common PDF extraction artifacts
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)  # Fix hyphenation
    return text.strip()


def extract_metadata_from_first_page(text: str) -> dict:
    """Extract product metadata from the first page text."""
    metadata = {}
    
    # Product Name - look for the actual product name line (usually first line or after specific pattern)
    # Try to find the actual product name from the header
    lines = text.split('\n')
    for i, line in enumerate(lines[:10]):  # Check first 10 lines
        line = line.strip()
        if line and not any(x in line.lower() for x in ['product name:', 'apvma', 'label name:']):
            if len(line) > 5 and line.isupper():
                metadata['product_name'] = line
                break
    
    # Also check Label Name field
    label_match = re.search(r'Label Name:\s*\n?\s*(.+?)(?:\n|Signal)', text)
    if label_match:
        metadata['product_name'] = label_match.group(1).strip()
    
    # APVMA Number
    apvma_match = re.search(r'(\d{4,6})\s*/\s*\d+', text)
    if apvma_match:
        metadata['apvma_number'] = apvma_match.group(1).strip()
    
    # Active Constituent
    active_match = re.search(r'Active Constituent[s]?:\s*(.+?)(?:\nMode of Action|$)', text, re.IGNORECASE | re.DOTALL)
    if active_match:
        active = active_match.group(1).strip().split('\n')[0]
        metadata['active_constituent'] = active
    
    # Mode of Action Group
    moa_match = re.search(r'GROUP\s+([A-Z0-9]+)\s+HERBICIDE', text)
    if moa_match:
        metadata['mode_of_action_group'] = moa_match.group(1)
    
    # Signal Heading (POISON, CAUTION, etc.)
    signal_match = re.search(r'(POISON|CAUTION|WARNING|DANGEROUS POISON)', text)
    if signal_match:
        metadata['signal_heading'] = signal_match.group(1)
    
    return metadata


def parse_pdf_local(pdf_path: Path, output_path: Path, force: bool = False) -> dict:
    """
    Parse a single PDF locally using PyMuPDF.
    
    Args:
        pdf_path: Path to the PDF file
        output_path: Path for the markdown output
        force: If True, re-parse even if output exists
        
    Returns:
        dict with 'success', 'skipped', 'error', 'pages' keys
    """
    result = {'success': False, 'skipped': False, 'error': None, 'pages': 0, 'metadata': {}}
    
    try:
        # Check if already parsed
        if output_path.exists() and not force:
            result['skipped'] = True
            result['success'] = True
            return result
        
        # Open PDF
        doc = pymupdf.open(str(pdf_path))
        result['pages'] = len(doc)
        
        # Extract text and tables from all pages
        full_text_parts = []
        all_tables = []
        
        for page_num, page in enumerate(doc):
            page_text = page.get_text()
            
            # Extract tables from this page
            tables = extract_tables_from_page(page)
            if tables:
                all_tables.extend(tables)
            
            # Add page marker and text
            if page_num > 0:
                full_text_parts.append(f"\n\n---\n## Page {page_num + 1}\n\n")
            full_text_parts.append(page_text)
        
        doc.close()
        
        # Combine all text
        full_text = clean_text("".join(full_text_parts))
        
        # Extract metadata from first page
        metadata = extract_metadata_from_first_page(full_text)
        result['metadata'] = metadata
        
        # Build YAML frontmatter
        product_no = pdf_path.stem.replace('ELBL', '')
        frontmatter = f"""---
product_number: "{product_no}"
source_file: "{pdf_path.name}"
pages: {result['pages']}
"""
        for key, value in metadata.items():
            # Escape quotes in YAML values
            safe_value = str(value).replace('"', '\\"')
            frontmatter += f'{key}: "{safe_value}"\n'
        frontmatter += "---\n\n"
        
        # Add tables section if any were found
        tables_section = ""
        if all_tables:
            tables_section = "\n\n## Extracted Tables\n\n"
            for i, table in enumerate(all_tables, 1):
                tables_section += f"### Table {i}\n\n"
                tables_section += table_to_markdown(table)
                tables_section += "\n"
        
        # Write output
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(frontmatter)
            f.write(full_text)
            f.write(tables_section)
        
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


def parse_all(force: bool = False):
    """
    Parse all PDFs in the labels directory.
    
    Args:
        force: If True, re-parse all files even if output exists
    """
    print("="*60)
    print("LOCAL PDF PARSER (PyMuPDF)")
    print("="*60)
    
    pdf_files = sorted(LABELS_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files to parse.\n")
    
    metadata = load_metadata()
    
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for pdf_path in tqdm(pdf_files, desc="Parsing PDFs"):
        output_path = PARSED_DIR / f"{pdf_path.stem}.md"
        result = parse_pdf_local(pdf_path, output_path, force=force)
        
        if result['skipped']:
            skip_count += 1
        elif result['success']:
            success_count += 1
            metadata['parsed'][pdf_path.stem] = {
                'pages': result['pages'],
                'output': f"{pdf_path.stem}.md",
                'metadata': result['metadata']
            }
        else:
            fail_count += 1
            if pdf_path.stem not in metadata['failed']:
                metadata['failed'].append(pdf_path.stem)
            print(f"\n  ✗ {pdf_path.name}: {result['error']}")
    
    save_metadata(metadata)
    
    print("\n" + "="*60)
    print("PARSING COMPLETE")
    print("="*60)
    print(f"Successfully parsed: {success_count}")
    print(f"Skipped (existing):  {skip_count}")
    print(f"Failed:              {fail_count}")
    print(f"\nOutput directory: {PARSED_DIR}")


def parse_single(pdf_name: str, force: bool = False) -> str:
    """
    Parse a single PDF by name.
    
    Args:
        pdf_name: Filename without extension (e.g., "31209ELBL")
        force: If True, re-parse even if output exists
        
    Returns:
        Path to the output markdown file
    """
    # Handle with or without extension
    if not pdf_name.endswith('.pdf'):
        pdf_name_full = f"{pdf_name}.pdf"
    else:
        pdf_name_full = pdf_name
        pdf_name = pdf_name.replace('.pdf', '')
    
    pdf_path = LABELS_DIR / pdf_name_full
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    output_path = PARSED_DIR / f"{pdf_name}.md"
    
    print(f"Parsing {pdf_path.name}...")
    result = parse_pdf_local(pdf_path, output_path, force=force)
    
    if result['success']:
        if result['skipped']:
            print(f"⊘ Skipped (already exists): {output_path}")
        else:
            print(f"✓ Saved to {output_path}")
            print(f"  Pages: {result['pages']}")
            if result['metadata']:
                print(f"  Product: {result['metadata'].get('product_name', 'Unknown')}")
                print(f"  Active: {result['metadata'].get('active_constituent', 'Unknown')}")
        return str(output_path)
    else:
        print(f"✗ Failed: {result['error']}")
        return ""


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Parse specific file
        pdf_name = sys.argv[1]
        force = "--force" in sys.argv
        parse_single(pdf_name, force=force)
    else:
        # Parse all files
        force = "--force" in sys.argv
        parse_all(force=force)
