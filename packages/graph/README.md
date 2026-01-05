# Weed WizAIrd Graph Package

Neo4j knowledge graph for herbicide selection recommendations.

## Graph Schema

### Nodes

- **Herbicide**: Commercial herbicide products
- **ActiveConstituent**: Chemical active ingredients
- **ModeOfAction**: Herbicide resistance groups (A-Z)
- **Crop**: Agricultural crops
- **Weed**: Weed species
- **State**: Australian states/territories

### Relationships

- `(Herbicide)-[:CONTAINS]->(ActiveConstituent)`
- `(Herbicide)-[:HAS_MODE_OF_ACTION]->(ModeOfAction)`
- `(Herbicide)-[:REGISTERED_FOR]->(Crop)`
- `(Herbicide)-[:CONTROLS {rate, timing, level}]->(Weed)`
- `(Herbicide)-[:REGISTERED_IN]->(State)`

## Usage

```bash
# Initialize virtual environment
uv venv
source .venv/bin/activate
uv pip install -e .

# Initialize schema (creates constraints and indexes)
init-schema

# Load data from extracted JSON
load-graph /path/to/extracted/json/directory
```

## Environment Variables

Required in `.env`:
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```
