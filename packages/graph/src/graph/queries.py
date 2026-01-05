"""
Common Cypher queries for the herbicide knowledge graph.

These queries power the GraphRAG retrieval system.
"""

from typing import Optional
from graph.schema import get_driver


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
