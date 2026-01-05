"""
Ingestion package for WeedAI - Herbicide Label Processing

Modules:
    - parser: Parse PDFs to markdown using LlamaParse
    - csv_scraper: Download labels from APVMA based on CSV
    - scraper: Direct APVMA portal scraper
"""

from ingestion.parser import parse_single, LABELS_DIR, PARSED_DIR

__all__ = ['parse_single', 'LABELS_DIR', 'PARSED_DIR']
