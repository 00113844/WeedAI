"""
Common Cypher queries for the herbicide knowledge graph.

These queries power the GraphRAG retrieval system.
"""

from typing import Optional
from graph.schema import get_driver

# Lazy import for embedding model (only when needed)
_embed_model = None

def _get_embed_model():
    """Get or initialize the embedding model."""
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer("all-mpnet-base-v2")
    return _embed_model

def embed_query(text: str) -> list[float]:
    """Generate embedding for a query text."""
    model = _get_embed_model()
    return model.encode(text, convert_to_numpy=True).tolist()


# ============== WEED CONTROL QUERIES ==============

def find_herbicides_for_weed(
    weed_name: str,
    crop: Optional[str] = None,
    state: Optional[str] = None,
    moa_group: Optional[str] = None,
    driver=None
) -> list[dict]:
    """
    Find herbicides that control a specific weed.
    
    Args:
        weed_name: Common name of the weed (partial match supported)
        crop: Optional crop to filter by
        state: Optional Australian state code (NSW, VIC, etc.)
        moa_group: Optional mode of action group to filter/exclude
        driver: Neo4j driver
    
    Returns:
        List of herbicide options with application details
    """
    if driver is None:
        driver = get_driver()
    
    query = """
    MATCH (h:Herbicide)-[r:CONTROLS]->(w:Weed)
    WHERE toLower(w.common_name) CONTAINS toLower($weed_name)
       OR toLower(w.display_name) CONTAINS toLower($weed_name)
    """
    
    params = {"weed_name": weed_name}
    
    if crop:
        query += " AND toLower(r.crop) CONTAINS toLower($crop)"
        params["crop"] = crop
    
    if state:
        query += " AND $state IN r.states"
        params["state"] = state.upper()
    
    if moa_group:
        query += """
        MATCH (h)-[:HAS_MODE_OF_ACTION]->(m:ModeOfAction)
        WHERE m.group <> $moa_group
        """
        params["moa_group"] = moa_group.upper()
    
    query += """
    OPTIONAL MATCH (h)-[:HAS_MODE_OF_ACTION]->(m:ModeOfAction)
    RETURN h.product_name as herbicide,
           h.product_number as product_number,
           h.active_constituent as active,
           m.group as moa_group,
           w.common_name as weed,
           w.scientific_name as weed_scientific,
           r.crop as crop,
           r.rate_per_ha as rate,
           r.application_timing as timing,
           r.control_level as control_level,
           r.states as states,
           r.critical_comments as comments
    ORDER BY h.product_name, r.crop
    """
    
    with driver.session() as session:
        result = session.run(query, **params)
        return [dict(record) for record in result]


def find_herbicides_for_crop(
    crop_name: str,
    state: Optional[str] = None,
    driver=None
) -> list[dict]:
    """
    Find all herbicides registered for a specific crop.
    
    Args:
        crop_name: Name of the crop (partial match)
        state: Optional Australian state filter
        driver: Neo4j driver
    
    Returns:
        List of registered herbicides with weeds they control
    """
    if driver is None:
        driver = get_driver()
    
    query = """
    MATCH (h:Herbicide)-[:REGISTERED_FOR]->(c:Crop)
    WHERE toLower(c.name) CONTAINS toLower($crop_name)
       OR toLower(c.display_name) CONTAINS toLower($crop_name)
    OPTIONAL MATCH (h)-[r:CONTROLS]->(w:Weed)
    WHERE toLower(r.crop) CONTAINS toLower($crop_name)
    """
    
    params = {"crop_name": crop_name}
    
    if state:
        query += " AND $state IN r.states"
        params["state"] = state.upper()
    
    query += """
    OPTIONAL MATCH (h)-[:HAS_MODE_OF_ACTION]->(m:ModeOfAction)
    RETURN h.product_name as herbicide,
           h.product_number as product_number,
           h.active_constituent as active,
           m.group as moa_group,
           c.name as crop,
           collect(DISTINCT w.common_name) as weeds_controlled
    ORDER BY h.product_name
    """
    
    with driver.session() as session:
        result = session.run(query, **params)
        return [dict(record) for record in result]


def get_moa_rotation_options(
    current_moa: str,
    crop: str,
    weed: str,
    driver=None
) -> list[dict]:
    """
    Find herbicides with different MOA groups for resistance management.
    
    Essential for recommending herbicide rotations to prevent resistance.
    
    Args:
        current_moa: Current mode of action group being used
        crop: Target crop
        weed: Target weed
        driver: Neo4j driver
    
    Returns:
        Alternative herbicides with different MOA groups
    """
    if driver is None:
        driver = get_driver()
    
    query = """
    MATCH (h:Herbicide)-[r:CONTROLS]->(w:Weed)
    MATCH (h)-[:HAS_MODE_OF_ACTION]->(m:ModeOfAction)
    WHERE (toLower(w.common_name) CONTAINS toLower($weed)
           OR toLower(w.display_name) CONTAINS toLower($weed))
      AND toLower(r.crop) CONTAINS toLower($crop)
      AND m.group <> $current_moa
    RETURN DISTINCT m.group as moa_group,
           m.description as moa_description,
           collect(DISTINCT {
               herbicide: h.product_name,
               product_number: h.product_number,
               active: h.active_constituent,
               rate: r.rate_per_ha,
               timing: r.application_timing,
               control_level: r.control_level
           }) as options
    ORDER BY m.group
    """
    
    with driver.session() as session:
        result = session.run(
            query,
            weed=weed,
            crop=crop,
            current_moa=current_moa.upper()
        )
        return [dict(record) for record in result]


def get_herbicide_details(product_number: str, driver=None) -> dict:
    """
    Get full details for a specific herbicide product.
    
    Args:
        product_number: APVMA product number
        driver: Neo4j driver
    
    Returns:
        Complete herbicide information
    """
    if driver is None:
        driver = get_driver()
    
    query = """
    MATCH (h:Herbicide {product_number: $product_number})
    OPTIONAL MATCH (h)-[:HAS_MODE_OF_ACTION]->(m:ModeOfAction)
    OPTIONAL MATCH (h)-[:CONTAINS]->(a:ActiveConstituent)
    OPTIONAL MATCH (h)-[:REGISTERED_FOR]->(c:Crop)
    OPTIONAL MATCH (h)-[r:CONTROLS]->(w:Weed)
    OPTIONAL MATCH (h)-[:REGISTERED_IN]->(s:State)
    RETURN h.product_name as product_name,
           h.product_number as product_number,
           h.active_constituent as active_constituent,
           h.chemical_group as chemical_group,
           h.withholding_period as withholding_period,
           h.application_methods as application_methods,
           m.group as moa_group,
           m.description as moa_description,
           collect(DISTINCT c.name) as registered_crops,
           collect(DISTINCT {
               weed: w.common_name,
               scientific: w.scientific_name,
               crop: r.crop,
               rate: r.rate_per_ha,
               timing: r.application_timing,
               level: r.control_level,
               states: r.states,
               comments: r.critical_comments
           }) as weed_controls,
           collect(DISTINCT s.code) as registered_states
    """
    
    with driver.session() as session:
        result = session.run(query, product_number=product_number)
        record = result.single()
        return dict(record) if record else None


def search_weeds(search_term: str, driver=None) -> list[dict]:
    """
    Search for weeds by common or scientific name.
    
    Args:
        search_term: Partial name to search
        driver: Neo4j driver
    
    Returns:
        Matching weed entries
    """
    if driver is None:
        driver = get_driver()
    
    query = """
    MATCH (w:Weed)
    WHERE toLower(w.common_name) CONTAINS toLower($term)
       OR toLower(w.display_name) CONTAINS toLower($term)
       OR toLower(w.scientific_name) CONTAINS toLower($term)
    OPTIONAL MATCH (h:Herbicide)-[r:CONTROLS]->(w)
    RETURN w.common_name as common_name,
           w.display_name as display_name,
           w.scientific_name as scientific_name,
           count(DISTINCT h) as herbicide_count
    ORDER BY w.common_name
    LIMIT 20
    """
    
    with driver.session() as session:
        result = session.run(query, term=search_term)
        return [dict(record) for record in result]


def search_crops(search_term: str, driver=None) -> list[dict]:
    """
    Search for crops by name.
    
    Args:
        search_term: Partial name to search
        driver: Neo4j driver
    
    Returns:
        Matching crop entries with herbicide counts
    """
    if driver is None:
        driver = get_driver()
    
    query = """
    MATCH (c:Crop)
    WHERE toLower(c.name) CONTAINS toLower($term)
       OR toLower(c.display_name) CONTAINS toLower($term)
    OPTIONAL MATCH (h:Herbicide)-[:REGISTERED_FOR]->(c)
    RETURN c.name as name,
           c.display_name as display_name,
           count(DISTINCT h) as herbicide_count
    ORDER BY c.name
    LIMIT 20
    """
    
    with driver.session() as session:
        result = session.run(query, term=search_term)
        return [dict(record) for record in result]


# ============== GRAPH STATISTICS ==============

def get_graph_summary(driver=None) -> dict:
    """
    Get a summary of the knowledge graph contents.
    """
    if driver is None:
        driver = get_driver()
    
    with driver.session() as session:
        # Count nodes
        result = session.run("""
            MATCH (h:Herbicide) WITH count(h) as herbicides
            MATCH (c:Crop) WITH herbicides, count(c) as crops
            MATCH (w:Weed) WITH herbicides, crops, count(w) as weeds
            MATCH ()-[r:CONTROLS]->() WITH herbicides, crops, weeds, count(r) as controls
            RETURN herbicides, crops, weeds, controls
        """)
        record = result.single()
        
        # Top weeds by herbicide coverage
        top_weeds = session.run("""
            MATCH (h:Herbicide)-[:CONTROLS]->(w:Weed)
            RETURN w.common_name as weed, count(DISTINCT h) as herbicide_count
            ORDER BY herbicide_count DESC
            LIMIT 10
        """)
        
        # Top crops by herbicide coverage  
        top_crops = session.run("""
            MATCH (h:Herbicide)-[:REGISTERED_FOR]->(c:Crop)
            RETURN c.name as crop, count(DISTINCT h) as herbicide_count
            ORDER BY herbicide_count DESC
            LIMIT 10
        """)
        
        return {
            'total_herbicides': record['herbicides'],
            'total_crops': record['crops'],
            'total_weeds': record['weeds'],
            'total_controls': record['controls'],
            'top_weeds': [dict(r) for r in top_weeds],
            'top_crops': [dict(r) for r in top_crops],
        }


# ============== RAG QUERIES (HYBRID RETRIEVAL) ==============

def vector_search_chunks(
    query_embedding: list[float],
    k: int = 10,
    chunk_type: Optional[str] = None,
    product_number: Optional[str] = None,
    driver=None
) -> list[dict]:
    """
    Semantic search for chunks using vector similarity.
    
    Uses Neo4j's vector index for approximate nearest neighbor search.
    
    Args:
        query_embedding: Query vector (768d for all-mpnet-base-v2)
        k: Number of results to return
        chunk_type: Optional filter by chunk type (weed_table, directions, etc.)
        product_number: Optional filter by specific product
        driver: Neo4j driver
        
    Returns:
        List of matching chunks with similarity scores
    """
    if driver is None:
        driver = get_driver()
    
    # Build WHERE clause for filtering
    filters = []
    params = {"k": k, "embedding": query_embedding}
    
    if chunk_type:
        filters.append("chunk.chunk_type = $chunk_type")
        params["chunk_type"] = chunk_type
    
    if product_number:
        filters.append("chunk.product_number = $product_number")
        params["product_number"] = product_number
    
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    
    query = f"""
    CALL db.index.vector.queryNodes('chunk_embeddings', $k, $embedding)
    YIELD node AS chunk, score
    {where_clause}
    OPTIONAL MATCH (d:Document)-[:CONTAINS_CHUNK]->(chunk)
    OPTIONAL MATCH (h:Herbicide)-[:HAS_LABEL]->(d)
    RETURN chunk.chunk_id AS chunk_id,
           chunk.text AS text,
           chunk.chunk_type AS chunk_type,
           chunk.parent_section AS section,
           chunk.product_number AS product_number,
           h.product_name AS product_name,
           h.active_constituent AS active_constituent,
           score
    ORDER BY score DESC
    """
    
    with driver.session() as session:
        result = session.run(query, **params)
        return [dict(record) for record in result]


def search_chunks(
    query_text: str,
    k: int = 10,
    chunk_type: Optional[str] = None,
    product_number: Optional[str] = None,
    driver=None
) -> list[dict]:
    """
    Semantic search for chunks using natural language query.
    
    Convenience wrapper that generates embedding from text.
    
    Args:
        query_text: Natural language query
        k: Number of results to return
        chunk_type: Optional filter by chunk type
        product_number: Optional filter by specific product
        driver: Neo4j driver
        
    Returns:
        List of matching chunks with similarity scores
    """
    embedding = embed_query(query_text)
    return vector_search_chunks(
        query_embedding=embedding,
        k=k,
        chunk_type=chunk_type,
        product_number=product_number,
        driver=driver
    )


def graph_traverse_from_chunks(
    chunk_ids: list[str],
    include_adjacent: bool = True,
    driver=None
) -> dict:
    """
    Traverse graph from chunks to related entities.
    
    Follows relationships:
    - Chunk -> MENTIONS -> Weed/Crop
    - Chunk <- CONTAINS_CHUNK <- Document <- HAS_LABEL <- Herbicide
    - Herbicide -> CONTROLS -> Weed (with details)
    
    Args:
        chunk_ids: List of chunk IDs to start from
        include_adjacent: Whether to include NEXT chunks for context
        driver: Neo4j driver
        
    Returns:
        Dictionary with chunks, herbicides, weeds, crops, and control details
    """
    if driver is None:
        driver = get_driver()
    
    with driver.session() as session:
        # Get chunks and their context
        chunks_query = """
        UNWIND $chunk_ids AS cid
        MATCH (c:Chunk {chunk_id: cid})
        OPTIONAL MATCH (c)-[:NEXT]->(next:Chunk)
        OPTIONAL MATCH (prev:Chunk)-[:NEXT]->(c)
        RETURN c.chunk_id AS chunk_id,
               c.text AS text,
               c.chunk_type AS chunk_type,
               c.parent_section AS section,
               c.product_number AS product_number,
               prev.chunk_id AS prev_chunk_id,
               prev.text AS prev_text,
               next.chunk_id AS next_chunk_id,
               next.text AS next_text
        """
        
        chunks_result = session.run(chunks_query, chunk_ids=chunk_ids)
        chunks = [dict(r) for r in chunks_result]
        
        # Get mentioned entities
        mentions_query = """
        UNWIND $chunk_ids AS cid
        MATCH (c:Chunk {chunk_id: cid})-[:MENTIONS]->(entity)
        RETURN labels(entity)[0] AS entity_type,
               CASE 
                   WHEN entity:Weed THEN entity.common_name
                   WHEN entity:Crop THEN entity.name
                   ELSE 'unknown'
               END AS entity_name,
               collect(DISTINCT cid) AS mentioned_in_chunks
        """
        
        mentions_result = session.run(mentions_query, chunk_ids=chunk_ids)
        mentions = [dict(r) for r in mentions_result]
        
        # Get associated herbicides and their control details
        herbicides_query = """
        UNWIND $chunk_ids AS cid
        MATCH (c:Chunk {chunk_id: cid})
        MATCH (d:Document {product_number: c.product_number})
        MATCH (h:Herbicide)-[:HAS_LABEL]->(d)
        OPTIONAL MATCH (h)-[:HAS_MODE_OF_ACTION]->(m:ModeOfAction)
        OPTIONAL MATCH (h)-[r:CONTROLS]->(w:Weed)
        RETURN DISTINCT h.product_number AS product_number,
               h.product_name AS product_name,
               h.active_constituent AS active_constituent,
               m.group AS moa_group,
               collect(DISTINCT {
                   weed: w.common_name,
                   crop: r.crop,
                   rate: r.rate_per_ha,
                   timing: r.application_timing,
                   control_level: r.control_level
               })[0..10] AS control_samples
        """
        
        herbicides_result = session.run(herbicides_query, chunk_ids=chunk_ids)
        herbicides = [dict(r) for r in herbicides_result]
        
        return {
            "chunks": chunks,
            "mentions": mentions,
            "herbicides": herbicides,
        }


def hybrid_search(
    query_text: str,
    k: int = 5,
    expand_graph: bool = True,
    chunk_type: Optional[str] = None,
    driver=None
) -> dict:
    """
    Hybrid search combining vector similarity with graph traversal.
    
    Pipeline:
    1. Embed query text
    2. Vector search for relevant chunks
    3. (Optional) Traverse graph from chunks to get structured data
    
    Args:
        query_text: Natural language query
        k: Number of initial chunks to retrieve
        expand_graph: Whether to traverse graph from chunks
        chunk_type: Optional filter by chunk type
        driver: Neo4j driver
        
    Returns:
        Combined results with chunks and graph context
    """
    if driver is None:
        driver = get_driver()
    
    # 1. Generate query embedding
    from graph.chunk_loader import embed_text
    query_embedding = embed_text(query_text)
    
    # 2. Vector search
    vector_results = vector_search_chunks(
        query_embedding,
        k=k,
        chunk_type=chunk_type,
        driver=driver
    )
    
    result = {
        "query": query_text,
        "chunks": vector_results,
    }
    
    # 3. Graph expansion
    if expand_graph and vector_results:
        chunk_ids = [r["chunk_id"] for r in vector_results]
        graph_context = graph_traverse_from_chunks(chunk_ids, driver=driver)
        result["graph_context"] = graph_context
    
    return result


def find_chunks_for_weed(
    weed_name: str,
    k: int = 10,
    driver=None
) -> list[dict]:
    """
    Find chunks that mention a specific weed.
    
    Uses both MENTIONS relationships and text search.
    
    Args:
        weed_name: Weed common name to search for
        k: Max results
        driver: Neo4j driver
        
    Returns:
        Relevant chunks mentioning the weed
    """
    if driver is None:
        driver = get_driver()
    
    query = """
    // First find chunks with MENTIONS relationship
    MATCH (c:Chunk)-[:MENTIONS]->(w:Weed)
    WHERE toLower(w.common_name) CONTAINS toLower($weed_name)
       OR toLower(w.display_name) CONTAINS toLower($weed_name)
    WITH c, w, 1.0 AS score
    
    UNION
    
    // Also find chunks with text match (fallback)
    MATCH (c:Chunk)
    WHERE toLower(c.text) CONTAINS toLower($weed_name)
    WITH c, null AS w, 0.8 AS score
    
    WITH c, w, score
    OPTIONAL MATCH (d:Document)-[:CONTAINS_CHUNK]->(c)
    OPTIONAL MATCH (h:Herbicide)-[:HAS_LABEL]->(d)
    RETURN c.chunk_id AS chunk_id,
           c.text AS text,
           c.chunk_type AS chunk_type,
           c.parent_section AS section,
           c.product_number AS product_number,
           h.product_name AS product_name,
           w.common_name AS matched_weed,
           score
    ORDER BY score DESC
    LIMIT $k
    """
    
    with driver.session() as session:
        result = session.run(query, weed_name=weed_name, k=k)
        return [dict(record) for record in result]


def find_chunks_for_crop(
    crop_name: str,
    k: int = 10,
    driver=None
) -> list[dict]:
    """
    Find chunks relevant to a specific crop.
    
    Args:
        crop_name: Crop name to search for
        k: Max results
        driver: Neo4j driver
        
    Returns:
        Relevant chunks for the crop
    """
    if driver is None:
        driver = get_driver()
    
    query = """
    MATCH (c:Chunk)-[:MENTIONS]->(cr:Crop)
    WHERE toLower(cr.name) CONTAINS toLower($crop_name)
       OR toLower(cr.display_name) CONTAINS toLower($crop_name)
    WITH c, cr, 1.0 AS score
    
    UNION
    
    MATCH (c:Chunk)
    WHERE toLower(c.text) CONTAINS toLower($crop_name)
    WITH c, null AS cr, 0.8 AS score
    
    WITH c, cr, score
    OPTIONAL MATCH (d:Document)-[:CONTAINS_CHUNK]->(c)
    OPTIONAL MATCH (h:Herbicide)-[:HAS_LABEL]->(d)
    RETURN c.chunk_id AS chunk_id,
           c.text AS text,
           c.chunk_type AS chunk_type,
           c.parent_section AS section,
           c.product_number AS product_number,
           h.product_name AS product_name,
           cr.name AS matched_crop,
           score
    ORDER BY score DESC
    LIMIT $k
    """
    
    with driver.session() as session:
        result = session.run(query, crop_name=crop_name, k=k)
        return [dict(record) for record in result]


def get_chunk_context(
    chunk_id: str,
    context_window: int = 2,
    driver=None
) -> dict:
    """
    Get a chunk with surrounding context (previous/next chunks).
    
    Useful for expanding RAG context when initial chunk is too short.
    
    Args:
        chunk_id: The central chunk ID
        context_window: Number of chunks before/after to include
        driver: Neo4j driver
        
    Returns:
        Central chunk with context chunks
    """
    if driver is None:
        driver = get_driver()
    
    query = """
    MATCH (center:Chunk {chunk_id: $chunk_id})
    
    // Get previous chunks
    OPTIONAL MATCH path_prev = (prev:Chunk)-[:NEXT*1..%d]->(center)
    WITH center, collect(DISTINCT prev) AS prev_chunks
    
    // Get next chunks  
    OPTIONAL MATCH path_next = (center)-[:NEXT*1..%d]->(next:Chunk)
    WITH center, prev_chunks, collect(DISTINCT next) AS next_chunks
    
    RETURN center.chunk_id AS chunk_id,
           center.text AS text,
           center.chunk_type AS chunk_type,
           center.parent_section AS section,
           center.product_number AS product_number,
           [p IN prev_chunks | {id: p.chunk_id, text: p.text}] AS prev_chunks,
           [n IN next_chunks | {id: n.chunk_id, text: n.text}] AS next_chunks
    """ % (context_window, context_window)
    
    with driver.session() as session:
        result = session.run(query, chunk_id=chunk_id)
        record = result.single()
        return dict(record) if record else None

