"""Tests for CLI commands"""

import pytest
from click.testing import CliRunner
from pathlib import Path
import tempfile
from shoothighlm.cli import main


@pytest.fixture
def runner():
    """Create CLI test runner"""
    return CliRunner()


@pytest.fixture
def temp_notebook():
    """Create a temporary notebook directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test-notebook"


def test_cli_version(runner):
    """Test CLI version flag"""
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower()


def test_cli_help(runner):
    """Test CLI help"""
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "shootHighLM" in result.output
    assert "NotebookLM" in result.output


def test_init_creates_directory(runner, temp_notebook):
    """Test init command creates notebook directory"""
    result = runner.invoke(main, ["init", str(temp_notebook)])
    assert result.exit_code == 0
    assert temp_notebook.exists()
    assert (temp_notebook / ".shoothighlm").exists()
    assert "Created" in result.output


def test_init_existing_directory(runner, temp_notebook):
    """Test init works on existing directory"""
    temp_notebook.mkdir(parents=True)
    result = runner.invoke(main, ["init", str(temp_notebook)])
    assert result.exit_code == 0
    assert "Created" in result.output


def test_index_no_pdfs(runner, temp_notebook):
    """Test index command with no PDFs"""
    # Create notebook first
    runner.invoke(main, ["init", str(temp_notebook)])
    
    result = runner.invoke(main, ["index", str(temp_notebook)])
    assert result.exit_code == 0
    assert "No PDFs found" in result.output


def test_chat_no_index(runner, temp_notebook):
    """Test chat command without index"""
    # Create notebook but don't index
    runner.invoke(main, ["init", str(temp_notebook)])
    
    result = runner.invoke(main, ["chat", str(temp_notebook), "test question"])
    assert result.exit_code == 0
    assert "No index found" in result.output
    assert "Run 'shoot-high index' first" in result.output


def test_chat_with_question(runner, temp_notebook):
    """Test chat command with a question (mocked)"""
    from unittest.mock import patch, MagicMock
    
    # Create notebook
    runner.invoke(main, ["init", str(temp_notebook)])
    
    # Create fake index
    db_dir = temp_notebook / ".shoothighlm"
    db_dir.mkdir(exist_ok=True)
    
    # Create empty database to pass existence check
    from shoothighlm.vectorstore import VectorStore
    db_path = db_dir / "vectors.db"
    store = VectorStore(db_path)
    store.close()
    
    # Mock RAG chat - patch where it's imported, not where it's defined
    with patch('shoothighlm.rag.RAGChat') as mock_rag_class:
        mock_rag = MagicMock()
        mock_rag.chat.return_value = MagicMock(
            answer="Test answer",
            citations=[],
            model="test-model"
        )
        mock_rag_class.return_value = mock_rag
        
        result = runner.invoke(main, ["chat", str(temp_notebook), "test question"])
        assert result.exit_code == 0
        assert "Q:" in result.output
        assert "test question" in result.output
        assert "Test answer" in result.output


def test_mindmap_no_pdfs(runner, temp_notebook):
    """Test mindmap command with no PDFs"""
    runner.invoke(main, ["init", str(temp_notebook)])
    
    result = runner.invoke(main, ["mindmap", str(temp_notebook)])
    assert result.exit_code == 0
    assert "No PDFs found" in result.output


def test_flashcard_no_pdfs(runner, temp_notebook):
    """Test flashcard command with no PDFs"""
    runner.invoke(main, ["init", str(temp_notebook)])
    
    result = runner.invoke(main, ["flashcard", str(temp_notebook)])
    assert result.exit_code == 0
    assert "No PDFs found" in result.output


def test_podcast_no_pdfs(runner, temp_notebook):
    """Test podcast command with no PDFs"""
    runner.invoke(main, ["init", str(temp_notebook)])
    
    result = runner.invoke(main, ["podcast", str(temp_notebook)])
    assert result.exit_code == 0
    assert "No PDFs found" in result.output
