"""Test GraphRAG search queries."""
import warnings
import logging

# Suppress Neo4j warnings about non-existent relationship types
logging.getLogger("neo4j").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=DeprecationWarning)

from graph import search_chunks

print("=== Query: ryegrass ===")
r = search_chunks("ryegrass control rates", k=2)
for i, c in enumerate(r):
    print(f"{i+1}. [{c['chunk_type']}] Score: {c['score']:.3f}")
    print(f"   {c['text'][:150]}...\n")

print("=== Query: wheat herbicide ===")
r = search_chunks("wheat herbicide application", k=2)
for i, c in enumerate(r):
    print(f"{i+1}. [{c['chunk_type']}] Score: {c['score']:.3f}")
    print(f"   {c['text'][:150]}...\n")

print("=== Query: resistance management ===")
r = search_chunks("herbicide resistance management groups", k=2)
for i, c in enumerate(r):
    print(f"{i+1}. [{c['chunk_type']}] Score: {c['score']:.3f}")
    print(f"   {c['text'][:150]}...\n")
