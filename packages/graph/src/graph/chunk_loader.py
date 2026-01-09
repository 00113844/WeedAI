"""
Chunk loader with embeddings for GraphRAG.

Loads Docling chunks into Neo4j with:
- Vector embeddings (sentence-transformers)
- Sequential NEXT relationships
- Entity linking to Weed/Crop nodes via MENTIONS
"""

import json
import re
from pathlib import Path
from typing import Optional
from datetime import datetime

from neo4j import GraphDatabase
from dotenv import load_dotenv

from graph.schema import get_driver, init_schema, VECTOR_INDEX_CONFIG
from graph.chunker import Chunk, chunk_docling_json, chunk_directory

load_dotenv()


# ============== EMBEDDING MODEL ==============

_embedding_model = None


def get_embedding_model():
    """
    Lazy-load sentence-transformers embedding model.
    
    Uses all-mpnet-base-v2 (768 dimensions) by default.
    """
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer('all-mpnet-base-v2')
            print(f"  ✓ Loaded embedding model: all-mpnet-base-v2 (768d)")
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
    return _embedding_model


def embed_text(text: str) -> list[float]:
    """Generate embedding for text using sentence-transformers."""
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def embed_batch(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
    model = get_embedding_model()
    embeddings = model.encode(texts, batch_size=batch_size, convert_to_numpy=True)
    return [e.tolist() for e in embeddings]


# ============== ENTITY LINKING ==============

# Common weed name patterns for entity linking
WEED_PATTERNS = [
    r"ryegrass",
    r"capeweed",
    r"wild\s*radish",
    r"wild\s*oats?",
    r"brome\s*grass",
    r"barley\s*grass",
    r"clover",
    r"dock",
    r"thistle",
    r"fumitory",
    r"fat\s*hen",
    r"charlock",
    r"sow\s*thistle",
    r"skeleton\s*weed",
    r"turnip\s*weed",
    r"shepherd'?s?\s*purse",
    r"wireweed",
    r"medic",
    r"marshmallow",
    r"sorrel",
    r"deadnettle",
    r"chickweed",
    r"pigweed",
    r"amaranth",
    r"burr",
    r"caltrop",
    r"bindweed",
    r"fleabane",
]

# Crop patterns for entity linking
CROP_PATTERNS = [
    r"wheat",
    r"barley",
    r"canola",
    r"lupins?",
    r"oats?",
    r"triticale",
    r"pasture",
    r"fallow",
    r"chickpea",
    r"lentils?",
    r"field\s*pea",
    r"faba\s*bean",
    r"vetch",
    r"cereal",
    r"grain\s*legume",
]


def extract_entity_mentions(text: str) -> tuple[list[str], list[str]]:
    """
    Extract weed and crop mentions from chunk text.
    
    Returns:
        Tuple of (weed_names, crop_names) found in text
    """
    text_lower = text.lower()
    
    weeds = []
    for pattern in WEED_PATTERNS:
        if re.search(pattern, text_lower):
            # Normalize to common form
            match = re.search(pattern, text_lower)
            if match:
                weeds.append(match.group().replace(" ", "").lower())
    
    crops = []
    for pattern in CROP_PATTERNS:
        if re.search(pattern, text_lower):
            match = re.search(pattern, text_lower)
            if match:
                crops.append(match.group().replace(" ", "").lower())
    
    return list(set(weeds)), list(set(crops))


# ============== CHUNK LOADING ==============

def load_chunks_from_docling(
    docling_path: Path,
    driver=None,
    batch_size: int = 50,
    link_entities: bool = True,
) -> dict:
    """
    Load chunks from a Docling JSON file into Neo4j.
    
    Creates:
    - Document node (linked to Herbicide if exists)
    - Chunk nodes with embeddings
    - NEXT relationships between sequential chunks
    - MENTIONS relationships to Weed/Crop nodes
    
    Args:
        docling_path: Path to .docling.json file
        driver: Neo4j driver
        batch_size: Batch size for embedding generation
        link_entities: Whether to create MENTIONS relationships
        
    Returns:
        Statistics dict
    """
    if driver is None:
        driver = get_driver()
    
    # Generate chunks
    chunks = list(chunk_docling_json(docling_path))
    if not chunks:
        return {"chunks": 0, "next_rels": 0, "mentions_weeds": 0, "mentions_crops": 0, "error": "No chunks generated"}
    
    product_number = chunks[0].product_number
    
    stats = {
        "product_number": product_number,
        "chunks": len(chunks),
        "next_rels": 0,
        "mentions_weeds": 0,
        "mentions_crops": 0,
    }
    
    # Generate embeddings in batches
    print(f"  Generating embeddings for {len(chunks)} chunks...")
    contextualized_texts = [c.contextualize() for c in chunks]
    embeddings = embed_batch(contextualized_texts, batch_size=batch_size)
    
    with driver.session() as session:
        # 1. Create Document node
        session.run(
            """
            MERGE (d:Document {product_number: $product_number})
            SET d.source_file = $source_file,
                d.chunk_count = $chunk_count,
                d.loaded_at = datetime()
            """,
            product_number=product_number,
            source_file=str(docling_path.name),
            chunk_count=len(chunks),
        )
        
        # 2. Link Document to Herbicide if it exists
        session.run(
            """
            MATCH (d:Document {product_number: $product_number})
            MATCH (h:Herbicide {product_number: $product_number})
            MERGE (h)-[:HAS_LABEL]->(d)
            """,
            product_number=product_number,
        )
        
        # 3. Create Chunk nodes with embeddings
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            session.run(
                """
                MERGE (c:Chunk {chunk_id: $chunk_id})
                SET c.text = $text,
                    c.chunk_type = $chunk_type,
                    c.sequence_order = $sequence_order,
                    c.parent_section = $parent_section,
                    c.table_id = $table_id,
                    c.row_count = $row_count,
                    c.column_count = $column_count,
                    c.product_number = $product_number,
                    c.embedding = $embedding
                WITH c
                MATCH (d:Document {product_number: $product_number})
                MERGE (d)-[:CONTAINS_CHUNK]->(c)
                """,
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                chunk_type=chunk.chunk_type,
                sequence_order=chunk.sequence_order,
                parent_section=chunk.parent_section,
                table_id=chunk.table_id,
                row_count=chunk.row_count,
                column_count=chunk.column_count,
                product_number=product_number,
                embedding=embedding,
            )
            
            # 4. Create NEXT relationship to previous chunk
            if i > 0:
                prev_chunk_id = chunks[i - 1].chunk_id
                session.run(
                    """
                    MATCH (prev:Chunk {chunk_id: $prev_id})
                    MATCH (curr:Chunk {chunk_id: $curr_id})
                    MERGE (prev)-[:NEXT]->(curr)
                    """,
                    prev_id=prev_chunk_id,
                    curr_id=chunk.chunk_id,
                )
                stats["next_rels"] += 1
            
            # 5. Create MENTIONS relationships (entity linking)
            if link_entities:
                weeds, crops = extract_entity_mentions(chunk.text)
                
                for weed in weeds:
                    result = session.run(
                        """
                        MATCH (c:Chunk {chunk_id: $chunk_id})
                        MATCH (w:Weed)
                        WHERE toLower(w.common_name) CONTAINS $weed_pattern
                           OR toLower(w.display_name) CONTAINS $weed_pattern
                        MERGE (c)-[:MENTIONS]->(w)
                        RETURN count(*) as linked
                        """,
                        chunk_id=chunk.chunk_id,
                        weed_pattern=weed,
                    )
                    linked = result.single()["linked"]
                    stats["mentions_weeds"] += linked
                
                for crop in crops:
                    result = session.run(
                        """
                        MATCH (c:Chunk {chunk_id: $chunk_id})
                        MATCH (cr:Crop)
                        WHERE toLower(cr.name) CONTAINS $crop_pattern
                           OR toLower(cr.display_name) CONTAINS $crop_pattern
                        MERGE (c)-[:MENTIONS]->(cr)
                        RETURN count(*) as linked
                        """,
                        chunk_id=chunk.chunk_id,
                        crop_pattern=crop,
                    )
                    linked = result.single()["linked"]
                    stats["mentions_crops"] += linked
    
    return stats


def load_chunks_directory(
    docling_dir: Path,
    driver=None,
    batch_size: int = 50,
    link_entities: bool = True,
    limit: Optional[int] = None,
) -> dict:
    """
    Load all Docling JSON files from a directory.
    
    Args:
        docling_dir: Directory containing .docling.json files
        driver: Neo4j driver
        batch_size: Batch size for embedding
        link_entities: Whether to create MENTIONS relationships
        limit: Max files to process (for testing)
        
    Returns:
        Aggregated statistics
    """
    if driver is None:
        driver = get_driver()
    
    files = sorted(docling_dir.glob("*.docling.json"))
    if limit:
        files = files[:limit]
    
    total_stats = {
        "files_processed": 0,
        "total_chunks": 0,
        "total_next_rels": 0,
        "total_mentions": 0,
        "errors": [],
    }
    
    print(f"Loading {len(files)} Docling files...")
    
    for i, json_file in enumerate(files):
        print(f"\n[{i+1}/{len(files)}] Processing {json_file.name}...")
        try:
            stats = load_chunks_from_docling(
                json_file,
                driver=driver,
                batch_size=batch_size,
                link_entities=link_entities,
            )
            total_stats["files_processed"] += 1
            total_stats["total_chunks"] += stats["chunks"]
            total_stats["total_next_rels"] += stats["next_rels"]
            total_stats["total_mentions"] += stats["mentions_weeds"] + stats["mentions_crops"]
            print(f"  ✓ {stats['chunks']} chunks, {stats['mentions_weeds']} weed mentions")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            total_stats["errors"].append({"file": json_file.name, "error": str(e)})
    
    return total_stats


# ============== CLI ==============

def main():
    """CLI for loading chunks into Neo4j."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Load Docling chunks into Neo4j with embeddings")
    parser.add_argument("input", type=Path, help="Docling JSON file or directory")
    parser.add_argument("--batch-size", type=int, default=50, help="Embedding batch size")
    parser.add_argument("--no-entity-linking", action="store_true", help="Skip MENTIONS relationships")
    parser.add_argument("--limit", type=int, help="Max files to process")
    parser.add_argument("--init-schema", action="store_true", help="Initialize schema first")
    
    args = parser.parse_args()
    
    driver = get_driver()
    
    try:
        if args.init_schema:
            print("Initializing schema...")
            init_schema(driver)
        
        if args.input.is_file():
            stats = load_chunks_from_docling(
                args.input,
                driver=driver,
                batch_size=args.batch_size,
                link_entities=not args.no_entity_linking,
            )
            print(f"\n✓ Loaded {stats['chunks']} chunks for {stats['product_number']}")
        else:
            stats = load_chunks_directory(
                args.input,
                driver=driver,
                batch_size=args.batch_size,
                link_entities=not args.no_entity_linking,
                limit=args.limit,
            )
            print(f"\n{'='*40}")
            print(f"✓ Processed {stats['files_processed']} files")
            print(f"  Total chunks: {stats['total_chunks']}")
            print(f"  NEXT relationships: {stats['total_next_rels']}")
            print(f"  MENTIONS relationships: {stats['total_mentions']}")
            if stats["errors"]:
                print(f"  Errors: {len(stats['errors'])}")
    
    finally:
        driver.close()


if __name__ == "__main__":
    main()
