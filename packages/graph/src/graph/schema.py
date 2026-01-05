"""
Neo4j schema initialization for the herbicide knowledge graph.

Creates constraints, indexes, and defines the graph structure.
"""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


def get_driver():
    """Get Neo4j driver from environment variables."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")
    
    if not password:
        raise ValueError("NEO4J_PASSWORD not found in environment variables")
    
    return GraphDatabase.driver(uri, auth=(user, password))


# ============== SCHEMA DEFINITIONS ==============

CONSTRAINTS = [
    # Unique constraints (also create indexes)
    "CREATE CONSTRAINT herbicide_product_number IF NOT EXISTS FOR (h:Herbicide) REQUIRE h.product_number IS UNIQUE",
    "CREATE CONSTRAINT active_name IF NOT EXISTS FOR (a:ActiveConstituent) REQUIRE a.name IS UNIQUE",
    "CREATE CONSTRAINT moa_group IF NOT EXISTS FOR (m:ModeOfAction) REQUIRE m.group IS UNIQUE",
    "CREATE CONSTRAINT crop_name IF NOT EXISTS FOR (c:Crop) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT weed_common_name IF NOT EXISTS FOR (w:Weed) REQUIRE w.common_name IS UNIQUE",
    "CREATE CONSTRAINT state_code IF NOT EXISTS FOR (s:State) REQUIRE s.code IS UNIQUE",
]

INDEXES = [
    # Additional indexes for common queries
    "CREATE INDEX herbicide_name IF NOT EXISTS FOR (h:Herbicide) ON (h.product_name)",
    "CREATE INDEX weed_scientific IF NOT EXISTS FOR (w:Weed) ON (w.scientific_name)",
    "CREATE INDEX active_chemical_group IF NOT EXISTS FOR (a:ActiveConstituent) ON (a.chemical_group)",
]

# Pre-populate Australian states
STATES = [
    ("NSW", "New South Wales"),
    ("VIC", "Victoria"),
    ("QLD", "Queensland"),
    ("SA", "South Australia"),
    ("WA", "Western Australia"),
    ("TAS", "Tasmania"),
    ("NT", "Northern Territory"),
    ("ACT", "Australian Capital Territory"),
]

# Mode of Action groups (herbicide resistance classification)
MOA_GROUPS = [
    ("A", "Inhibition of acetyl CoA carboxylase (ACCase inhibitors)", "Fops, Dims, Dens"),
    ("B", "Inhibition of acetolactate synthase (ALS inhibitors)", "Sulfonylureas, Imidazolinones, Triazolopyrimidines"),
    ("C", "Inhibition of photosynthesis at PSII", "Triazines, Ureas, Nitriles"),
    ("D", "Inhibition of photosynthesis at PSI", "Bipyridyliums"),
    ("E", "Inhibition of protoporphyrinogen oxidase (PPO)", "Diphenyl ethers, Oxadiazoles"),
    ("F", "Bleaching: Inhibition of carotenoid biosynthesis", "Triketones, Isoxazoles, Pyridazinones"),
    ("G", "Inhibition of EPSP synthase", "Glycines (glyphosate)"),
    ("H", "Inhibition of glutamine synthetase", "Phosphinic acids (glufosinate)"),
    ("I", "Inhibition of DHP synthase", "Carbamates"),
    ("J", "Inhibition of microtubule assembly", "Dinitroanilines, Benzamides"),
    ("K", "Inhibition of cell division / VLCFA inhibitors", "Chloroacetamides, Oxyacetamides"),
    ("L", "Inhibition of cell wall synthesis", "Nitriles, Benzamides"),
    ("M", "Uncouplers", "Dinitrophenols"),
    ("N", "Inhibition of lipid synthesis (not ACCase)", "Thiocarbamates, Phosphorodithioates"),
    ("O", "Synthetic auxins (IAA mimics)", "Phenoxy acids, Benzoic acids, Pyridine carboxylic acids"),
    ("P", "Inhibition of auxin transport", "Phthalamates, Semicarbazones"),
    ("Q", "Unknown mode of action", "Various"),
    ("R", "Inhibition of dihydropteroate synthase", "Sulfonamides"),
    ("Z", "Unknown / not classified", "Various"),
]


def init_schema(driver=None):
    """
    Initialize the Neo4j schema with constraints, indexes, and reference data.
    
    Args:
        driver: Optional Neo4j driver. If None, creates one from env vars.
    """
    if driver is None:
        driver = get_driver()
    
    with driver.session() as session:
        print("Creating constraints...")
        for constraint in CONSTRAINTS:
            try:
                session.run(constraint)
                print(f"  ✓ {constraint.split('CONSTRAINT ')[1].split(' IF')[0]}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"  ○ Already exists: {constraint.split('CONSTRAINT ')[1].split(' IF')[0]}")
                else:
                    print(f"  ✗ Error: {e}")
        
        print("\nCreating indexes...")
        for index in INDEXES:
            try:
                session.run(index)
                print(f"  ✓ {index.split('INDEX ')[1].split(' IF')[0]}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"  ○ Already exists")
                else:
                    print(f"  ✗ Error: {e}")
        
        print("\nCreating State nodes...")
        for code, name in STATES:
            session.run(
                "MERGE (s:State {code: $code}) SET s.name = $name",
                code=code, name=name
            )
        print(f"  ✓ Created {len(STATES)} state nodes")
        
        print("\nCreating ModeOfAction nodes...")
        for group, description, chemical_classes in MOA_GROUPS:
            session.run(
                """
                MERGE (m:ModeOfAction {group: $group})
                SET m.description = $description,
                    m.chemical_classes = $chemical_classes
                """,
                group=group, description=description, chemical_classes=chemical_classes
            )
        print(f"  ✓ Created {len(MOA_GROUPS)} mode of action nodes")
    
    print("\n✓ Schema initialization complete!")
    return True


def clear_graph(driver=None, confirm=False):
    """
    Clear all nodes and relationships from the graph.
    
    Args:
        driver: Optional Neo4j driver
        confirm: Must be True to actually delete
    """
    if not confirm:
        print("⚠ To clear the graph, call with confirm=True")
        return False
    
    if driver is None:
        driver = get_driver()
    
    with driver.session() as session:
        # Delete in batches to avoid memory issues
        print("Clearing graph...")
        result = session.run(
            """
            MATCH (n)
            WITH n LIMIT 10000
            DETACH DELETE n
            RETURN count(*) as deleted
            """
        )
        deleted = result.single()["deleted"]
        
        while deleted > 0:
            print(f"  Deleted {deleted} nodes...")
            result = session.run(
                """
                MATCH (n)
                WITH n LIMIT 10000
                DETACH DELETE n
                RETURN count(*) as deleted
                """
            )
            deleted = result.single()["deleted"]
    
    print("✓ Graph cleared")
    return True


def get_stats(driver=None):
    """Get statistics about the current graph."""
    if driver is None:
        driver = get_driver()
    
    with driver.session() as session:
        stats = {}
        
        # Node counts
        for label in ['Herbicide', 'Crop', 'Weed', 'ActiveConstituent', 'ModeOfAction', 'State']:
            result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
            stats[label] = result.single()["count"]
        
        # Relationship counts
        for rel_type in ['CONTROLS', 'REGISTERED_FOR', 'CONTAINS', 'HAS_MODE_OF_ACTION']:
            result = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count")
            stats[f"rel_{rel_type}"] = result.single()["count"]
        
        return stats


def main():
    """CLI entry point for schema initialization."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Initialize Neo4j schema for herbicide graph')
    parser.add_argument('--clear', action='store_true', help='Clear existing graph first')
    parser.add_argument('--stats', action='store_true', help='Show graph statistics')
    
    args = parser.parse_args()
    
    driver = get_driver()
    
    try:
        if args.stats:
            stats = get_stats(driver)
            print("Graph Statistics:")
            print("="*40)
            print("Nodes:")
            for label in ['Herbicide', 'Crop', 'Weed', 'ActiveConstituent', 'ModeOfAction', 'State']:
                print(f"  {label}: {stats[label]}")
            print("\nRelationships:")
            for rel_type in ['CONTROLS', 'REGISTERED_FOR', 'CONTAINS', 'HAS_MODE_OF_ACTION']:
                print(f"  {rel_type}: {stats[f'rel_{rel_type}']}")
            return
        
        if args.clear:
            clear_graph(driver, confirm=True)
        
        init_schema(driver)
        
    finally:
        driver.close()


if __name__ == '__main__':
    main()
