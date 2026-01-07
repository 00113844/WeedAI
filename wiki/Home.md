# WeedAI Wiki

## Purpose
WeedAI is an agronomic AI copilot for integrated weed management. It ingests Australian herbicide label PDFs, cleans them, extracts structured facts, and builds a Neo4j knowledge graph to power GraphRAG and downstream tools.

## What's here
- End-to-end ingestion pipeline (PDF -> Markdown -> cleaned Markdown -> Gemini JSON)
- Neo4j graph schema + loader
- Roadmap for API, UI, LangGraph orchestration, guardrails, and simulation sidecar

## Quick start
1) Install Python 3.11 and `uv`.
2) `uv pip install -e packages/ingestion` and `uv pip install -e packages/graph`.
3) Set `.env` with `GEMINI_API_KEY`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`.
4) Run ingestion (see Data Pipeline page) then `load-graph data/extracted`.

## Key directories
- `packages/ingestion`: parsing, cleaning, Gemini extraction
- `packages/graph`: Neo4j schema + loader
- `data/labels`: source PDFs (not in repo)
- `data/parsed`: Markdown outputs
- `data/extracted`: extracted JSON

## Status (current branch)
- Parsing/cleaning scripts in place; Gemini extraction command available
- Neo4j schema + loader implemented
- Roadmap defines upcoming FastAPI gateway, Next.js UI, LangGraph + guardrails, and simulation wrapper
