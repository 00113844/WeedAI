# Knowledge Graph

## Schema (Neo4j)
Nodes: Herbicide, ActiveConstituent, ModeOfAction, Crop, Weed, State
Relationships:
- (Herbicide)-[:CONTAINS]->(ActiveConstituent)
- (Herbicide)-[:HAS_MODE_OF_ACTION]->(ModeOfAction)
- (Herbicide)-[:REGISTERED_FOR]->(Crop)
- (Herbicide)-[:CONTROLS {rate, timing, level}]->(Weed)
- (Herbicide)-[:REGISTERED_IN]->(State)

## Setup
```sh
uv pip install -e packages/graph
init-schema                       # create constraints/indexes
load-graph data/extracted         # load JSON outputs
```

## Environment
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

## Usage
- Regenerate and reload anytime after new extraction batches.
- Add Cypher queries for product lookup, crop/weed filters, plant-back periods.
- Pair with semantic retrieval for hybrid QA (planned in API layer).
