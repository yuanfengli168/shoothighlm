"""Infographic generation — HTML/CSS templates rendered to PNG.

Approach:
1. LLM extracts structured data from PDF text (template-specific schema)
2. Jinja2 renders HTML from built-in templates
3. Save HTML to disk (always)
4. Optionally render to PNG via Playwright (--png flag)

Templates included:
- summary_card: title, summary, key topics, sources
- topic_hierarchy: tree-style mind map visualization
- stats_card: key facts and numbers

Why HTML/CSS over AI image gen:
- Perfect CJK text rendering (zero cost)
- Deterministic — same input, same output
- Editable — user can tweak the HTML
- Free — no API costs for the structural part
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import json
import httpx
import os
import re
import jinja2
from .sampling import stratified_sample, head_sample


# Base CSS used by all templates (embedded for portability)
BASE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Hiragino Sans GB",
               "Noto Sans CJK SC", "Source Han Sans SC", sans-serif;
  background: #fafafa;
  color: #1a1a1a;
  line-height: 1.6;
  padding: 40px;
}
.card {
  max-width: 900px;
  margin: 0 auto;
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  padding: 48px;
}
.title {
  font-size: 36px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 8px;
  letter-spacing: -0.5px;
}
.subtitle {
  font-size: 14px;
  color: #64748b;
  margin-bottom: 32px;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.section { margin-bottom: 32px; }
.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid #e2e8f0;
}
.summary { font-size: 16px; color: #475569; line-height: 1.8; }
.summary p { margin-bottom: 12px; }
.topic-list { list-style: none; padding: 0; }
.topic-list li {
  padding: 12px 16px;
  margin-bottom: 8px;
  background: #f1f5f9;
  border-left: 4px solid #3b82f6;
  border-radius: 4px;
  font-size: 15px;
}
.tree { font-size: 15px; line-height: 1.8; }
.tree ul { list-style: none; padding-left: 24px; }
.tree li { position: relative; padding: 4px 0; }
.tree li::before {
  content: "├─";
  position: absolute;
  left: -20px;
  color: #94a3b8;
}
.tree > ul { padding-left: 0; }
.tree > ul > li::before { content: ""; }
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}
.stat {
  padding: 20px;
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
  color: white;
  border-radius: 12px;
}
.stat-value { font-size: 32px; font-weight: 700; margin-bottom: 4px; }
.stat-label { font-size: 13px; opacity: 0.9; }
.sources {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
  font-size: 12px;
  color: #94a3b8;
}
.footer {
  margin-top: 32px;
  text-align: center;
  font-size: 11px;
  color: #cbd5e1;
}
"""

# Built-in templates
TEMPLATES = {
    "summary_card": {
        "description": "Single-page summary with title, key topics, and source attribution",
        "schema_hint": "title (string), summary (2-3 paragraphs), key_topics (5-8 items), sources (array)",
    },
    "topic_hierarchy": {
        "description": "Tree visualization of concepts and their relationships",
        "schema_hint": "title (string), root_topic (string), children (recursive: {label, children?})",
    },
    "stats_card": {
        "description": "Key facts and numbers as visual stat blocks",
        "schema_hint": "title (string), stats (array of {label, value, unit?}), summary (1-2 sentences)",
    },
}


@dataclass
class Infographic:
    """A generated infographic (HTML + optional PNG)"""
    template: str
    title: str
    data: Dict[str, Any]
    html_content: str
    output_path: Optional[Path] = None
    png_path: Optional[Path] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "template": self.template,
            "title": self.title,
            "data": self.data,
            "output_path": str(self.output_path) if self.output_path else None,
            "png_path": str(self.png_path) if self.png_path else None,
        }


class InfographicGenerator:
    """Generate infographics from text using LLM + HTML templates."""
    
    def __init__(
        self,
        chat_model: str = "qwen3.5:cloud",
        base_url: str = "http://127.0.0.1:11434",
    ):
        self.chat_model = chat_model
        self.base_url = base_url
        # See mindmap.py for the rationale on 600s timeout
        self.client = httpx.Client(timeout=600.0)
        self.jinja_env = jinja2.Environment(
            autoescape=jinja2.select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    
    def generate(
        self,
        text: str,
        template: str = "summary_card",
        title: str = "Document",
        sources: Optional[List[str]] = None,
        use_full: bool = False,
    ) -> Infographic:
        """
        Generate an infographic from text.

        Args:
            text: Source text (PDF content)
            template: One of TEMPLATES keys
            title: Infographic title
            sources: Source document names for attribution
            use_full: If True, use a larger prompt (50K chars) for
                higher-fidelity generation on large documents.

        Returns:
            Infographic object with html_content populated

        Raises:
            ValueError: If template is unknown
            RuntimeError: If LLM call fails
        """
        if template not in TEMPLATES:
            raise ValueError(
                f"Unknown template: {template}. "
                f"Choose from: {', '.join(TEMPLATES.keys())}"
            )

        # Truncate long text. Default 12K uses stratified sampling
        # (start + middle + end) so long books don't just sample the
        # intro. --full uses 50K chars in head_sample mode.
        max_chars = 50000 if use_full else 12000
        if len(text) > max_chars:
            text = (stratified_sample(text, max_chars)
                    if not use_full
                    else head_sample(text, max_chars))

        data = self._extract_data(text, template, title)
        if sources:
            data["sources"] = sources
        # Always include the notebook/document title in render data
        data["title"] = title
        
        html = self._render_html(template, data)
        
        return Infographic(
            template=template,
            title=title,
            data=data,
            html_content=html,
        )
    
    def _extract_data(self, text: str, template: str, title: str) -> Dict[str, Any]:
        """Call LLM to extract structured data per template schema."""
        template_info = TEMPLATES[template]
        
        # Build schema example based on template
        if template == "summary_card":
            schema_example = """{
  "summary": "First paragraph...\\n\\nSecond paragraph...\\n\\nThird paragraph...",
  "key_topics": ["Topic 1", "Topic 2", "Topic 3", "Topic 4", "Topic 5"]
}"""
        elif template == "topic_hierarchy":
            schema_example = """{
  "root_topic": "Main Concept",
  "children": [
    {
      "label": "Subtopic A",
      "children": [
        {"label": "Detail A1"},
        {"label": "Detail A2"}
      ]
    },
    {
      "label": "Subtopic B",
      "children": [
        {"label": "Detail B1"}
      ]
    }
  ]
}"""
        elif template == "stats_card":
            schema_example = """{
  "summary": "Brief 1-2 sentence overview.",
  "stats": [
    {"label": "Total Chapters", "value": "12", "unit": "chapters"},
    {"label": "Main Characters", "value": "5"},
    {"label": "Time Period", "value": "1850-1900"}
  ]
}"""
        else:
            schema_example = "{}"
        
        prompt = f"""Extract structured data from the following text to populate an infographic.

## Infographic template: {template}
{template_info['description']}

## Required schema:
{schema_example}

## Title: {title}

## Instructions:
- Extract data strictly following the schema
- Use Chinese if the source is in Chinese, English if English (preserve language)
- For "summary" fields: use \\n\\n to separate paragraphs
- For lists: provide 5-8 items max
- Output ONLY valid JSON, no other text or markdown

## Source text:
{text}

## JSON:
"""
        
        response = self.client.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.chat_model,
                "prompt": prompt,
                "stream": False,
            },
        )
        response.raise_for_status()
        output = response.json()["response"]
        
        # Parse JSON
        json_str = self._extract_json(output)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"LLM returned invalid JSON: {e}\n\nResponse was:\n{output[:500]}")
        
        return data
    
    def _extract_json(self, output: str) -> str:
        """Extract JSON from LLM response, handling markdown code blocks."""
        if "```json" in output:
            return output.split("```json")[1].split("```")[0].strip()
        elif "```" in output:
            return output.split("```")[1].split("```")[0].strip()
        return output.strip()
    
    def _render_html(self, template: str, data: Dict[str, Any]) -> str:
        """Render data into HTML using the template's Jinja2 template."""
        if template == "summary_card":
            tpl_str = self._summary_card_template()
        elif template == "topic_hierarchy":
            tpl_str = self._topic_hierarchy_template()
        elif template == "stats_card":
            tpl_str = self._stats_card_template()
        else:
            raise ValueError(f"No HTML template for: {template}")
        
        tpl = self.jinja_env.from_string(tpl_str)
        return tpl.render(
            title=data.get("title", "Document"),
            data=data,
            css=BASE_CSS,
        )
    
    def _summary_card_template(self) -> str:
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>{{ title }}</title>
  <style>{{ css }}</style>
</head>
<body>
  <div class="card">
    <div class="subtitle">📚 Notebook Summary</div>
    <h1 class="title">{{ data.get('title', title) }}</h1>
    
    {% if data.get('summary') %}
    <div class="section">
      <h2 class="section-title">概述</h2>
      <div class="summary">
        {% for para in data.summary.replace('\\n\\n', '\n').split('\n') if para.strip() %}
        <p>{{ para }}</p>
        {% endfor %}
      </div>
    </div>
    {% endif %}
    
    {% if data.get('key_topics') %}
    <div class="section">
      <h2 class="section-title">关键主题</h2>
      <ul class="topic-list">
        {% for topic in data.key_topics %}
        <li>{{ topic }}</li>
        {% endfor %}
      </ul>
    </div>
    {% endif %}
    
    {% if data.get('sources') %}
    <div class="sources">
      📄 来源: {{ data.sources | join(', ') }}
    </div>
    {% endif %}
    
    <div class="footer">Generated by shootHighLM</div>
  </div>
</body>
</html>"""
    
    def _topic_hierarchy_template(self) -> str:
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>{{ title }}</title>
  <style>{{ css }}</style>
</head>
<body>
  <div class="card">
    <div class="subtitle">🌳 Topic Hierarchy</div>
    <h1 class="title">{{ data.get('title', title) }}</h1>
    
    <div class="section">
      <div class="tree">
        <ul>
          <li><strong>{{ data.get('root_topic', title) }}</strong>
            {% if data.get('children') %}
            <ul>
              {% for child in data.children %}
              <li>{{ child.label }}
                {% if child.get('children') %}
                <ul>
                  {% for grandchild in child.children %}
                  <li>{{ grandchild.label }}</li>
                  {% endfor %}
                </ul>
                {% endif %}
              </li>
              {% endfor %}
            </ul>
            {% endif %}
          </li>
        </ul>
      </div>
    </div>
    
    {% if data.get('sources') %}
    <div class="sources">
      📄 来源: {{ data.sources | join(', ') }}
    </div>
    {% endif %}
    
    <div class="footer">Generated by shootHighLM</div>
  </div>
</body>
</html>"""
    
    def _stats_card_template(self) -> str:
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>{{ title }}</title>
  <style>{{ css }}</style>
</head>
<body>
  <div class="card">
    <div class="subtitle">📊 Key Stats</div>
    <h1 class="title">{{ data.get('title', title) }}</h1>
    
    {% if data.get('summary') %}
    <div class="section">
      <p class="summary">{{ data.summary }}</p>
    </div>
    {% endif %}
    
    {% if data.get('stats') %}
    <div class="section">
      <div class="stat-grid">
        {% for stat in data.stats %}
        <div class="stat">
          <div class="stat-value">
            {{ stat.value }}{% if stat.get('unit') %} <span style="font-size: 18px; opacity: 0.8;">{{ stat.unit }}</span>{% endif %}
          </div>
          <div class="stat-label">{{ stat.label }}</div>
        </div>
        {% endfor %}
      </div>
    </div>
    {% endif %}
    
    {% if data.get('sources') %}
    <div class="sources">
      📄 来源: {{ data.sources | join(', ') }}
    </div>
    {% endif %}
    
    <div class="footer">Generated by shootHighLM</div>
  </div>
</body>
</html>"""
    
    def close(self):
        self.client.close()


def render_html_to_png(
    html_path: Path,
    png_path: Path,
    width: int = 1200,
    height: int = 1600,
    use_system_chrome: bool = True,
) -> None:
    """Render HTML file to PNG using Playwright.
    
    Args:
        html_path: Path to HTML file
        png_path: Path for output PNG
        width: Viewport width in pixels
        height: Viewport height in pixels
        use_system_chrome: If True, fall back to system Chrome when Playwright's
            bundled Chromium is not installed
    
    Raises:
        ImportError: If playwright is not installed
        RuntimeError: If rendering fails and no Chrome is available
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError(
            "playwright is required for PNG rendering. "
            "Install with: pip install playwright && playwright install chromium"
        )
    
    png_path = Path(png_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    
    with sync_playwright() as p:
        # Try Playwright's bundled chromium first; fall back to system Chrome
        launch_kwargs = {"args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        if use_system_chrome:
            for chrome_path in ("/usr/bin/google-chrome", "/usr/bin/chromium",
                                "/usr/bin/chromium-browser"):
                if Path(chrome_path).exists():
                    launch_kwargs["executable_path"] = chrome_path
                    break
        
        try:
            browser = p.chromium.launch(**launch_kwargs)
        except Exception as e:
            if "Executable doesn't exist" in str(e) and "executable_path" not in launch_kwargs:
                # No bundled chromium and no system Chrome found
                raise RuntimeError(
                    "Chromium not found. Either run `playwright install chromium` "
                    "or install Google Chrome / Chromium on your system."
                ) from e
            raise
        
        try:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(f"file://{html_path.resolve()}")
            # Wait for fonts and content to settle
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(png_path), full_page=True)
        finally:
            browser.close()
