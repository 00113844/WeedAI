#!/usr/bin/env python3
"""
Merge multiple JSON blocks in docling files into a single valid docling.json.
Preserves all data without removing, suppressing, or changing any information.
"""
import json
import re
from pathlib import Path

# Files flagged as poorly extracted (with multiple blocks)
flagged_files = [
    '31525ELBL.docling.json',
    '31538ELBL.docling.json',
    '66285ELBL.docling.json',
    '66949ELBL.docling.json',
    '67439ELBL.docling.json',
    '68208ELBL.docling.json',
]

docling_dir = Path('WeedAI/data/docling')

def split_json_blocks(text):
    """Split multiple JSON objects from text, handling appended markdown."""
    blocks = []
    current = ''
    depth = 0
    in_string = False
    escape_next = False
    
    for char in text:
        if escape_next:
            current += char
            escape_next = False
            continue
        if char == '\\' and in_string:
            escape_next = True
            current += char
            continue
        if char == '"' and not escape_next:
            in_string = not in_string
        if not in_string:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and current.strip():
                    current += char
                    try:
                        json.loads(current)
                        blocks.append(('json', current))
                        current = ''
                        continue
                    except json.JSONDecodeError:
                        pass
        current += char
    
    # Remaining text is markdown/plain text
    if current.strip() and not current.startswith('{'):
        blocks.append(('markdown', current.strip()))
    
    return blocks

def merge_docling_file(filepath):
    """Merge multiple JSON blocks and markdown into a single docling JSON."""
    print(f"Processing {filepath.name}...")
    
    text = filepath.read_text(encoding='utf-8')
    blocks = split_json_blocks(text)
    
    if len(blocks) <= 1:
        print(f"  → Only 1 block, no merge needed.")
        return False
    
    json_blocks = [b for b in blocks if b[0] == 'json']
    markdown_blocks = [b[1] for b in blocks if b[0] == 'markdown']
    
    print(f"  → Found {len(json_blocks)} JSON blocks and {len(markdown_blocks)} markdown block(s)")
    
    # Parse all JSON blocks
    parsed = []
    for _, json_text in json_blocks:
        try:
            parsed.append(json.loads(json_text))
        except json.JSONDecodeError as e:
            print(f"  ⚠ Error parsing JSON block: {e}")
            return False
    
    # Use first block as base
    merged = parsed[0].copy()
    merged['merged_from'] = 'multiple_blocks_preserved'
    
    # Collect all tables from all blocks
    all_tables = []
    for block in parsed:
        if 'tables' in block and block['tables']:
            all_tables.extend(block['tables'])
    merged['tables'] = all_tables
    
    # Collect all text_items
    all_text = []
    for block in parsed:
        if 'text_items' in block and block['text_items']:
            all_text.extend([t for t in block['text_items'] if isinstance(t, str) and t.strip()])
    
    # Add markdown content to text_items
    if markdown_blocks:
        combined_markdown = '\n\n'.join(markdown_blocks)
        # Split by common section markers
        sections = re.split(r'(?:^|\n)#+\s+', combined_markdown)
        for section in sections:
            if section.strip():
                all_text.append(section.strip())
    
    merged['text_items'] = all_text
    
    # Store original blocks
    merged['raw_blocks'] = []
    for i, block in enumerate(parsed):
        merged['raw_blocks'].append({
            'block_index': i,
            'num_tables': len(block.get('tables', [])),
            'has_text_items': bool(block.get('text_items'))
        })
    if markdown_blocks:
        merged['raw_blocks'].append({
            'block_index': len(parsed),
            'type': 'markdown',
            'content_preview': (markdown_blocks[0][:100] + '...') if markdown_blocks[0] else ''
        })
    
    # Write merged file
    filepath.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"  ✓ Merged: {len(all_tables)} tables, {len(all_text)} text items")
    return True

# Process all flagged files
success_count = 0
for fname in flagged_files:
    filepath = docling_dir / fname
    if filepath.exists():
        if merge_docling_file(filepath):
            success_count += 1
    else:
        print(f"File not found: {fname}")

print(f"\n✓ Merged {success_count}/{len(flagged_files)} files successfully.")
