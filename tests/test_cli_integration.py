"""Integration tests for CLI mindmap and flashcard commands"""

import pytest
from click.testing import CliRunner
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock
from shoothighlm.cli import main
from shoothighlm.mindmap import MindMapNode
from shoothighlm.flashcard import Flashcard


@pytest.fixture
def runner():
    """Create CLI test runner"""
    return CliRunner()


@pytest.fixture
def temp_notebook_with_pdf():
    """Create a temporary notebook with a fake PDF"""
    with tempfile.TemporaryDirectory() as tmpdir:
        notebook = Path(tmpdir) / "test-notebook"
        notebook.mkdir()
        
        # Create a fake PDF file
        pdf_file = notebook / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf content")
        
        yield notebook


# ============ Mindmap CLI Tests ============

def test_mindmap_markdown_output(runner, temp_notebook_with_pdf):
    """Test mindmap command with Markdown output"""
    mock_node = MindMapNode(id="root", title="Test Document", children=[])
    
    with patch('shoothighlm.mindmap.MindMapExtractor') as mock_extractor_class:
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = mock_node
        mock_extractor_class.return_value = mock_extractor
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Test content from PDF"])
            
            result = runner.invoke(main, ["mindmap", str(temp_notebook_with_pdf), "--format", "markdown"])
            
            assert result.exit_code == 0
            assert "Mind map saved to" in result.output


def test_mindmap_opml_output(runner, temp_notebook_with_pdf):
    """Test mindmap command with OPML output"""
    mock_node = MindMapNode(id="root", title="Test", children=[])
    
    with patch('shoothighlm.mindmap.MindMapExtractor') as mock_extractor_class:
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = mock_node
        mock_extractor_class.return_value = mock_extractor
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Test content"])
            
            result = runner.invoke(main, ["mindmap", str(temp_notebook_with_pdf), "--format", "opml"])
            
            assert result.exit_code == 0
            assert "Mind map saved to" in result.output


def test_mindmap_html_output(runner, temp_notebook_with_pdf):
    """Test mindmap command with HTML (Markmap) output"""
    mock_node = MindMapNode(id="root", title="Test", children=[])
    
    with patch('shoothighlm.mindmap.MindMapExtractor') as mock_extractor_class:
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = mock_node
        mock_extractor_class.return_value = mock_extractor
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Test content"])
            
            result = runner.invoke(main, ["mindmap", str(temp_notebook_with_pdf), "--format", "html"])
            
            assert result.exit_code == 0
            assert "Mind map saved to" in result.output
            # Check HTML file was created
            output_dir = temp_notebook_with_pdf / "output"
            assert output_dir.exists()
            html_files = list(output_dir.glob("*.html"))
            assert len(html_files) > 0


def test_mindmap_json_output(runner, temp_notebook_with_pdf):
    """Test mindmap command with JSON output"""
    mock_node = MindMapNode(id="root", title="Test", children=[])
    
    with patch('shoothighlm.mindmap.MindMapExtractor') as mock_extractor_class:
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = mock_node
        mock_extractor_class.return_value = mock_extractor
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Test content"])
            
            result = runner.invoke(main, ["mindmap", str(temp_notebook_with_pdf), "--format", "json"])
            
            assert result.exit_code == 0
            assert "Mind map saved to" in result.output


def test_mindmap_custom_output_path(runner, temp_notebook_with_pdf):
    """Test mindmap command with custom output path"""
    mock_node = MindMapNode(id="root", title="Test", children=[])
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "custom-output.md"
        
        with patch('shoothighlm.mindmap.MindMapExtractor') as mock_extractor_class:
            mock_extractor = MagicMock()
            mock_extractor.extract.return_value = mock_node
            mock_extractor_class.return_value = mock_extractor
            
            with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
                mock_parse.return_value = iter(["Test content"])
                
                result = runner.invoke(main, [
                    "mindmap",
                    str(temp_notebook_with_pdf),
                    "--format", "markdown",
                    "--output", str(output_path),
                ])
                
                assert result.exit_code == 0
                assert str(output_path) in result.output
                assert output_path.exists()


def test_mindmap_no_text_extracted(runner, temp_notebook_with_pdf):
    """Test mindmap when PDF parsing returns no text"""
    with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
        mock_parse.return_value = iter([""])  # Empty text
        
        result = runner.invoke(main, ["mindmap", str(temp_notebook_with_pdf)])
        
        assert result.exit_code == 0
        assert "No text extracted" in result.output


# ============ Flashcard CLI Tests ============

def test_flashcard_markdown_output(runner, temp_notebook_with_pdf):
    """Test flashcard command with Markdown output"""
    mock_cards = [
        Flashcard(id="card-1", question="Q1?", answer="A1", tags=["tag1"]),
    ]
    
    with patch('shoothighlm.flashcard.FlashcardGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = mock_cards
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Test content"])
            
            result = runner.invoke(main, [
                "flashcard",
                str(temp_notebook_with_pdf),
                "--format", "markdown",
            ])
            
            assert result.exit_code == 0
            assert "Flashcards saved to" in result.output


def test_flashcard_csv_output(runner, temp_notebook_with_pdf):
    """Test flashcard command with CSV (Anki) output"""
    mock_cards = [
        Flashcard(id="card-1", question="Q1?", answer="A1", tags=["tag1"]),
    ]
    
    with patch('shoothighlm.flashcard.FlashcardGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = mock_cards
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Test content"])
            
            result = runner.invoke(main, [
                "flashcard",
                str(temp_notebook_with_pdf),
                "--format", "csv",
            ])
            
            assert result.exit_code == 0
            assert "Flashcards saved to" in result.output


def test_flashcard_json_output(runner, temp_notebook_with_pdf):
    """Test flashcard command with JSON output"""
    mock_cards = [
        Flashcard(id="card-1", question="Q1?", answer="A1", tags=["tag1"]),
    ]
    
    with patch('shoothighlm.flashcard.FlashcardGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = mock_cards
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Test content"])
            
            result = runner.invoke(main, [
                "flashcard",
                str(temp_notebook_with_pdf),
                "--format", "json",
            ])
            
            assert result.exit_code == 0
            assert "Flashcards saved to" in result.output


def test_flashcard_custom_num(runner, temp_notebook_with_pdf):
    """Test flashcard command with custom number of cards"""
    mock_cards = [Flashcard(id=f"card-{i}", question=f"Q{i}?", answer=f"A{i}") for i in range(20)]
    
    with patch('shoothighlm.flashcard.FlashcardGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = mock_cards
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Test content"])
            
            result = runner.invoke(main, [
                "flashcard",
                str(temp_notebook_with_pdf),
                "--num", "20",
            ])
            
            assert result.exit_code == 0
            assert "Generated 20 flashcards" in result.output


def test_flashcard_custom_output_path(runner, temp_notebook_with_pdf):
    """Test flashcard command with custom output path"""
    mock_cards = [Flashcard(id="card-1", question="Q?", answer="A")]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "custom-flashcards.csv"
        
        with patch('shoothighlm.flashcard.FlashcardGenerator') as mock_gen_class:
            mock_gen = MagicMock()
            mock_gen.generate.return_value = mock_cards
            mock_gen_class.return_value = mock_gen
            
            with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
                mock_parse.return_value = iter(["Test content"])
                
                result = runner.invoke(main, [
                    "flashcard",
                    str(temp_notebook_with_pdf),
                    "--format", "csv",
                    "--output", str(output_path),
                ])
                
                assert result.exit_code == 0
                assert str(output_path) in result.output
                assert output_path.exists()


def test_flashcard_no_cards_generated(runner, temp_notebook_with_pdf):
    """Test flashcard when generator returns empty list"""
    with patch('shoothighlm.flashcard.FlashcardGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = []
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Test content"])
            
            result = runner.invoke(main, ["flashcard", str(temp_notebook_with_pdf)])
            
            assert result.exit_code == 0
            assert "No flashcards generated" in result.output


def test_flashcard_no_text_extracted(runner, temp_notebook_with_pdf):
    """Test flashcard when PDF parsing returns no text"""
    with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
        mock_parse.return_value = iter([""])  # Empty text
        
        result = runner.invoke(main, ["flashcard", str(temp_notebook_with_pdf)])
        
        assert result.exit_code == 0
        assert "No text extracted" in result.output
