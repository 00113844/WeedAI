# Weed WizAIrd Graph Package

Neo4j knowledge graph with GraphRAG support for herbicide selection recommendations.

## Features

- **Entity Graph**: Structured herbicide/weed/crop relationships
- **GraphRAG**: Chunk-based retrieval with vector embeddings
- **Hybrid Search**: Combined semantic + graph traversal
- **Agentic Tools**: LangGraph-compatible tools for orchestration

## Graph Schema

### Entity Nodes

- **Herbicide**: Commercial herbicide products
- **ActiveConstituent**: Chemical active ingredients
- **ModeOfAction**: Herbicide resistance groups (A-Z)
- **Crop**: Agricultural crops
- **Weed**: Weed species
- **State**: Australian states/territories

### RAG Nodes

- **Document**: Herbicide label documents (links Herbicide to Chunks)
- **Chunk**: Text chunks with embeddings for semantic search

### Relationships

**Entity Relationships:**
- `(Herbicide)-[:CONTAINS]->(ActiveConstituent)`
- `(Herbicide)-[:HAS_MODE_OF_ACTION]->(ModeOfAction)`
- `(Herbicide)-[:REGISTERED_FOR]->(Crop)`
- `(Herbicide)-[:CONTROLS {rate, timing, level}]->(Weed)`
- `(Herbicide)-[:REGISTERED_IN]->(State)`

**RAG Relationships:**
- `(Herbicide)-[:HAS_LABEL]->(Document)`
- `(Document)-[:CONTAINS_CHUNK]->(Chunk)`
- `(Chunk)-[:NEXT]->(Chunk)` (sequential reading order)
- `(Chunk)-[:MENTIONS]->(Weed|Crop)` (entity linking)

## Usage

### Setup

```bash
# Initialize virtual environment
uv venv
source .venv/bin/activate
uv pip install -e .

# Initialize schema (creates constraints, indexes, vector index)
init-schema

# Load structured entity data from extracted JSON
load-graph /path/to/extracted/json/directory

# Load chunks from Docling JSON with embeddings
load-chunks /path/to/docling/json/directory --init-schema
```

### Python API

```python
from graph import (
    # Entity queries
    find_herbicides_for_weed,
    find_herbicides_for_crop,
    get_moa_rotation_options,
    
    # RAG queries
    hybrid_search,
    vector_search_chunks,
    find_chunks_for_weed,
    
    # Agentic tools
    get_langchain_tools,
)

# Hybrid RAG search
results = hybrid_search("annual ryegrass control in wheat", k=5)
print(results["chunks"])  # Relevant text chunks
print(results["graph_context"])  # Related entities

# Entity query
herbicides = find_herbicides_for_weed("ryegrass", crop="wheat", state="WA")

# Get LangChain tools for agent
tools = get_langchain_tools()
```

### CLI Commands

```bash
# Initialize schema with vector index
init-schema

# Load entity data
load-graph data/extracted/

# Chunk Docling JSON files
chunk-docling data/docling/ --output chunks.json

# Load chunks with embeddings into Neo4j
load-chunks data/docling/ --batch-size 50
```

## Environment Variables

Required in `.env`:
```
NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io  # AuraDB
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

## Vector Index

Uses sentence-transformers `all-mpnet-base-v2` (768 dimensions) by default.
To change embedding model, update `VECTOR_INDEX_CONFIG` in `schema.py`.

## Agentic Tools

The package provides LangGraph-compatible tools:

- `vector_search_tool`: Semantic chunk retrieval
- `graph_traversal_tool`: Structured entity queries
- `hybrid_search_tool`: Combined semantic + graph search
- `resistance_rotation_tool`: MOA rotation recommendations
- `text2cypher_tool`: Natural language to Cypher queries

```python
from graph import get_langchain_tools
tools = get_langchain_tools()
```
