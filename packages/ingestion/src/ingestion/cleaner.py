"""
Document cleaner for parsed herbicide labels.

Removes noise from parsed markdown files to improve GraphRAG quality:
- Page headers/footers (dates, page numbers)
- Duplicate boilerplate sections (repeated safety warnings, product headers)
- HTML artifacts (<br>*, etc.)
- Irrelevant metadata (Product No., Batch No., Date of Manufacture)
- Trademark notices and company addresses
- Empty lines and formatting noise
"""

import re
import argparse
from pathlib import Path
from typing import List, Tuple
import json
from datetime import datetime


# Patterns to remove (compiled for performance)
NOISE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # Page headers with dates (e.g., "5/01/99", "12/03/2024")
    (re.compile(r'^\d{1,2}/\d{1,2}/\d{2,4}\s*$', re.MULTILINE), ''),
    
    # Page numbers (e.g., "Page 1 of 18", "Page 4")
    (re.compile(r'^Page\s+\d+\s*(of\s+\d+)?\s*$', re.MULTILINE | re.IGNORECASE), ''),
    
    # Combined date + page (e.g., "5/01/99\nPage 1 of 18")
    (re.compile(r'\d{1,2}/\d{1,2}/\d{2,4}\s*\n\s*Page\s+\d+\s*(of\s+\d+)?', re.IGNORECASE), ''),
    
    # Filename references (e.g., "Filename: Spinn4.doc")
    (re.compile(r'^Filename:\s*\S+\.(doc|docx|pdf)\s*$', re.MULTILINE | re.IGNORECASE), ''),
    
    # Draft labels (standalone line)
    (re.compile(r'^Draft\s+(pack\s+)?label\s*(leaflet|booklet)?\s*$', re.MULTILINE | re.IGNORECASE), ''),
    
    # HTML artifacts
    (re.compile(r'<br>\s*\*?', re.IGNORECASE), ' '),
    (re.compile(r'</?[a-z]+[^>]*>', re.IGNORECASE), ''),  # Remove any HTML tags
    
    # Product/Batch/Manufacture metadata (not useful for GraphRAG)
    (re.compile(r'^Product\s+No\.?:\s*$', re.MULTILINE | re.IGNORECASE), ''),
    (re.compile(r'^Batch\s+No\.?:\s*$', re.MULTILINE | re.IGNORECASE), ''),
    (re.compile(r'^Date\s+of\s+Manufacture:\s*$', re.MULTILINE | re.IGNORECASE), ''),
    (re.compile(r'^NRA\s+Approval\s+No\.?:\s*\d*/?\d*\s*$', re.MULTILINE | re.IGNORECASE), ''),
    (re.compile(r'^APVMA\s+Approval\s+No\.?:\s*\d*/?\d*\s*$', re.MULTILINE | re.IGNORECASE), ''),
    
    # Trademark notices
    (re.compile(r'^\s*[-*]\s*Registered\s+trademark\s+of\s+[^.\n]+\.?\s*$', re.MULTILINE | re.IGNORECASE), ''),
    (re.compile(r'^\s*[®™]\s*[^\n]*$', re.MULTILINE), ''),
    (re.compile(r'\(c\)\s*Copyright[,.]?\s*[^,\n]+,?\s*\d{4}\s*', re.IGNORECASE), ''),
    (re.compile(r'©\s*Copyright[,.]?\s*[^,\n]+,?\s*\d{4}\s*', re.IGNORECASE), ''),
    (re.compile(r'\(C\)\s*Copyright[,.]?\s*[^,\n]+,?\s*\d{4}\s*'), ''),
    
    # Company addresses (Australian format) - more flexible pattern
    (re.compile(r'^\d+\s+[\w\s]+\s+(Road|Street|Avenue|Drive|Way|Rd|St|Ave),?\s+[\w\s]+\s+(NSW|VIC|QLD|SA|WA|TAS|NT|ACT)\s+\d{4}\s*$', re.MULTILINE | re.IGNORECASE), ''),
    # Address fragments like "95 5 Gibbon Road..."
    (re.compile(r'^\d+\s+\d+\s+\w+\s+(Road|Street|Avenue|Drive|Way|Rd|St|Ave)[^\n]*$', re.MULTILINE | re.IGNORECASE), ''),
    
    # Container sizes standing alone (e.g., "1L", "5L", "20L")
    (re.compile(r'^(\d+)\s*L\s*$', re.MULTILINE), ''),
    
    # Dangerous goods transport statements
    (re.compile(r'THIS PRODUCT IS NOT CONSIDERED TO BE A DANGEROUS GOOD[S]? UNDER THE AUSTRALIAN\s*\n?CODE FOR THE TRANSPORT OF DANGEROUS GOODS BY ROAD AND RAIL\.?', re.IGNORECASE), ''),
    
    # Emergency phone header without number
    (re.compile(r'\*\*FOR SPECIALIST ADVICE IN AN EMERGENCY ONLY\*\*', re.IGNORECASE), ''),
    
    # Toll-free phone lines (keep the number, remove redundant header)
    (re.compile(r'\*\*TOLL FREE - ALL HOURS - AUSTRALIA WIDE\*\*', re.IGNORECASE), ''),
    
    # Company names alone on a line (like "**CYANAMID**")
    (re.compile(r'^\*\*CYANAMID\*\*\s*$', re.MULTILINE), ''),
    (re.compile(r'^\d+\s+CYANAMID AGRICULTURE PTY\.?\s*LIMITED\s*$', re.MULTILINE | re.IGNORECASE), ''),
    (re.compile(r'^\d+\s*$', re.MULTILINE), ''),  # Standalone numbers
    
    # Random numbers that appear alone (likely OCR artifacts or page-break artifacts)
    (re.compile(r'^\s*\d{1,3}\s+\d{1,3}\s*$', re.MULTILINE), ''),
    (re.compile(r'^\s*10\s+20\s*$', re.MULTILINE), ''),  # Common OCR artifact
    (re.compile(r'^\s*95\s+5\s*$', re.MULTILINE), ''),   # From addresses
    
    # Multiple consecutive blank lines -> single blank line
    (re.compile(r'\n{4,}'), '\n\n\n'),
    
    # Lines with only asterisks or dashes
    (re.compile(r'^\s*[\*\-_]{3,}\s*$', re.MULTILINE), ''),
    
    # Col1, Col2, Col3 table artifacts
    (re.compile(r'\|Col\d+\|', re.IGNORECASE), '|'),
    
    # Section attachment placeholders
    (re.compile(r'^This section contains file attachment\.\s*$', re.MULTILINE | re.IGNORECASE), ''),
    
    # ========== NON-RELEVANT SECTIONS FOR GRAPHRAG ==========
    # These sections don't help with herbicide selection decisions
    
    # SAFETY DIRECTIONS section (full block)
    (re.compile(
        r'\*?\*?SAFETY DIRECTIONS:?\*?\*?\s*\n'
        r'((?:(?!\n\*\*[A-Z]).)*)',
        re.IGNORECASE | re.DOTALL
    ), ''),
    
    # FIRST AID section
    (re.compile(
        r'\*?\*?FIRST AID:?\*?\*?\s*\n'
        r'((?:(?!\n\*\*[A-Z]).)*)',
        re.IGNORECASE | re.DOTALL
    ), ''),
    
    # STORAGE AND DISPOSAL section
    (re.compile(
        r'\*?\*?STORAGE AND DISPOSAL:?\*?\*?\s*\n'
        r'((?:(?!\n\*\*[A-Z]).)*)',
        re.IGNORECASE | re.DOTALL
    ), ''),
    
    # MSDS/SDS section
    (re.compile(
        r'\*?\*?M?SDS:?\*?\*?\s*\n'
        r'((?:(?!\n\*\*[A-Z]).)*)',
        re.IGNORECASE | re.DOTALL
    ), ''),
    
    # WARRANTY section
    (re.compile(
        r'\*?\*?WARRANTY:?\*?\*?\s*\n'
        r'((?:(?!\n\*\*[A-Z]).)*)',
        re.IGNORECASE | re.DOTALL
    ), ''),
    
    # PROTECTION OF WILDLIFE, FISH, CRUSTACEA section
    (re.compile(
        r'\*?\*?PROTECTION OF WILDLIFE,?\s*FISH,?\s*CRUSTACEA?\s*(AND\s*(THE\s*)?ENVIRONMENT)?:?\*?\*?\s*\n'
        r'((?:(?!\n\*\*[A-Z]).)*)',
        re.IGNORECASE | re.DOTALL
    ), ''),
    
    # Emergency phone numbers (standalone)
    (re.compile(r'\*?\*?PHONE\s*[-–]\s*1\s*800\s*\d{3}\s*\d{3}\*?\*?', re.IGNORECASE), ''),
    
    # Poisons Information Centre references
    (re.compile(r'If poisoning occurs,?\s*contact a doctor or Poisons Information Centre[^\n]*', re.IGNORECASE), ''),
    (re.compile(r'Phone Australia 13 11 26[^\n]*', re.IGNORECASE), ''),
    (re.compile(r'Telephone 131126 Australia-wide\.?', re.IGNORECASE), ''),
]


# Boilerplate sections to deduplicate (keep only first occurrence)
DEDUPE_PATTERNS = [
    # Safety headings that often repeat
    r'\*\*KEEP OUT OF REACH OF CHILDREN\*\*\s*\n\s*\*\*READ SAFETY DIRECTIONS BEFORE OPENING OR USING\*\*',
    # Product headers that repeat for different pack sizes
    r'#\s*\*\*[A-Z][A-Z\s\*]+\*\*\s*\n+\s*\*\*Herbicide\*\*',
    # GROUP X HERBICIDE headers
    r'#\s*\*\*GROUP\s+[A-Z]\s+HERBICIDE\*\*',
    # Active Constituent declarations
    r'Active Constituent:\s*\d+\s*g/L\s*\*?\*?[A-Z]+\*?\*?',
    # DIRECTIONS FOR USE header
    r'\*\*DIRECTIONS FOR USE:\*\*\s*\n\s*\*\*READ THE ATTACHED (LEAFLET|BOOKLET) BEFORE USING THIS PRODUCT\.\*\*',
]


def normalize_text(text: str) -> str:
    """Normalize text for comparison (lowercase, collapse whitespace)."""
    return re.sub(r'\s+', ' ', text.lower().strip())


def extract_frontmatter(content: str) -> Tuple[str, str]:
    """Extract YAML frontmatter from content."""
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            return f'---{parts[1]}---\n', parts[2]
    return '', content


def deduplicate_sections(content: str) -> str:
    """Remove duplicate boilerplate sections, keeping first occurrence."""
    for pattern_str in DEDUPE_PATTERNS:
        pattern = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
        matches = list(pattern.finditer(content))
        if len(matches) > 1:
            # Keep first, remove rest
            for match in reversed(matches[1:]):
                content = content[:match.start()] + content[match.end():]
    return content


def remove_duplicate_blocks(content: str) -> str:
    """
    Remove large duplicate text blocks (e.g., repeated label pages for different pack sizes).
    Uses paragraph-level comparison to find and remove duplicates.
    """
    # Split into paragraphs (blocks separated by 2+ newlines)
    paragraphs = re.split(r'\n{2,}', content)
    
    seen_normalized = set()
    unique_paragraphs = []
    
    for para in paragraphs:
        # Skip very short paragraphs (likely headers or noise)
        if len(para.strip()) < 50:
            unique_paragraphs.append(para)
            continue
        
        normalized = normalize_text(para)
        
        # Skip if we've seen this paragraph before
        if normalized in seen_normalized:
            continue
        
        seen_normalized.add(normalized)
        unique_paragraphs.append(para)
    
    return '\n\n'.join(unique_paragraphs)


def remove_duplicate_product_headers(content: str) -> str:
    """
    Remove duplicate product name headers that appear for different pack sizes.
    These often have identical Active Constituent and GROUP information.
    """
    # Pattern for product header blocks
    header_pattern = re.compile(
        r'(#\s*\*\*[^*]+\*\*\s*\n\s*\*\*Herbicide\*\*\s*\n\s*'
        r'Active Constituent:[^\n]+\n[^\n]*\n'
        r'#?\s*\*\*GROUP\s+[A-Z]\s+HERBICIDE\*\*)',
        re.IGNORECASE
    )
    
    matches = list(header_pattern.finditer(content))
    if len(matches) > 1:
        # Keep first, remove duplicates that are substantially similar
        first_match_text = matches[0].group(0).lower().strip()
        for match in reversed(matches[1:]):
            if match.group(0).lower().strip() == first_match_text:
                content = content[:match.start()] + content[match.end():]
    
    return content


def clean_content(content: str) -> str:
    """Apply all cleaning patterns to content."""
    # Extract and preserve frontmatter
    frontmatter, body = extract_frontmatter(content)
    
    # Apply noise removal patterns
    for pattern, replacement in NOISE_PATTERNS:
        body = pattern.sub(replacement, body)
    
    # Deduplicate sections
    body = deduplicate_sections(body)
    body = remove_duplicate_product_headers(body)
    body = remove_duplicate_blocks(body)
    
    # Clean up resulting whitespace
    # Remove lines that are only whitespace
    body = re.sub(r'^[ \t]+$', '', body, flags=re.MULTILINE)
    
    # Collapse multiple blank lines
    body = re.sub(r'\n{3,}', '\n\n', body)
    
    # Remove trailing whitespace on lines
    body = re.sub(r'[ \t]+$', '', body, flags=re.MULTILINE)
    
    # Remove leading/trailing whitespace from body
    body = body.strip()
    
    return frontmatter + '\n' + body + '\n'


def calculate_reduction(original: str, cleaned: str) -> Tuple[int, int, float]:
    """Calculate size reduction statistics."""
    orig_size = len(original)
    clean_size = len(cleaned)
    reduction_pct = ((orig_size - clean_size) / orig_size * 100) if orig_size > 0 else 0
    return orig_size, clean_size, reduction_pct


def clean_file(input_path: Path, output_path: Path = None, in_place: bool = False) -> dict:
    """
    Clean a single markdown file.
    
    Args:
        input_path: Path to the input markdown file
        output_path: Path for cleaned output (optional, defaults to same as input with .cleaned suffix)
        in_place: If True, overwrite the input file
    
    Returns:
        Dictionary with cleaning statistics
    """
    content = input_path.read_text(encoding='utf-8')
    cleaned = clean_content(content)
    
    orig_size, clean_size, reduction_pct = calculate_reduction(content, cleaned)
    
    if in_place:
        output_path = input_path
    elif output_path is None:
        output_path = input_path.with_suffix('.cleaned.md')
    
    output_path.write_text(cleaned, encoding='utf-8')
    
    return {
        'file': input_path.name,
        'original_size': orig_size,
        'cleaned_size': clean_size,
        'reduction_percent': round(reduction_pct, 1),
        'output_path': str(output_path)
    }


def clean_directory(
    input_dir: Path,
    output_dir: Path = None,
    in_place: bool = False,
    pattern: str = '*.md'
) -> dict:
    """
    Clean all markdown files in a directory.
    
    Args:
        input_dir: Directory containing markdown files
        output_dir: Directory for cleaned output (optional)
        in_place: If True, overwrite input files
        pattern: Glob pattern for files to process
    
    Returns:
        Dictionary with aggregate statistics
    """
    input_dir = Path(input_dir)
    files = list(input_dir.glob(pattern))
    
    # Exclude already cleaned files and metadata
    files = [f for f in files if not f.name.endswith('.cleaned.md') 
             and f.name != 'parsing_metadata.json']
    
    if output_dir and not in_place:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    total_original = 0
    total_cleaned = 0
    
    for i, file_path in enumerate(files, 1):
        try:
            if in_place:
                out_path = None
            elif output_dir:
                out_path = output_dir / file_path.name
            else:
                out_path = None
            
            stats = clean_file(file_path, out_path, in_place)
            results.append(stats)
            total_original += stats['original_size']
            total_cleaned += stats['cleaned_size']
            
            if i % 50 == 0 or i == len(files):
                print(f"Processed {i}/{len(files)} files...")
                
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")
            results.append({
                'file': file_path.name,
                'error': str(e)
            })
    
    total_reduction = ((total_original - total_cleaned) / total_original * 100) if total_original > 0 else 0
    
    summary = {
        'timestamp': datetime.now().isoformat(),
        'files_processed': len(files),
        'files_succeeded': len([r for r in results if 'error' not in r]),
        'files_failed': len([r for r in results if 'error' in r]),
        'total_original_bytes': total_original,
        'total_cleaned_bytes': total_cleaned,
        'total_reduction_percent': round(total_reduction, 1),
        'in_place': in_place,
        'results': results
    }
    
    return summary


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Clean parsed herbicide label markdown files for GraphRAG'
    )
    parser.add_argument(
        'input',
        type=Path,
        help='Input file or directory'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Output file or directory (optional)'
    )
    parser.add_argument(
        '--in-place',
        action='store_true',
        help='Modify files in place'
    )
    parser.add_argument(
        '--stats-file',
        type=Path,
        help='Write cleaning statistics to JSON file'
    )
    
    args = parser.parse_args()
    
    input_path = args.input.resolve()
    
    if input_path.is_file():
        stats = clean_file(input_path, args.output, args.in_place)
        print(f"Cleaned {stats['file']}: {stats['original_size']} -> {stats['cleaned_size']} bytes "
              f"({stats['reduction_percent']}% reduction)")
        summary = {'files': [stats]}
    else:
        summary = clean_directory(input_path, args.output, args.in_place)
        print(f"\nCleaning complete!")
        print(f"Files processed: {summary['files_processed']}")
        print(f"Succeeded: {summary['files_succeeded']}")
        print(f"Failed: {summary['files_failed']}")
        print(f"Total size reduction: {summary['total_original_bytes']:,} -> {summary['total_cleaned_bytes']:,} bytes")
        print(f"Overall reduction: {summary['total_reduction_percent']}%")
    
    if args.stats_file:
        args.stats_file.write_text(json.dumps(summary, indent=2))
        print(f"\nStatistics written to {args.stats_file}")


if __name__ == '__main__':
    main()
