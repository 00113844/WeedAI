We will implement a **"Sandwich" Guardrail pattern**:

1.  **Input Rail:** Filters user queries *before* they reach the agents (e.g., blocking political or medical questions).
2.  **Output Rail:** Validates the agent's response *before* sending it to the user (ensuring the response stays within the agronomic domain).

Here is the detailed development roadmap and the architectural diagram.

-----

### **Development Roadmap**

#### **Phase 1: Domain-Specific Guardrails & Governance**

*Objective: Define the "Safety Box" for the AI. If the query isn't about crops, weeds, or herbicides, the system refuses to answer.*

  * **Sub-Tasks:**
      * Define **Topical Rails** (Allowed topics: Agronomy, Botany, Chemistry, Weather. Disallowed: Human Medicine, Politics, General Coding).
      * Implement **Jailbreak Detection** (Preventing users from bypassing safety prompts).
      * Develop **Hallucination Detection** (Check if cited herbicide rates actually exist in the retrieved context).
      * Set up PII (Personally Identifiable Information) masking if user farm data is uploaded.
  * **Libraries needed:** `nemo-guardrails` (NVIDIA), `guardrails-ai`, or `llama-guard` (Meta).
  * **Resources needed:** A dedicated small LLM (e.g., a fine-tuned Llama-3-8b) specifically for classification tasks to keep latency low.

#### **Phase 2: Advanced Data Ingestion & Non-Naive Graph RAG**

*Objective: Build the base knowledge layer from APVMA documents.*

  * **Sub-Tasks:**
      * Develop a scraper for the APVMA PubCRIS database to download PDF labels.
      * Implement **Multi-Modal Parsing** to convert PDF Tables into Markdown. Create a vector store or embedding with key information. Remove repetitive information such as "Safety Directions", "First Aid Instructions". The goal is to extract only agronomically relevant data.
      * Set up **MongoDB Atlas** for vector storage. Check whether to use Pinecone, ChromaDB or Weaviate as an alternative, .
      * Implement **Contextual Chunking** (Prepend product name/active ingredient to every text chunk).
  * **Libraries needed:** `llama-parse` (for PDF tables), `beautifulsoup4`, `pymongo`, `llama-index`.
  * **Resources needed:** LlamaCloud API Key (or Unstructured.io key), MongoDB Atlas Instance.

#### **Phase 3: The Knowledge Graph (GraphRAG)**

*Objective: Map the relationships between Weeds, Crops, and Chemicals to enable complex reasoning.*

  * **Sub-Tasks:**
      * Design the Ontology (Schema): `(Herbicide)-[:CONTROLS]->(Weed)`, `(Herbicide)-[:REGISTERED_FOR]->(Crop)`.
      * Run Entity Extraction on the parsed text to populate Neo4j nodes.
      * Connect the RAG system to the Graph (GraphRAG) so the agent can query structure *and* text.
  * **Libraries needed:** `neo4j-driver`, `langchain-community` (GraphCypherQAChain), `spacy` (for entity recognition).
  * **Resources needed:** Neo4j AuraDB (Cloud) or Self-Hosted Enterprise Server.

#### **Phase 4: Simulation Wrapper (The "Sidecar")**

*Objective: Make the legacy "Weed Seed Wizard" accessible via API.*

  * **Sub-Tasks:**
      * Containerize the Weed Seed Wizard (Java/Eclipse RCP) in Docker with a headless JRE.
      * Build a **FastAPI** wrapper to accept JSON, write the simulation files, run the Java CLI, and parse the output CSV.
      * Implement an asynchronous task queue (The simulation takes time; the HTTP request shouldn't hang).
  * **Libraries needed:** `fastapi`, `celery` (or `rq`), `redis` (as message broker), `pandas` (to parse simulation outputs).
  * **Resources needed:** GCP Compute Engine or Cloud Run (requires ample RAM for Java).

#### **Phase 5: Agent Orchestration (The "Brain")**

*Objective: The LangGraph controller that routes tasks to the tools above. Discuss this with technical herbicide management team*

  * **Sub-Tasks:**
      * Build the **State Graph**: Define nodes (Supervisor, Researcher, Simulator, Coder) and edges.
      * Implement **Tool Definitions**: Standardize inputs for the Geo-agent, Reg-agent, and Sim-agent.
      * Integrate the **Guardrails** from Phase 1 into the entry/exit points of the graph.
  * **Libraries needed:** `langgraph`, `langchain`, `pydantic` (for strict data validation).
  * **Resources needed:** OpenAI API (GPT-4o) or Vertex AI (Gemini 1.5 Pro) for the Orchestrator.

#### **Phase 6: Deployment & Frontend**

*Objective: User interface and infrastructure.*

  * **Sub-Tasks:**
      * Develop React/Next.js frontend with chat interface and map visualization.
      * Implement **Auth0** or **Firebase Auth**.
      * Set up API Gateway and Usage Tracking (for future billing).
  * **Libraries needed:** `React`, `TailwindCSS`, `Leaflet` (for maps).
  * **Resources needed:** Vercel (Frontend), GCP Cloud Run (Backend).

-----

### **System Architecture Diagram**

This diagram illustrates the flow from the User, through the Guardrails, to the Orchestrator, and out to the asynchronous agents.

```mermaid
graph TD
    %% Styling
    classDef guard fill:#f9f,stroke:#333,stroke-width:2px;
    classDef agent fill:#bbf,stroke:#333,stroke-width:2px;
    classDef db fill:#ffd,stroke:#333,stroke-width:2px;
    classDef ext fill:#ddd,stroke:#333,stroke-width:2px;

    %% User Layer
    User([User]) --> Frontend[Frontend React App]
    Frontend --> Auth[Auth Layer / Usage Metering]
    Auth --> InputRail{Input Guardrails}
    
    %% Guardrails Layer
    InputRail -- "Off-Topic / Unsafe" --> Block[Block Response]
    InputRail -- "Agronomic Query" --> Orchestrator

    %% Orchestration Layer (LangGraph)
    subgraph "Reactive Agent Core (LangGraph)"
        Orchestrator[Main Orchestrator Agent]
        Orchestrator -- "Plan & Delegate" --> GeoAgent[Geospatial Agent]
        Orchestrator -- "Plan & Delegate" --> RegAgent[Regulatory Agent]
        Orchestrator -- "Plan & Delegate" --> SimAgent[Simulation Agent]
    end

    %% Tool/Data Layer
    
    %% Geospatial Path
    GeoAgent --> WeatherAPI[Weather APIs BOM/DPIRD]
    GeoAgent --> SoilDB[(Soil Database)]

    %% Regulatory Path (RAG + Graph)
    RegAgent --> HybridSearch{Hybrid Search}
    HybridSearch --> Mongo[(MongoDB Vector Store)]
    HybridSearch --> Neo4j[(Neo4j Knowledge Graph)]
    
    %% Simulation Path (Legacy Wrapper)
    SimAgent -- "Async Job" --> JobQueue[Redis Queue]
    JobQueue --> Worker[Sim Worker / Wrapper]
    Worker --> WSW[Weed Seed Wizard (Java VM)]
    WSW --> Worker
    Worker --> SimAgent

    %% Synthesis & Output
    GeoAgent --> Orchestrator
    RegAgent --> Orchestrator
    SimAgent --> Orchestrator
    Orchestrator -- "Draft Answer" --> OutputRail{Output Guardrails}
    
    OutputRail -- "Hallucination Detected" --> Orchestrator
    OutputRail -- "Safe & Verified" --> Frontend

    %% Classes
    class InputRail,OutputRail guard;
    class Orchestrator,GeoAgent,RegAgent,SimAgent agent;
    class Mongo,Neo4j,SoilDB,JobQueue db;
    class WeatherAPI,WSW ext;
```

### **Next Step**

To ensure the **Guardrails** (Phase 1) are robust, would you like me to draft the **Colang** configuration (standard for NeMo Guardrails) that specifically blocks medical advice while permitting chemical safety instructions?