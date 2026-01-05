"""
Tests for the PDF parser module.

Run with: pytest tests/test_parser.py -v
Or for a single live test: python -m tests.test_parser
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from ingestion.parser import (
    parse_pdf,
    load_metadata,
    save_metadata,
    LABELS_DIR,
    PARSED_DIR,
    PARSING_INSTRUCTION,
)


class TestParserConfig:
    """Test parser configuration."""

    def test_labels_dir_exists(self):
        """Verify labels directory exists with PDFs."""
        assert LABELS_DIR.exists(), f"Labels directory not found: {LABELS_DIR}"
        pdf_count = len(list(LABELS_DIR.glob("*.pdf")))
        assert pdf_count > 0, "No PDF files found in labels directory"
        print(f"✓ Found {pdf_count} PDF files")

    def test_parsed_dir_created(self):
        """Verify parsed directory is created."""
        assert PARSED_DIR.exists(), f"Parsed directory should be auto-created: {PARSED_DIR}"

    def test_parsing_instruction_content(self):
        """Verify parsing instruction contains key extraction targets."""
        required_terms = [
            "Active constituent",
            "Crop",
            "Weed",
            "Application rate",
            "growth stage",
            "Herbicide mode of action",
        ]
        for term in required_terms:
            assert term.lower() in PARSING_INSTRUCTION.lower(), \
                f"Parsing instruction missing key term: {term}"
        print("✓ Parsing instruction contains all required extraction targets")


class TestMetadata:
    """Test metadata persistence."""

    def test_load_empty_metadata(self, tmp_path):
        """Test loading when no metadata exists."""
        with patch('ingestion.parser.METADATA_FILE', tmp_path / 'meta.json'):
            from ingestion.parser import load_metadata
            meta = load_metadata()
            assert meta == {'parsed': {}, 'failed': []}

    def test_save_and_load_metadata(self, tmp_path):
        """Test saving and loading metadata."""
        meta_file = tmp_path / 'meta.json'
        with patch('ingestion.parser.METADATA_FILE', meta_file):
            from ingestion.parser import load_metadata, save_metadata
            
            test_meta = {
                'parsed': {'12345ELBL': {'pages': 5, 'output': '12345ELBL.md'}},
                'failed': ['99999ELBL']
            }
            save_metadata(test_meta)
            
            loaded = load_metadata()
            assert loaded == test_meta
            print("✓ Metadata save/load working correctly")


class TestParsePDF:
    """Test PDF parsing functionality."""

    @pytest.mark.asyncio
    async def test_parse_pdf_skips_existing(self, tmp_path):
        """Test that existing parsed files are skipped."""
        # Create a mock existing output file
        output_path = tmp_path / "test.md"
        output_path.write_text("existing content")
        
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"fake pdf")
        
        mock_parser = MagicMock()
        
        result = await parse_pdf(mock_parser, pdf_path, output_path)
        
        assert result['success'] is True
        assert result['skipped'] is True
        mock_parser.aload_data.assert_not_called()
        print("✓ Parser correctly skips existing files")

    @pytest.mark.asyncio
    async def test_parse_pdf_success(self, tmp_path):
        """Test successful PDF parsing."""
        pdf_path = tmp_path / "12345ELBL.pdf"
        pdf_path.write_bytes(b"fake pdf content")
        output_path = tmp_path / "12345ELBL.md"
        
        # Mock LlamaParse response
        mock_doc = MagicMock()
        mock_doc.text = "# Product Name\n\nActive: Glyphosate 450g/L"
        
        mock_parser = MagicMock()
        mock_parser.aload_data = AsyncMock(return_value=[mock_doc])
        
        result = await parse_pdf(mock_parser, pdf_path, output_path)
        
        assert result['success'] is True
        assert result['skipped'] is False
        assert result['pages'] == 1
        assert output_path.exists()
        
        content = output_path.read_text()
        assert "product_number: 12345" in content
        assert "Glyphosate" in content
        print("✓ Parser successfully processes PDF and adds metadata header")

    @pytest.mark.asyncio
    async def test_parse_pdf_error_handling(self, tmp_path):
        """Test error handling during parsing."""
        pdf_path = tmp_path / "bad.pdf"
        pdf_path.write_bytes(b"corrupt")
        output_path = tmp_path / "bad.md"
        
        mock_parser = MagicMock()
        mock_parser.aload_data = AsyncMock(side_effect=Exception("API Error"))
        
        result = await parse_pdf(mock_parser, pdf_path, output_path)
        
        assert result['success'] is False
        assert result['error'] == "API Error"
        assert not output_path.exists()
        print("✓ Parser handles errors gracefully")


# --- Live Integration Test ---
# This test actually calls the LlamaParse API

@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_parse_single_pdf():
    """
    Live integration test - parses a real PDF using LlamaParse API.
    
    Requires: LLAMA_CLOUD_API_KEY in .env
    Run with: pytest tests/test_parser.py -v -m integration
    """
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not api_key or api_key == "llx-your-api-key-here":
        pytest.skip("LLAMA_CLOUD_API_KEY not configured - skipping live test")
    
    from llama_parse import LlamaParse
    
    # Pick the first available PDF
    pdf_files = sorted(LABELS_DIR.glob("*.pdf"))
    if not pdf_files:
        pytest.skip("No PDF files available for testing")
    
    test_pdf = pdf_files[0]
    output_path = PARSED_DIR / f"{test_pdf.stem}_test.md"
    
    # Clean up any previous test output
    if output_path.exists():
        output_path.unlink()
    
    print(f"\n🔄 Live parsing: {test_pdf.name}")
    
    parser = LlamaParse(
        api_key=api_key,
        result_type="markdown",
        language="en",
        parsing_instruction=PARSING_INSTRUCTION,
        premium_mode=True,
        continuous_mode=True,
    )
    
    result = await parse_pdf(parser, test_pdf, output_path)
    
    assert result['success'] is True, f"Parse failed: {result['error']}"
    assert output_path.exists(), "Output file not created"
    
    content = output_path.read_text()
    assert len(content) > 500, "Parsed content seems too short"
    assert "---" in content, "Missing YAML frontmatter"
    
    print(f"✓ Successfully parsed {test_pdf.name}")
    print(f"  Pages: {result['pages']}")
    print(f"  Output: {output_path}")
    print(f"  Content length: {len(content)} chars")
    print(f"\n--- First 1000 chars of output ---\n{content[:1000]}")
    
    # Cleanup test file
    # output_path.unlink()  # Uncomment to auto-cleanup


# Allow running directly for quick live test
if __name__ == "__main__":
    import asyncio
    
    print("=" * 60)
    print("INGESTION PARSER - LIVE TEST")
    print("=" * 60)
    
    # Run unit tests first
    print("\n[1/2] Running unit tests...")
    pytest.main([__file__, "-v", "-x", "--ignore-glob=*integration*", "-m", "not integration"])
    
    # Prompt for live test
    print("\n[2/2] Live API test")
    response = input("Run live LlamaParse API test? (y/N): ").strip().lower()
    if response == 'y':
        asyncio.run(test_live_parse_single_pdf())
    else:
        print("Skipped live test.")
