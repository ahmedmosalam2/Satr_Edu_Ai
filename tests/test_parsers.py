"""
tests/test_parsers.py
─────────────────────
Unit tests for document parsers.
"""

import os
import sys
import tempfile
import pytest

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestParserFactory:
    """Test parser factory auto-detection."""

    def test_supported_extensions(self):
        from src.parsers.parser_factory import get_supported_extensions
        exts = get_supported_extensions()
        assert ".pdf" in exts
        assert ".docx" in exts
        assert ".pptx" in exts
        assert ".xlsx" in exts
        assert ".html" in exts
        assert ".txt" in exts
        assert ".md" in exts
        assert ".json" in exts

    def test_is_supported(self):
        from src.parsers.parser_factory import is_supported
        assert is_supported("test.pdf") is True
        assert is_supported("test.docx") is True
        assert is_supported("test.pptx") is True
        assert is_supported("test.unknown") is False
        assert is_supported("test.exe") is False

    def test_get_parser_pdf(self):
        from src.parsers.parser_factory import get_parser
        from src.parsers.pdf_parser import PDFParser
        parser = get_parser("document.pdf")
        assert parser is not None
        assert isinstance(parser, PDFParser)

    def test_get_parser_docx(self):
        from src.parsers.parser_factory import get_parser
        from src.parsers.docx_parser import DOCXParser
        parser = get_parser("document.docx")
        assert parser is not None
        assert isinstance(parser, DOCXParser)

    def test_get_parser_unsupported(self):
        from src.parsers.parser_factory import get_parser
        parser = get_parser("file.xyz")
        assert parser is None


class TestTextParser:
    """Test text/markdown parser."""

    def test_parse_txt(self):
        from src.parsers.text_parser import TextParser
        parser = TextParser()

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Hello World\n\nThis is a test paragraph.\n\nAnother paragraph here.")
            f.flush()
            path = f.name

        try:
            pages = parser.parse(path)
            assert len(pages) > 0
            assert "Hello World" in pages[0].page_content
        finally:
            os.unlink(path)

    def test_parse_markdown(self):
        from src.parsers.text_parser import TextParser
        parser = TextParser()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("# Title\n\nFirst section content.\n\n## Subtitle\n\nSecond section content.")
            f.flush()
            path = f.name

        try:
            pages = parser.parse(path)
            assert len(pages) >= 2  # Should split by headings
            assert "Title" in pages[0].page_content
        finally:
            os.unlink(path)

    def test_parse_json(self):
        from src.parsers.text_parser import JSONParser
        parser = JSONParser()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write('[{"name": "test1"}, {"name": "test2"}]')
            f.flush()
            path = f.name

        try:
            pages = parser.parse(path)
            assert len(pages) == 2  # One per array item
        finally:
            os.unlink(path)

    def test_arabic_encoding(self):
        from src.parsers.text_parser import TextParser
        parser = TextParser()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("مرحباً بالعالم\n\nهذا اختبار للنص العربي")
            f.flush()
            path = f.name

        try:
            pages = parser.parse(path)
            assert len(pages) > 0
            assert "مرحباً" in pages[0].page_content
        finally:
            os.unlink(path)


class TestHTMLParser:
    """Test HTML parser."""

    def test_parse_html(self):
        from src.parsers.html_parser import HTMLParser
        parser = HTMLParser()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write("""
            <html><head><title>Test</title></head>
            <body>
                <h1>Main Title</h1>
                <p>First paragraph.</p>
                <h2>Section</h2>
                <p>Second paragraph.</p>
            </body></html>
            """)
            f.flush()
            path = f.name

        try:
            pages = parser.parse(path)
            assert len(pages) > 0
            # Check that it found some content
            all_text = " ".join(p.page_content for p in pages)
            assert "Main Title" in all_text
        finally:
            os.unlink(path)


class TestChunkers:
    """Test chunking strategies."""

    def test_naive_chunker(self):
        from src.chunking.naive_chunker import NaiveChunker
        from src.parsers.base_parser import ParsedPage

        chunker = NaiveChunker()
        pages = [ParsedPage(
            page_content="A" * 1000 + "\n\n" + "B" * 1000,
            metadata={"page": 0}
        )]

        chunks = chunker.chunk(pages, chunk_size=500)
        assert len(chunks) > 1  # Should split
        for chunk in chunks:
            assert len(chunk.chunk_text) <= 600  # Some tolerance

    def test_structure_chunker(self):
        from src.chunking.structure_chunker import StructureChunker
        from src.parsers.base_parser import ParsedPage

        chunker = StructureChunker()
        pages = [ParsedPage(
            page_content="# Introduction\n\nThis is the intro.\n\n# Chapter 1\n\nThis is chapter one.",
            metadata={"page": 0}
        )]

        chunks = chunker.chunk(pages, chunk_size=500)
        assert len(chunks) >= 1

    def test_qa_chunker_pseudo(self):
        from src.chunking.qa_chunker import QAChunker
        from src.parsers.base_parser import ParsedPage

        chunker = QAChunker(generation_client=None, language="ar")
        pages = [ParsedPage(
            page_content="قانون نيوتن الثاني ينص على أن القوة تساوي الكتلة مضروبة في التسارع",
            metadata={"heading": "قانون نيوتن الثاني", "page": 0}
        )]

        chunks = chunker.chunk(pages, chunk_size=500)
        assert len(chunks) > 0
        assert "Q:" in chunks[0].chunk_text
        assert "A:" in chunks[0].chunk_text

    def test_chunker_factory(self):
        from src.chunking.chunker_factory import get_chunker, list_strategies

        strategies = list_strategies()
        assert "naive" in strategies
        assert "structure" in strategies
        assert "semantic" in strategies
        assert "qa" in strategies

        for strategy in ["naive", "structure"]:
            chunker = get_chunker(strategy)
            assert chunker.name == strategy


class TestPipeline:
    """Test the pipeline orchestrator."""

    def test_pipeline_text(self):
        from src.pipeline.pipeline_manager import DocumentPipeline

        pipeline = DocumentPipeline()
        result = pipeline.process_text(
            text="Hello World. This is a test. Another sentence here.",
            chunk_strategy="naive",
            chunk_size=50,
        )

        assert result.success is True
        assert result.chunks_count > 0

    def test_pipeline_txt_file(self):
        from src.pipeline.pipeline_manager import DocumentPipeline

        pipeline = DocumentPipeline()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Test content for pipeline.\n\nSecond paragraph.")
            f.flush()
            path = f.name

        try:
            result = pipeline.process(path, chunk_strategy="naive")
            assert result.success is True
            assert result.pages_count > 0
            assert result.chunks_count > 0
            assert result.total_time_ms > 0
        finally:
            os.unlink(path)

    def test_pipeline_unsupported(self):
        from src.pipeline.pipeline_manager import DocumentPipeline

        pipeline = DocumentPipeline()
        result = pipeline.process("file.xyz")
        assert result.success is False
        assert result.error is not None

    def test_pipeline_file_not_found(self):
        from src.pipeline.pipeline_manager import DocumentPipeline

        pipeline = DocumentPipeline()
        result = pipeline.process("/nonexistent/file.txt")
        assert result.success is False

    def test_supported_extensions(self):
        from src.pipeline.pipeline_manager import DocumentPipeline
        exts = DocumentPipeline.supported_extensions()
        assert len(exts) >= 10

    def test_available_strategies(self):
        from src.pipeline.pipeline_manager import DocumentPipeline
        strategies = DocumentPipeline.available_strategies()
        assert "naive" in strategies
        assert "structure" in strategies
        assert "qa" in strategies


class TestAgent:
    """Test agent components."""

    def test_calculator_tool(self):
        import asyncio
        from src.agent.tools.calculator import CalculatorTool

        calc = CalculatorTool()
        result = asyncio.run(calc.execute(expression="2 + 3 * 4"))
        assert "14" in result

    def test_calculator_sqrt(self):
        import asyncio
        from src.agent.tools.calculator import CalculatorTool

        calc = CalculatorTool()
        result = asyncio.run(calc.execute(expression="sqrt(16)"))
        assert "4" in result

    def test_calculator_division_by_zero(self):
        import asyncio
        from src.agent.tools.calculator import CalculatorTool

        calc = CalculatorTool()
        result = asyncio.run(calc.execute(expression="1/0"))
        assert "Error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
