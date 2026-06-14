"""Tests for data table extraction"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from shoothighlm.tables import DataTable, TableExtractor


@pytest.fixture
def extractor():
    return TableExtractor(chat_model="test-model")


# ============== DataTable dataclass ==============

def test_datatable_basic():
    t = DataTable(
        name="Sales",
        description="Q3 sales by region",
        columns=["Region", "Q1", "Q2", "Q3"],
        rows=[
            ["North", "10K", "12K", "15K"],
            ["South", "8K", "9K", "11K"],
        ],
    )
    assert t.name == "Sales"
    assert len(t.rows) == 2
    assert t.rows[0] == ["North", "10K", "12K", "15K"]


def test_datatable_normalizes_short_rows():
    """Rows with fewer cells than columns get padded with empty strings"""
    t = DataTable(
        name="X",
        description="",
        columns=["A", "B", "C"],
        rows=[["1", "2"]],  # only 2 cells, needs 3
    )
    assert t.rows[0] == ["1", "2", ""]


def test_datatable_normalizes_long_rows():
    """Rows with more cells than columns get truncated"""
    t = DataTable(
        name="X",
        description="",
        columns=["A", "B"],
        rows=[["1", "2", "3", "4"]],  # 4 cells, only 2 cols
    )
    assert t.rows[0] == ["1", "2"]


def test_datatable_coerces_non_string_cells():
    """All cell values get coerced to strings"""
    t = DataTable(
        name="X",
        description="",
        columns=["A", "B"],
        rows=[[1, 2.5], [True, None]],
    )
    assert t.rows[0] == ["1", "2.5"]
    assert t.rows[1] == ["True", ""]


def test_datatable_to_dict():
    t = DataTable(
        name="Sales",
        description="Q3 by region",
        columns=["Region", "Q1"],
        rows=[["North", "10K"]],
        source="book.pdf",
    )
    d = t.to_dict()
    assert d["name"] == "Sales"
    assert d["description"] == "Q3 by region"
    assert d["columns"] == ["Region", "Q1"]
    assert d["rows"] == [["North", "10K"]]
    assert d["source"] == "book.pdf"


# ============== to_markdown ==============

def test_to_markdown_basic():
    t = DataTable(
        name="Sales",
        description="By region",
        columns=["Region", "Q1", "Q2"],
        rows=[["North", "10", "12"], ["South", "8", "9"]],
    )
    md = t.to_markdown()
    assert md.startswith("### Sales\n\n")
    assert "_By region_" in md
    assert "| Region | Q1 | Q2 |" in md
    # Separator row (3 columns)
    assert "---" in md
    assert md.count("|") >= 12  # rough sanity: header + sep + 2 body rows
    assert "| North | 10 | 12 |" in md
    assert "| South | 8 | 9 |" in md


def test_to_markdown_no_description():
    t = DataTable(
        name="X",
        description="",
        columns=["A"],
        rows=[["1"]],
    )
    md = t.to_markdown()
    # No empty italic line
    assert "__\n" not in md
    assert "### X" in md


def test_to_markdown_empty_columns():
    t = DataTable(name="Bad", description="", columns=[], rows=[])
    md = t.to_markdown()
    assert "### Bad" in md
    assert "no columns" in md.lower() or "_(no columns)_" in md


# ============== to_csv ==============

def test_to_csv_basic():
    t = DataTable(
        name="Sales",
        description="ignored in CSV",
        columns=["Region", "Q1"],
        rows=[["North", "10"]],
    )
    csv = t.to_csv()
    assert csv == "Region,Q1\nNorth,10"


def test_to_csv_quotes_special_chars():
    t = DataTable(
        name="X",
        description="",
        columns=["Name", "Note"],
        rows=[['Smith, John', 'Hello "world"'], ["Multi\nline", "ok"]],
    )
    csv = t.to_csv()
    # Comma triggers quoting
    assert '"Smith, John"' in csv
    # Internal quotes get doubled
    assert '"Hello ""world"""' in csv
    # Newlines trigger quoting
    assert '"Multi\nline"' in csv
    assert csv.endswith("ok")


# ============== to_html ==============

def test_to_html_basic():
    t = DataTable(
        name="Sales",
        description="By region",
        columns=["Region", "Q1"],
        rows=[["North", "10"]],
    )
    html = t.to_html()
    assert "<table" in html
    assert "<caption>Sales</caption>" in html
    assert "<th>Region</th>" in html
    assert "<th>Q1</th>" in html
    assert "<td>North</td>" in html
    assert "data-table" in html
    assert "<em>By region</em>" in html


def test_to_html_no_columns():
    t = DataTable(name="X", description="caption", columns=[], rows=[])
    html = t.to_html()
    assert "<table" in html
    assert "caption" in html.lower() or "X" in html


# ============== TableExtractor ==============

def test_extractor_init(extractor):
    assert extractor.chat_model == "test-model"
    assert extractor.base_url == "http://127.0.0.1:11434"


def test_extractor_default_model():
    e = TableExtractor()
    assert e.chat_model == "qwen3.5:cloud"
    e.close()


def test_extractor_close(extractor):
    with patch.object(extractor.client, "close") as mock_close:
        extractor.close()
        mock_close.assert_called_once()


def test_extract_returns_empty_for_empty_text(extractor):
    """No text → no tables, no LLM call"""
    result, _usage = extractor.extract("", max_tables=3)
    assert result == []


def test_extract_returns_empty_for_whitespace(extractor):
    result, _usage = extractor.extract("   \n\t  ", max_tables=3)
    assert result == []


def test_extract_basic(extractor):
    """Successful extraction with a single table"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": json.dumps([
            {
                "name": "Q3 Sales",
                "description": "Sales by region",
                "columns": ["Region", "Q3"],
                "rows": [["North", "15K"], ["South", "11K"]],
            }
        ])
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(extractor.client, "post", return_value=mock_response):
        tables, _usage = extractor.extract("Some text about sales.", max_tables=3)
    
    assert len(tables) == 1
    t = tables[0]
    assert t.name == "Q3 Sales"
    assert t.description == "Sales by region"
    assert t.columns == ["Region", "Q3"]
    assert t.rows == [["North", "15K"], ["South", "11K"]]


def test_extract_multiple_tables(extractor):
    """Returns up to max_tables tables"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": json.dumps([
            {"name": "T1", "description": "", "columns": ["A"], "rows": [["1"]]},
            {"name": "T2", "description": "", "columns": ["B"], "rows": [["2"]]},
            {"name": "T3", "description": "", "columns": ["C"], "rows": [["3"]]},
            {"name": "T4", "description": "", "columns": ["D"], "rows": [["4"]]},
        ])
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(extractor.client, "post", return_value=mock_response):
        tables, _usage = extractor.extract("text", max_tables=2)
    
    assert len(tables) == 2
    assert tables[0].name == "T1"
    assert tables[1].name == "T2"


def test_extract_sets_source(extractor):
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": json.dumps([{
            "name": "X", "description": "", "columns": ["A"], "rows": [["1"]]
        }])
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(extractor.client, "post", return_value=mock_response):
        tables, _usage = extractor.extract("text", source="book.pdf")
    
    assert tables[0].source == "book.pdf"


def test_extract_handles_json_code_block(extractor):
    """LLM wraps JSON in ```json ... ``` block"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": "```json\n[{\"name\": \"X\", \"description\": \"\", \"columns\": [\"A\"], \"rows\": [[\"1\"]]}]\n```"
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(extractor.client, "post", return_value=mock_response):
        tables, _usage = extractor.extract("text")
    
    assert len(tables) == 1
    assert tables[0].name == "X"


def test_extract_handles_bare_code_block(extractor):
    """LLM wraps JSON in ``` ... ``` (no language tag)"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": "```\n[{\"name\": \"X\", \"description\": \"\", \"columns\": [\"A\"], \"rows\": [[\"1\"]]}]\n```"
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(extractor.client, "post", return_value=mock_response):
        tables, _usage = extractor.extract("text")
    
    assert len(tables) == 1


def test_extract_handles_raw_json(extractor):
    """LLM returns raw JSON without any code fence"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": '[{"name": "X", "description": "", "columns": ["A"], "rows": [["1"]]}]'
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(extractor.client, "post", return_value=mock_response):
        tables, _usage = extractor.extract("text")
    
    assert len(tables) == 1


def test_extract_invalid_json_raises(extractor):
    """Non-JSON response should raise RuntimeError"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": "Sorry, I cannot extract tables from this text."
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(extractor.client, "post", return_value=mock_response):
        with pytest.raises(RuntimeError) as exc_info:
            extractor.extract("text")
        assert "invalid JSON" in str(exc_info.value)


def test_extract_non_array_raises(extractor):
    """LLM returns a single object instead of array"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": '{"name": "X", "columns": ["A"], "rows": []}'
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(extractor.client, "post", return_value=mock_response):
        with pytest.raises(RuntimeError) as exc_info:
            extractor.extract("text")
        assert "expected JSON array" in str(exc_info.value)


def test_extract_http_error_raises(extractor):
    """HTTP error should raise RuntimeError"""
    import httpx
    
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Server Error", request=Mock(), response=Mock()
    )
    
    with patch.object(extractor.client, "post", return_value=mock_response):
        with pytest.raises(RuntimeError) as exc_info:
            extractor.extract("text")
        assert "LLM request failed" in str(exc_info.value)


def test_extract_skips_malformed_entries(extractor):
    """Skip entries that aren't dicts or have no columns"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": json.dumps([
            {"name": "Good", "description": "", "columns": ["A"], "rows": [["1"]]},
            "not a dict",
            {"name": "NoColumns", "description": "", "columns": [], "rows": []},
            {"name": "AlsoGood", "description": "", "columns": ["B"], "rows": [["2"]]},
        ])
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(extractor.client, "post", return_value=mock_response):
        tables, _usage = extractor.extract("text")
    
    # Should skip the string and the no-columns entry
    assert len(tables) == 2
    assert tables[0].name == "Good"
    assert tables[1].name == "AlsoGood"


def test_extract_truncates_long_text(extractor):
    """Test that long text uses stratified sampling (start + middle + end)."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": "[]"
    }
    mock_response.raise_for_status = Mock()
    
    long_text = "X" * 100000
    
    with patch.object(extractor.client, "post", return_value=mock_response) as mock_post:
        extractor.extract(long_text)
        
        call_args = mock_post.call_args
        prompt = call_args[1]["json"]["prompt"]
        # Default mode uses stratified_sample, not the legacy
        # "... [truncated]" head-cut marker.
        assert "[... middle of document ...]" in prompt
        assert "[... end of document ...]" in prompt
        # The prompt itself should be well under 40K chars
        assert len(prompt) < 40000


def test_extract_default_max_tables(extractor):
    """If max_tables not specified, default is 3"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": "[]"
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(extractor.client, "post", return_value=mock_response) as mock_post:
        extractor.extract("text")
        call_args = mock_post.call_args
        prompt = call_args[1]["json"]["prompt"]
        # Default should be 3
        assert "up to 3" in prompt or "{max_tables}".format(max_tables=3) in prompt or "3 meaningful" in prompt


def test_extract_empty_array(extractor):
    """LLM returns empty array — should return empty list, not error"""
    mock_response = Mock()
    mock_response.json.return_value = {"response": "[]"}
    mock_response.raise_for_status = Mock()
    
    with patch.object(extractor.client, "post", return_value=mock_response):
        tables, _usage = extractor.extract("text")
    
    assert tables == []
