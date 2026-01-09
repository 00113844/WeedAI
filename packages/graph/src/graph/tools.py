"""
LangGraph-compatible tools for agentic GraphRAG.

Provides tool definitions that can be used with LangGraph/LangChain
for autonomous query routing and retrieval.
"""

from typing import Optional, Annotated
from pydantic import BaseModel, Field

from graph.schema import get_driver
from graph.queries import (
    vector_search_chunks,
    graph_traverse_from_chunks,
    hybrid_search,
    find_herbicides_for_weed,
    find_herbicides_for_crop,
    get_moa_rotation_options,
    get_herbicide_details,
    find_chunks_for_weed,
    find_chunks_for_crop,
)
from graph.chunk_loader import embed_text


# ============== PYDANTIC SCHEMAS FOR TOOL INPUTS ==============

class VectorSearchInput(BaseModel):
    """Input schema for vector search tool."""
    query: str = Field(description="Natural language query to search for")
    k: int = Field(default=5, description="Number of results to return")
    chunk_type: Optional[str] = Field(
        default=None,
        description="Filter by chunk type: 'weed_table', 'directions', 'metadata', 'table'"
    )


class GraphTraversalInput(BaseModel):
    """Input schema for graph traversal tool."""
    entity_type: str = Field(description="Type of entity: 'weed', 'crop', 'herbicide'")
    entity_name: str = Field(description="Name of the entity to search for")
    include_controls: bool = Field(default=True, description="Include control relationship details")


class HybridSearchInput(BaseModel):
    """Input schema for hybrid search tool."""
    query: str = Field(description="Natural language query")
    k: int = Field(default=5, description="Number of chunks to retrieve")
    expand_graph: bool = Field(default=True, description="Whether to traverse graph from chunks")


class Text2CypherInput(BaseModel):
    """Input schema for text-to-Cypher tool."""
    question: str = Field(description="Natural language question to convert to Cypher")


class HerbicideQueryInput(BaseModel):
    """Input schema for herbicide queries."""
    weed: Optional[str] = Field(default=None, description="Weed to control")
    crop: Optional[str] = Field(default=None, description="Crop being grown")
    state: Optional[str] = Field(default=None, description="Australian state code (NSW, VIC, etc.)")
    exclude_moa: Optional[str] = Field(default=None, description="MOA group to exclude for rotation")


class ResistanceRotationInput(BaseModel):
    """Input for resistance management queries."""
    current_moa: str = Field(description="Current mode of action group being used (A-Z)")
    crop: str = Field(description="Target crop")
    weed: str = Field(description="Target weed")


# ============== TOOL FUNCTIONS ==============

def vector_search_tool(query: str, k: int = 5, chunk_type: Optional[str] = None) -> str:
    """
    Search for relevant herbicide label chunks using semantic similarity.
    
    Use this tool when you need to find information in herbicide labels
    based on meaning rather than exact keyword matches. Good for:
    - Finding application instructions
    - Locating rate tables
    - Finding specific weed control information
    
    Args:
        query: Natural language description of what you're looking for
        k: Number of results (default 5)
        chunk_type: Optional filter - 'weed_table', 'directions', 'metadata'
        
    Returns:
        Formatted string with relevant chunks and their context
    """
    driver = get_driver()
    
    try:
        # Generate embedding
        query_embedding = embed_text(query)
        
        # Search
        results = vector_search_chunks(
            query_embedding,
            k=k,
            chunk_type=chunk_type,
            driver=driver
        )
        
        if not results:
            return "No relevant chunks found for your query."
        
        # Format results
        output = f"Found {len(results)} relevant chunks:\n\n"
        for i, r in enumerate(results, 1):
            output += f"--- Result {i} (score: {r['score']:.3f}) ---\n"
            output += f"Product: {r.get('product_name', 'Unknown')} ({r['product_number']})\n"
            output += f"Section: {r.get('section', 'Unknown')}\n"
            output += f"Type: {r['chunk_type']}\n"
            output += f"Content:\n{r['text'][:500]}{'...' if len(r['text']) > 500 else ''}\n\n"
        
        return output
        
    finally:
        driver.close()


def graph_traversal_tool(
    entity_type: str,
    entity_name: str,
    include_controls: bool = True
) -> str:
    """
    Query the knowledge graph for structured herbicide information.
    
    Use this tool for precise, structured queries about:
    - Herbicides registered for specific crops
    - Herbicides that control specific weeds
    - Product details (active ingredients, MOA groups)
    - Registration details
    
    Args:
        entity_type: 'weed', 'crop', or 'herbicide'
        entity_name: Name of the entity to query
        include_controls: Whether to include detailed control relationships
        
    Returns:
        Structured information from the knowledge graph
    """
    driver = get_driver()
    
    try:
        if entity_type.lower() == 'weed':
            results = find_herbicides_for_weed(entity_name, driver=driver)
            if not results:
                return f"No herbicides found for weed: {entity_name}"
            
            output = f"Herbicides controlling {entity_name}:\n\n"
            for r in results[:10]:  # Limit output
                output += f"• {r['herbicide']} ({r['product_number']})\n"
                output += f"  Active: {r['active']}\n"
                output += f"  MOA Group: {r['moa_group']}\n"
                output += f"  Crop: {r['crop']}\n"
                output += f"  Rate: {r['rate']}\n"
                if r.get('timing'):
                    output += f"  Timing: {r['timing']}\n"
                output += "\n"
            
            return output
            
        elif entity_type.lower() == 'crop':
            results = find_herbicides_for_crop(entity_name, driver=driver)
            if not results:
                return f"No herbicides found for crop: {entity_name}"
            
            output = f"Herbicides registered for {entity_name}:\n\n"
            for r in results[:10]:
                output += f"• {r['herbicide']} ({r['product_number']})\n"
                output += f"  Active: {r['active']}\n"
                output += f"  MOA Group: {r['moa_group']}\n"
                if r.get('weeds_controlled'):
                    weeds = r['weeds_controlled'][:5]
                    output += f"  Controls: {', '.join(weeds)}\n"
                output += "\n"
            
            return output
            
        elif entity_type.lower() == 'herbicide':
            result = get_herbicide_details(entity_name, driver=driver)
            if not result:
                return f"Herbicide not found: {entity_name}"
            
            output = f"Herbicide Details: {result['product_name']}\n"
            output += "=" * 40 + "\n"
            output += f"Product Number: {result['product_number']}\n"
            output += f"Active Constituent: {result['active_constituent']}\n"
            output += f"MOA Group: {result['moa_group']} - {result.get('moa_description', '')}\n"
            output += f"Registered Crops: {', '.join(result.get('registered_crops', [])[:10])}\n"
            output += f"Withholding Period: {result.get('withholding_period', 'Not specified')}\n"
            
            if include_controls and result.get('weed_controls'):
                output += "\nWeed Controls:\n"
                for wc in result['weed_controls'][:5]:
                    output += f"  • {wc['weed']} in {wc['crop']}: {wc['rate']}\n"
            
            return output
        
        else:
            return f"Unknown entity type: {entity_type}. Use 'weed', 'crop', or 'herbicide'."
            
    finally:
        driver.close()


def hybrid_search_tool(query: str, k: int = 5, expand_graph: bool = True) -> str:
    """
    Combined semantic + graph search for comprehensive results.
    
    Use this tool when you need both:
    - Relevant text chunks from herbicide labels
    - Structured data from the knowledge graph
    
    This is the most comprehensive search option, combining:
    1. Vector similarity search on label text
    2. Graph traversal to related entities
    
    Args:
        query: Natural language query
        k: Number of initial chunks to retrieve
        expand_graph: Whether to include graph context
        
    Returns:
        Combined results with text chunks and structured graph data
    """
    driver = get_driver()
    
    try:
        results = hybrid_search(
            query_text=query,
            k=k,
            expand_graph=expand_graph,
            driver=driver
        )
        
        output = f"Hybrid Search Results for: '{query}'\n"
        output += "=" * 50 + "\n\n"
        
        # Text chunks
        output += "RELEVANT TEXT CHUNKS:\n"
        for i, chunk in enumerate(results.get('chunks', [])[:5], 1):
            output += f"\n[{i}] {chunk.get('product_name', 'Unknown')} - {chunk['section']}\n"
            output += f"    Score: {chunk['score']:.3f}\n"
            text_preview = chunk['text'][:300].replace('\n', ' ')
            output += f"    {text_preview}...\n"
        
        # Graph context
        if expand_graph and results.get('graph_context'):
            ctx = results['graph_context']
            
            if ctx.get('mentions'):
                output += "\n\nMENTIONED ENTITIES:\n"
                for m in ctx['mentions']:
                    output += f"  • {m['entity_type']}: {m['entity_name']}\n"
            
            if ctx.get('herbicides'):
                output += "\n\nRELATED HERBICIDES:\n"
                for h in ctx['herbicides'][:3]:
                    output += f"  • {h['product_name']} ({h['moa_group']})\n"
                    output += f"    Active: {h['active_constituent']}\n"
        
        return output
        
    finally:
        driver.close()


def resistance_rotation_tool(
    current_moa: str,
    crop: str,
    weed: str
) -> str:
    """
    Find herbicide rotation options for resistance management.
    
    CRITICAL for agronomic advice. Use this when:
    - A farmer has been using one MOA group repeatedly
    - Resistance to a herbicide group is suspected
    - Building a rotation plan
    
    Args:
        current_moa: Current mode of action group (A, B, C, etc.)
        crop: Target crop
        weed: Target weed
        
    Returns:
        Alternative herbicides with different MOA groups
    """
    driver = get_driver()
    
    try:
        results = get_moa_rotation_options(
            current_moa=current_moa,
            crop=crop,
            weed=weed,
            driver=driver
        )
        
        if not results:
            return f"No rotation options found for {weed} in {crop} excluding MOA Group {current_moa}"
        
        output = f"Rotation Options (excluding Group {current_moa}):\n"
        output += f"Target: {weed} in {crop}\n"
        output += "=" * 40 + "\n\n"
        
        for group in results:
            output += f"GROUP {group['moa_group']}: {group['moa_description']}\n"
            for opt in group['options'][:3]:
                output += f"  • {opt['herbicide']}\n"
                output += f"    Rate: {opt['rate']}\n"
                if opt.get('timing'):
                    output += f"    Timing: {opt['timing']}\n"
            output += "\n"
        
        return output
        
    finally:
        driver.close()


def text2cypher_tool(question: str) -> str:
    """
    Generate and execute a Cypher query from natural language.
    
    ADVANCED TOOL - Use when other tools don't provide the needed data.
    This tool attempts to translate complex questions into graph queries.
    
    Examples of questions this can handle:
    - "How many herbicides control annual ryegrass?"
    - "What's the most common MOA group for wheat herbicides?"
    - "Which weeds are controlled by the most herbicides?"
    
    Args:
        question: Natural language question about the herbicide data
        
    Returns:
        Query results or error message
    """
    driver = get_driver()
    
    # Simple pattern matching for common questions
    # In production, this would use an LLM for text-to-Cypher
    question_lower = question.lower()
    
    try:
        with driver.session() as session:
            # Count queries
            if "how many herbicides" in question_lower:
                if "control" in question_lower:
                    # Extract weed name (simplified)
                    result = session.run("""
                        MATCH (h:Herbicide)-[:CONTROLS]->(w:Weed)
                        WHERE toLower(w.common_name) CONTAINS toLower($q)
                        RETURN count(DISTINCT h) as count, w.common_name as weed
                        LIMIT 1
                    """, q=question.split("control")[-1].strip().rstrip("?"))
                    record = result.single()
                    if record:
                        return f"{record['count']} herbicides control {record['weed']}"
                else:
                    result = session.run("MATCH (h:Herbicide) RETURN count(h) as count")
                    return f"Total herbicides: {result.single()['count']}"
            
            elif "most common moa" in question_lower or "most used moa" in question_lower:
                result = session.run("""
                    MATCH (h:Herbicide)-[:HAS_MODE_OF_ACTION]->(m:ModeOfAction)
                    RETURN m.group as moa, m.description as description, count(h) as count
                    ORDER BY count DESC
                    LIMIT 5
                """)
                output = "Most common MOA groups:\n"
                for r in result:
                    output += f"  Group {r['moa']} ({r['description']}): {r['count']} herbicides\n"
                return output
            
            elif "which weeds" in question_lower and "most" in question_lower:
                result = session.run("""
                    MATCH (h:Herbicide)-[:CONTROLS]->(w:Weed)
                    RETURN w.common_name as weed, count(DISTINCT h) as herbicide_count
                    ORDER BY herbicide_count DESC
                    LIMIT 10
                """)
                output = "Weeds controlled by the most herbicides:\n"
                for r in result:
                    output += f"  {r['weed']}: {r['herbicide_count']} herbicides\n"
                return output
            
            else:
                return (
                    "I couldn't parse that question into a query. "
                    "Try asking about:\n"
                    "- 'How many herbicides control [weed]?'\n"
                    "- 'What's the most common MOA group?'\n"
                    "- 'Which weeds are controlled by the most herbicides?'"
                )
                
    finally:
        driver.close()


# ============== LANGCHAIN TOOL WRAPPERS ==============

def get_langchain_tools():
    """
    Get LangChain-compatible tool definitions.
    
    Returns a list of tools that can be used with LangChain agents.
    Requires: langchain-core
    """
    try:
        from langchain_core.tools import tool
    except ImportError:
        raise ImportError(
            "langchain-core not installed. "
            "Run: pip install langchain-core"
        )
    
    @tool
    def semantic_search(query: str, k: int = 5) -> str:
        """Search herbicide labels for relevant information using semantic similarity.
        Use for finding application instructions, rate tables, or weed control info."""
        return vector_search_tool(query, k)
    
    @tool  
    def query_graph(entity_type: str, entity_name: str) -> str:
        """Query the knowledge graph for structured herbicide data.
        entity_type: 'weed', 'crop', or 'herbicide'
        entity_name: name to search for"""
        return graph_traversal_tool(entity_type, entity_name)
    
    @tool
    def comprehensive_search(query: str) -> str:
        """Combined semantic and graph search for comprehensive herbicide information.
        Use when you need both text chunks and structured data."""
        return hybrid_search_tool(query)
    
    @tool
    def rotation_options(current_moa: str, crop: str, weed: str) -> str:
        """Find herbicide rotation options to manage resistance.
        current_moa: MOA group currently in use (A-Z)
        crop: target crop
        weed: target weed"""
        return resistance_rotation_tool(current_moa, crop, weed)
    
    return [semantic_search, query_graph, comprehensive_search, rotation_options]


# ============== LANGGRAPH STATE & NODES ==============

def create_rag_nodes():
    """
    Create LangGraph nodes for RAG pipeline.
    
    Returns dict of node functions for use in a LangGraph workflow.
    """
    
    def retrieve_node(state: dict) -> dict:
        """Retrieve relevant chunks based on query."""
        query = state.get("query", "")
        results = hybrid_search_tool(query, k=5)
        return {"context": results, **state}
    
    def route_query(state: dict) -> str:
        """Route query to appropriate tool based on intent."""
        query = state.get("query", "").lower()
        
        # Simple keyword-based routing
        if any(w in query for w in ["rotation", "resistance", "alternative"]):
            return "rotation"
        elif any(w in query for w in ["how many", "count", "most common"]):
            return "cypher"
        elif any(w in query for w in ["control", "herbicide for"]):
            return "graph"
        else:
            return "semantic"
    
    def semantic_node(state: dict) -> dict:
        """Semantic search node."""
        query = state.get("query", "")
        results = vector_search_tool(query)
        return {"context": results, **state}
    
    def graph_node(state: dict) -> dict:
        """Graph traversal node."""
        query = state.get("query", "")
        # Extract entity from query (simplified)
        results = graph_traversal_tool("weed", query)
        return {"context": results, **state}
    
    return {
        "retrieve": retrieve_node,
        "route": route_query,
        "semantic": semantic_node,
        "graph": graph_node,
    }


# ============== EXPORTS ==============

__all__ = [
    # Tool functions
    "vector_search_tool",
    "graph_traversal_tool", 
    "hybrid_search_tool",
    "resistance_rotation_tool",
    "text2cypher_tool",
    # Pydantic schemas
    "VectorSearchInput",
    "GraphTraversalInput",
    "HybridSearchInput",
    "Text2CypherInput",
    "HerbicideQueryInput",
    "ResistanceRotationInput",
    # Integration helpers
    "get_langchain_tools",
    "create_rag_nodes",
]
