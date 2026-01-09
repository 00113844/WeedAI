"""
Structure-aware chunker for Docling JSON output.

Transforms Docling-parsed herbicide labels into enriched chunks
with hierarchical context for GraphRAG retrieval.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional
from hashlib import md5


@dataclass
class Chunk:
    """A chunk of text with metadata for RAG retrieval."""
    
    chunk_id: str
    text: str
    chunk_type: str  # "table", "metadata", "directions", "weed_table"
    sequence_order: int
    source_file: str
    product_number: str
    
    # Hierarchical context
    parent_section: Optional[str] = None
    table_id: Optional[str] = None
    
    # Table-specific metadata
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    headers: list[str] = field(default_factory=list)
    
    # Page info (if available)
    page_number: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "chunk_type": self.chunk_type,
            "sequence_order": self.sequence_order,
            "source_file": self.source_file,
            "product_number": self.product_number,
            "parent_section": self.parent_section,
            "table_id": self.table_id,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "headers": self.headers,
            "page_number": self.page_number,
        }
    
    def contextualize(self) -> str:
        """
        Return metadata-enriched text for embedding.
        
        Prepends hierarchical context to improve retrieval relevance.
        """
        parts = []
        
        # Add product context
        if self.product_number:
            parts.append(f"[Product: {self.product_number}]")
        
        # Add section context
        if self.parent_section:
            parts.append(f"[Section: {self.parent_section}]")
        
        # Add chunk type context
        if self.chunk_type == "weed_table":
            parts.append("[Weed Control Table]")
        elif self.chunk_type == "directions":
            parts.append("[Directions for Use]")
        
        parts.append(self.text)
        
        return " ".join(parts)


# Section classification patterns
SECTION_PATTERNS = {
    "product_identity": re.compile(r"label\s*name|product\s*name|apvma", re.I),
    "claims": re.compile(r"statement\s*of\s*claims|claim", re.I),
    "resistance_warning": re.compile(r"resistance\s*warning|group\s*[a-z]\s*herbicide", re.I),
    "directions_for_use": re.compile(r"situation|crop|weeds|rate|critical\s*comments", re.I),
    "weed_table": re.compile(r"weed\s*table|weeds?\s*controlled", re.I),
    "withholding_period": re.compile(r"withholding|whp|harvest", re.I),
    "compatibility": re.compile(r"compatib|tank\s*mix|mixing", re.I),
    "safety": re.compile(r"safety|first\s*aid|poison|hazard", re.I),
    "storage": re.compile(r"storage|disposal|container", re.I),
}


def classify_section(table: dict) -> str:
    """
    Classify a table into a section type based on content.
    
    Args:
        table: Docling table object with rows and markdown
        
    Returns:
        Section type string
    """
    # Combine all text for pattern matching
    text = table.get("markdown", "")
    if not text:
        rows = table.get("rows", [])
        text = " ".join(" ".join(str(cell) for cell in row) for row in rows)
    
    # Check patterns
    for section_name, pattern in SECTION_PATTERNS.items():
        if pattern.search(text):
            return section_name
    
    # Default based on column count
    col_count = table.get("column_count", 0)
    if col_count >= 4:
        return "directions_for_use"
    elif col_count == 2:
        return "metadata"
    
    return "general"


def is_weed_table(table: dict) -> bool:
    """Check if table is a weed control table (list of weeds with rates)."""
    rows = table.get("rows", [])
    if len(rows) < 3:
        return False
    
    # Check for weed-like entries (column 0 often has weed names)
    weed_indicators = ["weed", "grass", "thistle", "dock", "clover", "ryegrass"]
    
    text = " ".join(str(rows[0][0]) if rows[0] else "" for _ in range(1)).lower()
    for row in rows[:5]:
        if row:
            first_col = str(row[0]).lower()
            if any(ind in first_col for ind in weed_indicators):
                return True
            # Check for rate patterns (mL/ha, g/ha, L/ha)
            for cell in row:
                if re.search(r"\d+\s*(mL|g|L)/ha", str(cell), re.I):
                    return True
    
    return False


def chunk_docling_json(json_path: Path, max_chunk_tokens: int = 512) -> Iterator[Chunk]:
    """
    Process Docling JSON into structured chunks.
    
    Uses table structure to create semantically meaningful chunks
    rather than fixed-size splits.
    
    Args:
        json_path: Path to .docling.json file
        max_chunk_tokens: Approx max tokens per chunk (for splitting large tables)
        
    Yields:
        Chunk objects with enriched metadata
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        doc = json.load(f)
    
    # Extract product number from filename
    product_number = json_path.stem.replace("ELBL", "").replace(".docling", "")
    source_file = str(json_path.name)
    
    sequence = 0
    current_section = None
    
    tables = doc.get("tables", [])
    
    for table in tables:
        table_id = table.get("id", f"table-{sequence}")
        markdown = table.get("markdown", "")
        rows = table.get("rows", [])
        
        if not markdown and not rows:
            continue
        
        # Classify section
        section = classify_section(table)
        if section != "general":
            current_section = section
        
        # Determine chunk type
        if is_weed_table(table):
            chunk_type = "weed_table"
        elif section == "directions_for_use":
            chunk_type = "directions"
        elif section == "metadata" or table.get("column_count", 0) <= 2:
            chunk_type = "metadata"
        else:
            chunk_type = "table"
        
        # Extract headers (first row for multi-column tables)
        headers = []
        if rows and table.get("column_count", 0) >= 3:
            headers = [str(cell) for cell in rows[0]] if rows else []
        
        # Create chunk text
        if markdown:
            text = markdown
        else:
            # Convert rows to readable text
            text = "\n".join(" | ".join(str(cell) for cell in row) for row in rows)
        
        # Skip empty or very short chunks
        if len(text.strip()) < 20:
            continue
        
        # Generate unique chunk ID
        chunk_hash = md5(f"{product_number}-{table_id}-{sequence}".encode()).hexdigest()[:8]
        chunk_id = f"{product_number}-{table_id}-{chunk_hash}"
        
        # Handle large tables by splitting rows
        estimated_tokens = len(text.split())
        
        if estimated_tokens > max_chunk_tokens and len(rows) > 3:
            # Split large tables into sub-chunks
            header_row = rows[0] if headers else None
            data_rows = rows[1:] if headers else rows
            
            # Group rows into sub-chunks
            rows_per_chunk = max(1, len(data_rows) // ((estimated_tokens // max_chunk_tokens) + 1))
            
            for i in range(0, len(data_rows), rows_per_chunk):
                sub_rows = data_rows[i:i + rows_per_chunk]
                
                if header_row:
                    sub_text = " | ".join(str(c) for c in header_row) + "\n"
                    sub_text += "\n".join(" | ".join(str(cell) for cell in row) for row in sub_rows)
                else:
                    sub_text = "\n".join(" | ".join(str(cell) for cell in row) for row in sub_rows)
                
                sub_chunk_id = f"{product_number}-{table_id}-part{i//rows_per_chunk}-{chunk_hash}"
                
                yield Chunk(
                    chunk_id=sub_chunk_id,
                    text=sub_text,
                    chunk_type=chunk_type,
                    sequence_order=sequence,
                    source_file=source_file,
                    product_number=product_number,
                    parent_section=current_section,
                    table_id=table_id,
                    row_count=len(sub_rows),
                    column_count=table.get("column_count"),
                    headers=headers,
                    page_number=table.get("bbox", {}).get("page"),
                )
                sequence += 1
        else:
            # Single chunk for table
            yield Chunk(
                chunk_id=chunk_id,
                text=text,
                chunk_type=chunk_type,
                sequence_order=sequence,
                source_file=source_file,
                product_number=product_number,
                parent_section=current_section,
                table_id=table_id,
                row_count=table.get("row_count"),
                column_count=table.get("column_count"),
                headers=headers,
                page_number=table.get("bbox", {}).get("page"),
            )
            sequence += 1


def chunk_directory(docling_dir: Path, max_chunk_tokens: int = 512) -> Iterator[tuple[str, list[Chunk]]]:
    """
    Process all Docling JSON files in a directory.
    
    Args:
        docling_dir: Directory containing .docling.json files
        max_chunk_tokens: Max tokens per chunk
        
    Yields:
        Tuples of (product_number, list of chunks)
    """
    for json_file in sorted(docling_dir.glob("*.docling.json")):
        chunks = list(chunk_docling_json(json_file, max_chunk_tokens))
        if chunks:
            yield chunks[0].product_number, chunks


def main():
    """CLI for testing chunker."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Chunk Docling JSON files")
    parser.add_argument("input", type=Path, help="Docling JSON file or directory")
    parser.add_argument("--max-tokens", type=int, default=512, help="Max tokens per chunk")
    parser.add_argument("--output", type=Path, help="Output JSON file for chunks")
    
    args = parser.parse_args()
    
    if args.input.is_file():
        chunks = list(chunk_docling_json(args.input, args.max_tokens))
        print(f"Generated {len(chunks)} chunks from {args.input.name}")
        
        for chunk in chunks[:5]:
            print(f"\n--- {chunk.chunk_id} ({chunk.chunk_type}) ---")
            print(f"Section: {chunk.parent_section}")
            print(chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump([c.to_dict() for c in chunks], f, indent=2)
            print(f"\nSaved to {args.output}")
    else:
        total_chunks = 0
        for product_number, chunks in chunk_directory(args.input, args.max_tokens):
            print(f"{product_number}: {len(chunks)} chunks")
            total_chunks += len(chunks)
        print(f"\nTotal: {total_chunks} chunks")


if __name__ == "__main__":
    main()
