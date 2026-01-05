"""
Neo4j loader for extracted herbicide JSON data.

Loads structured herbicide data into the knowledge graph.
"""

import json
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from neo4j import GraphDatabase
from dotenv import load_dotenv

from graph.schema import get_driver, init_schema

load_dotenv()


def normalize_crop_name(name: str) -> str:
    """Normalize crop names for consistent matching."""
    return name.lower().strip()


def normalize_weed_name(name: str) -> str:
    """Normalize weed names for consistent matching."""
    # Lowercase and strip
    name = name.lower().strip()
    # Remove common variations
    name = name.replace("'s", "s")  # Patterson's -> pattersons
    return name


def load_from_json(json_path: Path, driver=None) -> dict:
    """
    Load a single extracted JSON file into Neo4j.
    
    Args:
        json_path: Path to the extracted JSON file
        driver: Optional Neo4j driver
    
    Returns:
        Statistics about loaded entities
    """
    if driver is None:
        driver = get_driver()
    
    # Read JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    stats = {
        'herbicide': 0,
        'crops': 0,
        'weeds': 0,
        'controls_rels': 0,
        'registered_for_rels': 0,
    }
    
    with driver.session() as session:
        # 1. Create/update Herbicide node
        product_number = data.get('product_number', json_path.stem.replace('ELBL', ''))
        
        session.run(
            """
            MERGE (h:Herbicide {product_number: $product_number})
            SET h.product_name = $product_name,
                h.active_constituent = $active_constituent,
                h.chemical_group = $chemical_group,
                h.withholding_period = $withholding_period,
                h.application_methods = $application_methods,
                h.updated_at = datetime()
            """,
            product_number=product_number,
            product_name=data.get('product_name', ''),
            active_constituent=data.get('active_constituent', ''),
            chemical_group=data.get('chemical_group'),
            withholding_period=data.get('withholding_period'),
            application_methods=data.get('application_methods', []),
        )
        stats['herbicide'] = 1
        
        # 2. Create ActiveConstituent and link
        active = data.get('active_constituent', '')
        if active:
            session.run(
                """
                MERGE (a:ActiveConstituent {name: $name})
                SET a.chemical_group = $chemical_group
                WITH a
                MATCH (h:Herbicide {product_number: $product_number})
                MERGE (h)-[:CONTAINS]->(a)
                """,
                name=active,
                chemical_group=data.get('chemical_group'),
                product_number=product_number,
            )
        
        # 3. Link to ModeOfAction
        moa = data.get('mode_of_action_group', '')
        if moa:
            session.run(
                """
                MATCH (h:Herbicide {product_number: $product_number})
                MATCH (m:ModeOfAction {group: $group})
                MERGE (h)-[:HAS_MODE_OF_ACTION]->(m)
                """,
                product_number=product_number,
                group=moa.upper(),
            )
        
        # 4. Create Crop nodes and REGISTERED_FOR relationships
        for crop_name in data.get('registered_crops', []):
            normalized = normalize_crop_name(crop_name)
            session.run(
                """
                MERGE (c:Crop {name: $normalized})
                SET c.display_name = $display_name
                WITH c
                MATCH (h:Herbicide {product_number: $product_number})
                MERGE (h)-[:REGISTERED_FOR]->(c)
                """,
                normalized=normalized,
                display_name=crop_name,
                product_number=product_number,
            )
            stats['crops'] += 1
            stats['registered_for_rels'] += 1
        
        # 5. Create Weed nodes from registered_weeds list
        for weed_name in data.get('registered_weeds', []):
            normalized = normalize_weed_name(weed_name)
            session.run(
                """
                MERGE (w:Weed {common_name: $normalized})
                SET w.display_name = $display_name
                """,
                normalized=normalized,
                display_name=weed_name,
            )
            stats['weeds'] += 1
        
        # 6. Create detailed CONTROLS relationships from weed_control_entries
        for entry in data.get('weed_control_entries', []):
            weed_normalized = normalize_weed_name(entry.get('weed_common_name', ''))
            crop_normalized = normalize_crop_name(entry.get('crop', ''))
            
            if not weed_normalized or not crop_normalized:
                continue
            
            # Ensure Weed node exists
            session.run(
                """
                MERGE (w:Weed {common_name: $normalized})
                SET w.display_name = $display_name,
                    w.scientific_name = COALESCE($scientific_name, w.scientific_name)
                """,
                normalized=weed_normalized,
                display_name=entry.get('weed_common_name', ''),
                scientific_name=entry.get('weed_scientific_name'),
            )
            
            # Ensure Crop node exists
            session.run(
                """
                MERGE (c:Crop {name: $normalized})
                SET c.display_name = $display_name
                """,
                normalized=crop_normalized,
                display_name=entry.get('crop', ''),
            )
            
            # Create CONTROLS relationship with properties
            # Use MERGE with unique key to avoid duplicates
            session.run(
                """
                MATCH (h:Herbicide {product_number: $product_number})
                MATCH (w:Weed {common_name: $weed_name})
                MERGE (h)-[r:CONTROLS {crop: $crop}]->(w)
                SET r.rate_per_ha = $rate,
                    r.application_timing = $timing,
                    r.control_level = $level,
                    r.critical_comments = $comments,
                    r.states = $states
                """,
                product_number=product_number,
                weed_name=weed_normalized,
                crop=crop_normalized,
                rate=entry.get('rate_per_ha', ''),
                timing=entry.get('application_timing'),
                level=entry.get('control_level', 'control'),
                comments=entry.get('critical_comments'),
                states=entry.get('states', []),
            )
            stats['controls_rels'] += 1
            
            # Link Herbicide to states
            for state in entry.get('states', []):
                session.run(
                    """
                    MATCH (h:Herbicide {product_number: $product_number})
                    MATCH (s:State {code: $state})
                    MERGE (h)-[:REGISTERED_IN]->(s)
                    """,
                    product_number=product_number,
                    state=state.upper(),
                )
    
    return stats


def load_directory(
    input_dir: Path,
    driver=None,
    limit: Optional[int] = None,
    init: bool = True
) -> dict:
    """
    Load all extracted JSON files from a directory.
    
    Args:
        input_dir: Directory containing extracted JSON files
        driver: Optional Neo4j driver
        limit: Maximum files to process
        init: Whether to initialize schema first
    
    Returns:
        Summary statistics
    """
    input_dir = Path(input_dir)
    
    if driver is None:
        driver = get_driver()
    
    # Initialize schema if requested
    if init:
        print("Initializing schema...")
        init_schema(driver)
        print()
    
    # Get JSON files (exclude summary files)
    json_files = [f for f in input_dir.glob("*.json") 
                  if not f.name.startswith('_')]
    
    if limit:
        json_files = json_files[:limit]
    
    total = len(json_files)
    print(f"Loading {total} herbicide files into Neo4j...\n")
    
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_files': total,
        'succeeded': 0,
        'errors': 0,
        'total_crops': 0,
        'total_weeds': 0,
        'total_controls': 0,
        'error_files': [],
    }
    
    for i, json_path in enumerate(json_files, 1):
        print(f"[{i}/{total}] Loading: {json_path.name}")
        
        try:
            stats = load_from_json(json_path, driver)
            summary['succeeded'] += 1
            summary['total_crops'] += stats['crops']
            summary['total_weeds'] += stats['weeds']
            summary['total_controls'] += stats['controls_rels']
            print(f"  ✓ {stats['crops']} crops, {stats['weeds']} weeds, {stats['controls_rels']} controls")
            
        except Exception as e:
            summary['errors'] += 1
            summary['error_files'].append({
                'file': json_path.name,
                'error': str(e)
            })
            print(f"  ✗ Error: {e}")
    
    return summary


def main():
    """CLI entry point for loading data."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Load extracted herbicide JSON into Neo4j knowledge graph'
    )
    parser.add_argument(
        'input',
        type=Path,
        help='Input JSON file or directory'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Maximum files to process'
    )
    parser.add_argument(
        '--no-init',
        action='store_true',
        help='Skip schema initialization'
    )
    
    args = parser.parse_args()
    
    driver = get_driver()
    
    try:
        if args.input.is_file():
            # Single file
            print(f"Loading: {args.input}")
            stats = load_from_json(args.input, driver)
            print(f"\n✓ Loaded 1 herbicide")
            print(f"  Crops: {stats['crops']}")
            print(f"  Weeds: {stats['weeds']}")
            print(f"  CONTROLS relationships: {stats['controls_rels']}")
        else:
            # Directory
            summary = load_directory(
                args.input,
                driver,
                limit=args.limit,
                init=not args.no_init
            )
            
            print(f"\n{'='*50}")
            print("LOAD COMPLETE")
            print(f"{'='*50}")
            print(f"Files processed: {summary['total_files']}")
            print(f"Succeeded: {summary['succeeded']}")
            print(f"Errors: {summary['errors']}")
            print(f"\nGraph additions:")
            print(f"  Crop registrations: {summary['total_crops']}")
            print(f"  Weed entries: {summary['total_weeds']}")
            print(f"  CONTROLS relationships: {summary['total_controls']}")
            
            if summary['error_files']:
                print(f"\nError files:")
                for err in summary['error_files']:
                    print(f"  - {err['file']}: {err['error']}")
    
    finally:
        driver.close()


if __name__ == '__main__':
    main()
