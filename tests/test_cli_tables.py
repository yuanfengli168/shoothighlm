"""Integration tests for CLI tables command"""

import json
import pytest
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from shoothighlm.cli import main
from shoothighlm.llm import LLMUsage
from shoothighlm.tables import DataTable


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def temp_notebook():
    with tempfile.TemporaryDirectory() as tmpdir:
        notebook = Path(tmpdir) / "test-notebook"
        notebook.mkdir()
        (notebook / "book.pdf").write_bytes(b"%PDF-1.4 fake")
        yield notebook


@pytest.fixture
def sample_tables():
    return [
        DataTable(
            name="Q3 Sales",
            description="Sales by region",
            columns=["Region", "Q1", "Q2", "Q3"],
            rows=[
                ["North", "10K", "12K", "15K"],
                ["South", "8K", "9K", "11K"],
            ],
            source="book.pdf",
        ),
        DataTable(
            name="Top Products",
            description="Best-selling items",
            columns=["Product", "Units Sold"],
            rows=[["Widget A", "5000"], ["Widget B", "3200"]],
            source="book.pdf",
        ),
    ]


# ============== Default invocation ==============

def test_tables_default_markdown(runner, temp_notebook, sample_tables):
    """Default invocation: markdown format, 3 max tables"""
    with patch('shoothighlm.tables.TableExtractor') as mock_class:
        mock_ext = MagicMock()
        mock_ext.extract.return_value = (sample_tables, LLMUsage())
        mock_class.return_value = mock_ext
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["text content"])
            
            result = runner.invoke(main, ['tables', str(temp_notebook)])
            
            assert result.exit_code == 0
            assert "Found 1 PDF" in result.output
            assert "Found 2 table" in result.output
            assert "Tables saved" in result.output
            
            # Default output path
            output = temp_notebook / "output" / "test-notebook-tables.md"
            assert output.exists()
            content = output.read_text()
            assert "Q3 Sales" in content
            assert "Top Products" in content


def test_tables_custom_output(runner, temp_notebook, sample_tables):
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "custom.md"
        
        with patch('shoothighlm.tables.TableExtractor') as mock_class:
            mock_ext = MagicMock()
            mock_ext.extract.return_value = (sample_tables, LLMUsage())
            mock_class.return_value = mock_ext
            
            with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
                mock_parse.return_value = iter(["text"])
                
                result = runner.invoke(main, [
                    'tables', str(temp_notebook),
                    '--output', str(output_path),
                ])
                
                assert result.exit_code == 0
                assert output_path.exists()
                content = output_path.read_text()
                assert "Q3 Sales" in content


def test_tables_csv_format(runner, temp_notebook, sample_tables):
    """CSV format outputs first table only"""
    with patch('shoothighlm.tables.TableExtractor') as mock_class:
        mock_ext = MagicMock()
        mock_ext.extract.return_value = (sample_tables, LLMUsage())
        mock_class.return_value = mock_ext
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["text"])
            
            result = runner.invoke(main, [
                'tables', str(temp_notebook), '--format', 'csv'
            ])
            
            assert result.exit_code == 0
            
            output = temp_notebook / "output" / "test-notebook-tables.csv"
            content = output.read_text()
            assert "Region,Q1,Q2,Q3" in content
            assert "North,10K,12K,15K" in content
            # Should mention the second table wasn't included
            assert "additional table" in content.lower()


def test_tables_json_format(runner, temp_notebook, sample_tables):
    with patch('shoothighlm.tables.TableExtractor') as mock_class:
        mock_ext = MagicMock()
        mock_ext.extract.return_value = (sample_tables, LLMUsage())
        mock_class.return_value = mock_ext
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["text"])
            
            result = runner.invoke(main, [
                'tables', str(temp_notebook), '--format', 'json'
            ])
            
            assert result.exit_code == 0
            
            output = temp_notebook / "output" / "test-notebook-tables.json"
            data = json.loads(output.read_text())
            assert len(data) == 2
            assert data[0]["name"] == "Q3 Sales"
            assert data[1]["name"] == "Top Products"


def test_tables_html_format(runner, temp_notebook, sample_tables):
    with patch('shoothighlm.tables.TableExtractor') as mock_class:
        mock_ext = MagicMock()
        mock_ext.extract.return_value = (sample_tables, LLMUsage())
        mock_class.return_value = mock_ext
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["text"])
            
            result = runner.invoke(main, [
                'tables', str(temp_notebook), '--format', 'html'
            ])
            
            assert result.exit_code == 0
            
            output = temp_notebook / "output" / "test-notebook-tables.html"
            content = output.read_text()
            assert "<table" in content
            assert "Q3 Sales" in content
            assert "<th>Region</th>" in content


# ============== Flags ==============

def test_tables_max_tables_flag(runner, temp_notebook, sample_tables):
    """--max flag is passed to extractor"""
    with patch('shoothighlm.tables.TableExtractor') as mock_class:
        mock_ext = MagicMock()
        mock_ext.extract.return_value = (sample_tables, LLMUsage())[:1]
        mock_class.return_value = mock_ext
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["text"])
            
            result = runner.invoke(main, [
                'tables', str(temp_notebook), '--max', '1'
            ])
            
            assert result.exit_code == 0
            call_args = mock_ext.extract.call_args
            assert call_args[1]["max_tables"] == 1


def test_tables_multiple_pdfs(runner, sample_tables):
    """Multiple PDFs in notebook all get processed"""
    with tempfile.TemporaryDirectory() as tmpdir:
        notebook = Path(tmpdir) / "multi"
        notebook.mkdir()
        (notebook / "a.pdf").write_bytes(b"%PDF-1.4 fake a")
        (notebook / "b.pdf").write_bytes(b"%PDF-1.4 fake b")
        
        with patch('shoothighlm.tables.TableExtractor') as mock_class:
            mock_ext = MagicMock()
            # Different tables per PDF
            mock_ext.extract.side_effect = [
                ([sample_tables[0]], LLMUsage()),  # from a.pdf
                ([sample_tables[1]], LLMUsage()),  # from b.pdf
            ]
            mock_class.return_value = mock_ext
            
            with patch('shoothighlm.pdf.parse_pdf', side_effect=[
                iter(["text from a"]),
                iter(["text from b"]),
            ]):
                result = runner.invoke(main, ['tables', str(notebook)])
                
                assert result.exit_code == 0
                assert "Found 2 PDF" in result.output
                assert "Total: 2 table" in result.output


# ============== Error handling ==============

def test_tables_no_pdfs(runner):
    with tempfile.TemporaryDirectory() as tmpdir:
        notebook = Path(tmpdir) / "empty"
        notebook.mkdir()
        
        result = runner.invoke(main, ['tables', str(notebook)])
        
        assert result.exit_code == 0
        assert "No PDFs found" in result.output


def test_tables_pdf_returns_no_text(runner, temp_notebook):
    with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
        mock_parse.return_value = iter([""])
        
        result = runner.invoke(main, ['tables', str(temp_notebook)])
        
        assert result.exit_code == 0
        assert "No text extracted" in result.output
        assert "No tables extracted" in result.output


def test_tables_extraction_runtime_error(runner, temp_notebook):
    """If LLM call fails, error is reported but loop continues"""
    with patch('shoothighlm.tables.TableExtractor') as mock_class:
        mock_ext = MagicMock()
        mock_ext.extract.side_effect = RuntimeError("LLM timeout")
        mock_class.return_value = mock_ext
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["text"])
            
            result = runner.invoke(main, ['tables', str(temp_notebook)])
            
            assert result.exit_code == 0
            assert "Extraction failed" in result.output
            assert "LLM timeout" in result.output


def test_tables_no_tables_found(runner, temp_notebook):
    """LLM returns empty list"""
    with patch('shoothighlm.tables.TableExtractor') as mock_class:
        mock_ext = MagicMock()
        mock_ext.extract.return_value = ([], LLMUsage())
        mock_class.return_value = mock_ext
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["text"])
            
            result = runner.invoke(main, ['tables', str(temp_notebook)])
            
            assert result.exit_code == 0
            assert "No tables found" in result.output
            assert "No tables extracted" in result.output


def test_tables_closes_extractor(runner, temp_notebook, sample_tables):
    """extractor.close() is called even on success"""
    with patch('shoothighlm.tables.TableExtractor') as mock_class:
        mock_ext = MagicMock()
        mock_ext.extract.return_value = (sample_tables, LLMUsage())
        mock_class.return_value = mock_ext
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["text"])
            
            runner.invoke(main, ['tables', str(temp_notebook)])
            
            mock_ext.close.assert_called_once()
