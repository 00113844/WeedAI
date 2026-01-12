#!/bin/bash
# WeedAI 30-PDF Subsample Test Script
#
# This script tests the complete ingestion pipeline with a 30-PDF subsample.
# It verifies all components work before processing the full 386 PDFs.
#
# Prerequisites:
# - Neo4j running and configured in .env
# - Packages installed (ingestion, graph)
# - GEMINI_API_KEY in .env

set -e  # Exit on error

REPO_ROOT="/Users/dpird-mac/Documents/DPIRD/Git/WeedAI"
SUBSAMPLE_FILE="$REPO_ROOT/test_subsample_30.txt"

cd "$REPO_ROOT"

echo "=========================================="
echo "WeedAI 30-PDF Subsample Test"
echo "=========================================="
echo ""

# Verify subsample file exists
if [ ! -f "$SUBSAMPLE_FILE" ]; then
    echo "Error: Subsample file not found: $SUBSAMPLE_FILE"
    exit 1
fi

PDF_COUNT=$(wc -l < "$SUBSAMPLE_FILE")
echo "Testing with $PDF_COUNT PDFs from $SUBSAMPLE_FILE"
echo ""

# Step 1: Parse PDFs to Markdown (using local parser - no API costs)
echo "Step 1/4: Parsing PDFs to Markdown (local PyMuPDF parser)..."
echo "------------------------------------------"
while IFS= read -r pdf_name; do
    if [ -n "$pdf_name" ]; then
        echo "  Parsing $pdf_name..."
        python -m ingestion.local_parser "$pdf_name" || echo "  Warning: Failed to parse $pdf_name"
    fi
done < "$SUBSAMPLE_FILE"
echo "✓ Parsing complete"
echo ""

# Step 2: Clean Markdown
echo "Step 2/4: Cleaning Markdown..."
echo "------------------------------------------"
python -m ingestion.cleaner data/parsed --output data/parsed-clean
echo "✓ Cleaning complete"
echo ""

# Step 3: Extract JSON with Gemini (rate-limited for API quota)
echo "Step 3/4: Extracting structured JSON with Gemini..."
echo "------------------------------------------"
echo "Note: Using --limit 30 --delay 1.0 to respect API quotas"
python -m ingestion.extractor data/parsed-clean --output data/extracted --limit 30 --delay 1.0
echo "✓ Extraction complete"
echo ""

# Step 4: Load into Neo4j
echo "Step 4/4: Loading data into Neo4j..."
echo "------------------------------------------"
echo "Initializing Neo4j schema..."
init-schema

echo ""
echo "Loading extracted JSON into graph..."
load-graph data/extracted

echo ""
echo "Getting graph statistics..."
init-schema --stats

echo ""
echo "=========================================="
echo "Subsample Test Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Verify data in Neo4j Browser: http://localhost:7474"
echo "2. Run test query: MATCH (h:Herbicide) RETURN h LIMIT 10"
echo "3. Check extraction summary: cat data/_extraction_summary.json"
echo "4. Review parsed markdown: ls data/parsed-clean/ | head"
echo ""
echo "If everything looks good, you can process remaining PDFs with:"
echo "  python -m ingestion.extractor data/parsed-clean --output data/extracted --limit 50 --delay 1.0"
echo ""
