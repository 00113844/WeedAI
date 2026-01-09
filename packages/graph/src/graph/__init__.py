"""
Weed WizAIrd Graph Package

Neo4j knowledge graph for herbicide selection with GraphRAG support.
"""

from graph.schema import init_schema, get_driver, get_stats, VECTOR_INDEX_CONFIG
from graph.loader import load_from_json, load_directory
from graph.chunker import Chunk, chunk_docling_json, chunk_directory
from graph.chunk_loader import (
    load_chunks_from_docling,
    load_chunks_directory,
    embed_text,
    embed_batch,
)
from graph.queries import (
    # Entity queries
    find_herbicides_for_weed,
    find_herbicides_for_crop,
    get_moa_rotation_options,
    get_herbicide_details,
    search_weeds,
    search_crops,
    get_graph_summary,
    # RAG queries
    vector_search_chunks,
    search_chunks,
    embed_query,
    graph_traverse_from_chunks,
    hybrid_search,
    find_chunks_for_weed,
    find_chunks_for_crop,
    get_chunk_context,
)
from graph.tools import (
    vector_search_tool,
    graph_traversal_tool,
    hybrid_search_tool,
    resistance_rotation_tool,
    text2cypher_tool,
    get_langchain_tools,
    create_rag_nodes,
)

__all__ = [
    # Schema & Setup
    'init_schema',
    'get_driver', 
    'get_stats',
    'VECTOR_INDEX_CONFIG',
    # Entity Loading
    'load_from_json',
    'load_directory',
    # Chunking
    'Chunk',
    'chunk_docling_json',
    'chunk_directory',
    # Chunk Loading (RAG)
    'load_chunks_from_docling',
    'load_chunks_directory',
    'embed_text',
    'embed_batch',
    # Entity Queries
    'find_herbicides_for_weed',
    'find_herbicides_for_crop',
    'get_moa_rotation_options',
    'get_herbicide_details',
    'search_weeds',
    'search_crops',
    'get_graph_summary',
    # RAG Queries
    'vector_search_chunks',
    'graph_traverse_from_chunks',
    'hybrid_search',
    'find_chunks_for_weed',
    'find_chunks_for_crop',
    'get_chunk_context',
    # Agentic Tools
    'vector_search_tool',
    'graph_traversal_tool',
    'hybrid_search_tool',
    'resistance_rotation_tool',
    'text2cypher_tool',
    'get_langchain_tools',
    'create_rag_nodes',
]
