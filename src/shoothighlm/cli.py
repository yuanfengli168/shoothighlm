"""
shootHighLM CLI — Chinese-first, multi-LLM CLI alternative to Google NotebookLM
"""

import json
import click
from rich import print as rprint
from pathlib import Path
from . import __version__
from .config import init_config, Config


@click.group()
@click.version_option(version=__version__)
def main():
    """📚 shootHighLM — Chinese-first NotebookLM alternative
    
    Drop PDFs in a folder, run commands, get mind maps, flashcards, and AI-powered Q&A.
    """
    pass


@main.command()
@click.argument("notebook", type=click.Path(exists=False))
def init(notebook: str):
    """Initialize a new notebook directory"""
    rprint(f"[green]Initializing notebook:[/green] {notebook}")
    notebook_path = Path(notebook)
    notebook_path.mkdir(parents=True, exist_ok=True)
    
    # Create .shoothighlm config in notebook
    config_dir = notebook_path / ".shoothighlm"
    config_dir.mkdir(exist_ok=True)
    
    rprint(f"[green]✓ Created:[/green] {notebook_path}")
    rprint(f"[green]✓ Config dir:[/green] {config_dir}")


@main.command()
@click.argument("notebook", type=click.Path(exists=True))
def index(notebook: str):
    """Index PDFs in a notebook"""
    from .pdf import parse_pdf, chunk_text
    from .embedding import get_embedder
    from .vectorstore import VectorStore
    
    config = init_config()
    notebook_path = Path(notebook)
    
    # Find PDFs
    pdfs = list(notebook_path.glob("*.pdf"))
    if not pdfs:
        rprint("[red]No PDFs found in notebook[/red]")
        return
    
    rprint(f"[green]Found {len(pdfs)} PDF(s)[/green]")
    
    # Initialize vector store
    db_path = notebook_path / ".shoothighlm" / "vectors.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = VectorStore(db_path)
    
    # Get embedder
    embedder = get_embedder(model=config.get("models", "embedding", default="bge-m3"))
    
    # Process each PDF
    for pdf in pdfs:
        rprint(f"[blue]Processing:[/blue] {pdf.name}")
        try:
            # Concatenate text from every page (was: only first page!)
            all_text = "\n\n".join(page_text for page_text in parse_pdf(pdf) if page_text)
            if not all_text.strip():
                rprint(f"[yellow]⚠ No text extracted from {pdf.name}[/yellow]")
                continue

            chunks = list(chunk_text(
                all_text,
                str(pdf),
                chunk_size=config.get("rag", "chunk_size", default=4096),
                chunk_overlap=config.get("rag", "chunk_overlap", default=200),
            ))

            rprint(f"  Extracted {len(chunks)} chunks ({len(all_text):,} chars)")

            # Embed and store — skip individual chunk failures instead of
            # aborting the whole PDF (e.g. one bad page can fail to embed
            # even after truncation).
            ok = 0
            failed = 0
            for i, chunk in enumerate(chunks):
                if i % 5 == 0 or i == len(chunks) - 1:
                    rprint(f"  Embedding chunk {i + 1}/{len(chunks)}...")
                try:
                    embedding = embedder.embed(chunk.text)
                    store.add(chunk.chunk_id, chunk.text, chunk.source, embedding)
                    ok += 1
                except Exception as e:
                    failed += 1
                    rprint(
                        f"[yellow]  ⚠ Skipped chunk {i + 1} "
                        f"({len(chunk.text)} chars): {e}[/yellow]"
                    )

            rprint(
                f"[green]✓ Indexed:[/green] {pdf.name} "
                f"[dim]({ok}/{len(chunks)} chunks, {failed} skipped)[/dim]"
            )
        except Exception as e:
            rprint(f"[red]✗ Error:[/red] {e}")
    
    store.close()
    rprint("[green]✓ Indexing complete[/green]")


@main.command()
@click.argument("notebook", type=click.Path(exists=True))
@click.argument("question", nargs=-1)
@click.option("--model", "model", default=None, help="Override chat model")
def chat(notebook: str, question: tuple[str], model: str):
    """Chat with your PDFs"""
    from .config import Config
    from .embedding import get_embedder
    from .vectorstore import VectorStore
    from .rag import RAGChat
    
    config = Config()
    notebook_path = Path(notebook)
    
    # Check for indexed database
    db_path = notebook_path / ".shoothighlm" / "vectors.db"
    if not db_path.exists():
        rprint("[red]No index found. Run 'shoot-high index' first.[/red]")
        return
    
    # Initialize components
    store = VectorStore(db_path)
    embedder = get_embedder(model=config.get("models", "embedding", default="bge-m3"))
    chat_model = model or config.get("models", "chat", default="qwen3.5:cloud")
    
    rag = RAGChat(
        vectorstore=store,
        embedder=embedder,
        chat_model=chat_model,
        top_k=config.get("rag", "top_k", default=5),
        min_similarity=config.get("rag", "min_similarity", default=0.7),
    )
    
    try:
        if question:
            # Single question mode
            query = " ".join(question)
            rprint(f"[bold]Q:[/bold] {query}")
            rprint("[dim]Thinking...[/dim]")
            response = rag.chat(query)
            rprint(f"[green]A:[/green] {response.answer}")
        else:
            # Interactive mode
            rprint("[green]Chat mode. Type 'quit' to exit.[/green]")
            while True:
                try:
                    query = click.prompt(click.style("Q", bold=True, fg="green"), prompt_suffix="> ")
                except EOFError:
                    break
                if query.lower() in ["quit", "exit", "q"]:
                    break
                if not query.strip():
                    continue
                rprint("[dim]Thinking...[/dim]")
                response = rag.chat(query)
                rprint(f"[green]A:[/green] {response.answer}")
    finally:
        rag.close()
        store.close()


@main.command()
@click.argument("notebook", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["markdown", "opml", "html", "json"]), default="markdown")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
def mindmap(notebook: str, fmt: str, output: str):
    """Generate mind map from PDFs"""
    from .config import Config
    from .pdf import parse_pdf
    from .mindmap import MindMapExtractor
    
    config = Config()
    notebook_path = Path(notebook)
    
    # Find PDFs
    pdfs = list(notebook_path.glob("*.pdf"))
    if not pdfs:
        rprint("[red]No PDFs found in notebook[/red]")
        return
    
    rprint(f"[green]Found {len(pdfs)} PDF(s)[/green]")
    
    # Initialize extractor
    extractor = MindMapExtractor(
        chat_model=config.get("models", "chat", default="qwen3.5:cloud"),
    )
    
    try:
        # Process first PDF (for now)
        pdf = pdfs[0]
        rprint(f"[blue]Processing:[/blue] {pdf.name}")

        # Concatenate text from every page (was: only first page!)
        all_text = "\n\n".join(t for t in parse_pdf(pdf) if t)
        if not all_text.strip():
            rprint(f"[yellow]⚠ No text extracted from {pdf.name}[/yellow]")
            return

        rprint(f"  Extracted {len(all_text):,} chars")
        rprint("[dim]Extracting mind map...[/dim]")
        mindmap_tree = extractor.extract(all_text, title=pdf.stem)
        
        # Export based on format
        if fmt == "markdown":
            content = mindmap_tree.to_markdown()
            ext = ".md"
        elif fmt == "opml":
            content = f'<?xml version="1.0" encoding="UTF-8"?>\n<opml version="2.0">\n<head><title>{pdf.stem}</title></head>\n<body>\n{mindmap_tree.to_opml()}\n</body>\n</opml>'
            ext = ".opml"
        elif fmt == "json":
            content = json.dumps(mindmap_tree.to_dict(), indent=2, ensure_ascii=False)
            ext = ".json"
        elif fmt == "html":
            # Generate Markmap HTML
            md_content = mindmap_tree.to_markdown()
            content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>{pdf.stem} - Mind Map</title>
  <script src="https://cdn.jsdelivr.net/npm/markmap-autoloader@latest"></script>
  <style>
    body {{ margin: 0; padding: 20px; }}
    .markmap {{ width: 100%; height: 90vh; }}
  </style>
</head>
<body>
  <h1>{pdf.stem}</h1>
  <div class="markmap">

{md_content}

  </div>
</body>
</html>"""
            ext = ".html"
        
        # Write to file
        if output:
            output_path = Path(output)
        else:
            output_dir = notebook_path / "output"
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / f"{pdf.stem}-mindmap{ext}"
        
        output_path.write_text(content, encoding="utf-8")
        rprint(f"[green]✓ Mind map saved to:[/green] {output_path}")
        
    finally:
        extractor.close()


@main.command()
@click.argument("notebook", type=click.Path(exists=True))
@click.option("--num", "-n", default=10, help="Number of flashcards to generate")
@click.option("--format", "fmt", type=click.Choice(["markdown", "csv", "json"]), default="markdown")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
def flashcard(notebook: str, num: int, fmt: str, output: str):
    """Generate flashcards from PDFs"""
    from .config import Config
    from .pdf import parse_pdf
    from .flashcard import FlashcardGenerator
    
    config = Config()
    notebook_path = Path(notebook)
    
    # Find PDFs
    pdfs = list(notebook_path.glob("*.pdf"))
    if not pdfs:
        rprint("[red]No PDFs found in notebook[/red]")
        return
    
    rprint(f"[green]Found {len(pdfs)} PDF(s)[/green]")
    
    # Initialize generator
    generator = FlashcardGenerator(
        chat_model=config.get("models", "chat", default="qwen3.5:cloud"),
    )
    
    try:
        # Process first PDF (for now)
        pdf = pdfs[0]
        rprint(f"[blue]Processing:[/blue] {pdf.name}")

        # Concatenate text from every page (was: only first page!)
        all_text = "\n\n".join(t for t in parse_pdf(pdf) if t)
        if not all_text.strip():
            rprint(f"[yellow]⚠ No text extracted from {pdf.name}[/yellow]")
            return

        rprint(f"[dim]Generating {num} flashcards...[/dim]")
        cards = generator.generate(all_text, num_cards=num, source=pdf.name)
        
        if not cards:
            rprint("[yellow]⚠ No flashcards generated[/yellow]")
            return
        
        rprint(f"[green]✓ Generated {len(cards)} flashcards[/green]")
        
        # Export based on format
        if fmt == "markdown":
            content = "# Flashcards\n\n"
            for card in cards:
                content += card.to_markdown() + "\n\n"
            ext = ".md"
        elif fmt == "csv":
            lines = ["question,answer,tags"]
            for card in cards:
                lines.append(card.to_anki_csv())
            content = "\n".join(lines)
            ext = ".csv"
        elif fmt == "json":
            content = json.dumps([card.to_dict() for card in cards], indent=2, ensure_ascii=False)
            ext = ".json"
        
        # Write to file
        if output:
            output_path = Path(output)
        else:
            output_dir = notebook_path / "output"
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / f"{pdf.stem}-flashcards{ext}"
        
        output_path.write_text(content, encoding="utf-8")
        rprint(f"[green]✓ Flashcards saved to:[/green] {output_path}")
        
    finally:
        generator.close()


@main.command()
@click.argument("notebook", type=click.Path(exists=True))
@click.option("--duration", "-d", default=5, help="Podcast duration in minutes")
@click.option("--format", "fmt", type=click.Choice(["markdown", "json"]), default="markdown")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
@click.option("--host-a", default="Alex", help="Host A name")
@click.option("--host-b", default="Jamie", help="Host B name")
def podcast(notebook: str, duration: int, fmt: str, output: str, host_a: str, host_b: str):
    """Generate podcast from PDFs"""
    from .config import Config
    from .pdf import parse_pdf
    from .podcast import PodcastGenerator
    
    config = Config()
    notebook_path = Path(notebook)
    
    # Find PDFs
    pdfs = list(notebook_path.glob("*.pdf"))
    if not pdfs:
        rprint("[red]No PDFs found in notebook[/red]")
        return
    
    rprint(f"[green]Found {len(pdfs)} PDF(s)[/green]")
    
    # Initialize generator
    generator = PodcastGenerator(
        chat_model=config.get("models", "chat", default="qwen3.5:cloud"),
        host_a_name=host_a,
        host_b_name=host_b,
    )
    
    try:
        # Process first PDF (for now)
        pdf = pdfs[0]
        rprint(f"[blue]Processing:[/blue] {pdf.name}")

        # Concatenate text from every page (was: only first page!)
        all_text = "\n\n".join(t for t in parse_pdf(pdf) if t)
        if not all_text.strip():
            rprint(f"[yellow]⚠ No text extracted from {pdf.name}[/yellow]")
            return

        rprint(f"[dim]Generating {duration}-minute podcast script...[/dim]")
        script = generator.generate(all_text, title=pdf.stem, duration_minutes=duration)
        
        rprint(f"[green]✓ Generated {len(script.segments)} dialogue segments[/green]")
        
        # Export based on format
        if fmt == "markdown":
            content = script.to_markdown()
            ext = ".md"
        elif fmt == "json":
            content = script.to_json()
            ext = ".json"
        
        # Write to file
        if output:
            output_path = Path(output)
        else:
            output_dir = notebook_path / "output"
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / f"{pdf.stem}-podcast{ext}"
        
        output_path.write_text(content, encoding="utf-8")
        rprint(f"[green]✓ Podcast script saved to:[/green] {output_path}")
        
    finally:
        generator.close()


@main.command()
@click.argument("script", type=click.Path(exists=True))
@click.option("--provider", default=None, help="TTS provider (fish-audio, cosyvoice)")
@click.option("--voice-a", default=None, help="Voice ID for host A")
@click.option("--voice-b", default=None, help="Voice ID for host B")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output WAV path")
@click.option("--pause", default=0.4, help="Silence between segments (seconds)")
def synthesize(
    script: str,
    provider: str,
    voice_a: str,
    voice_b: str,
    output: str,
    pause: float,
):
    """Synthesize audio from a podcast script (JSON format)"""
    from .config import Config
    from .tts import get_provider, PodcastSynthesizer, TTSError
    
    config = Config()
    
    # Load script JSON
    script_path = Path(script)
    try:
        script_data = json.loads(script_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        rprint(f"[red]✗ Invalid JSON in script file:[/red] {e}")
        return
    
    segments = script_data.get("segments", [])
    if not segments:
        rprint("[red]✗ Script has no segments to synthesize[/red]")
        return
    
    # Get provider
    provider_name = provider or config.get("tts", "provider", default="fish-audio")
    
    try:
        tts_provider = get_provider(provider_name)
    except TTSError as e:
        rprint(f"[red]✗ TTS provider error:[/red] {e}")
        rprint("[yellow]Tip:[/yellow] Set FISH_AUDIO_API_KEY environment variable, "
               "or configure tts.api_key in ~/.shoothighlm/config.yaml")
        return
    
    synth = PodcastSynthesizer(
        tts_provider,
        host_a_voice=voice_a,
        host_b_voice=voice_b,
    )
    
    try:
        # Default output path
        if output:
            output_path = Path(output)
        else:
            output_path = script_path.parent / f"{script_path.stem}.wav"
        
        rprint(f"[blue]Synthesizing {len(segments)} segments via {tts_provider.name()}...[/blue]")
        
        result = synth.synthesize_script(segments, output_path, pause_seconds=pause)
        
        rprint(f"[green]✓ Audio saved:[/green] {result['output_path']}")
        rprint(f"[green]✓ Duration:[/green] {result['duration_seconds']}s "
               f"({result['segment_count']} segments)")
    except TTSError as e:
        rprint(f"[red]✗ Synthesis failed:[/red] {e}")
    finally:
        synth.close()


@main.command()
@click.argument("notebook", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["markdown", "json"]), default="markdown")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
@click.option("--questions", "-q", default=5, help="Number of suggested questions")
def guide(notebook: str, fmt: str, output: str, questions: int):
    """Generate notebook guide (summary, key topics, suggested questions)"""
    from .config import Config
    from .pdf import parse_pdf
    from .guide import GuideGenerator
    
    config = Config()
    notebook_path = Path(notebook)
    
    # Find PDFs
    pdfs = list(notebook_path.glob("*.pdf"))
    if not pdfs:
        rprint("[red]No PDFs found in notebook[/red]")
        return
    
    rprint(f"[green]Found {len(pdfs)} PDF(s)[/green]")
    
    # Initialize generator
    generator = GuideGenerator(
        chat_model=config.get("models", "chat", default="qwen3.5:cloud"),
    )
    
    try:
        # Combine text from all PDFs (guides work on the whole notebook)
        all_text = ""
        sources = []
        for pdf in pdfs:
            rprint(f"[blue]Processing:[/blue] {pdf.name}")
            pdf_text = "\n\n".join(t for t in parse_pdf(pdf) if t)
            if pdf_text:
                all_text += f"\n\n=== {pdf.name} ===\n\n" + pdf_text
                sources.append(pdf.name)
            else:
                rprint(f"[yellow]⚠ No text extracted from {pdf.name}[/yellow]")
        
        if not all_text.strip():
            rprint("[red]No text extracted from any PDFs[/red]")
            return
        
        rprint(f"[dim]Generating guide with {questions} suggested questions...[/dim]")
        notebook_guide = generator.generate(
            all_text,
            title=notebook_path.name,
            sources=sources,
            num_questions=questions,
        )
        
        # Export based on format
        if fmt == "markdown":
            content = notebook_guide.to_markdown()
            ext = ".md"
        elif fmt == "json":
            content = notebook_guide.to_json()
            ext = ".json"
        
        # Write to file
        if output:
            output_path = Path(output)
        else:
            output_dir = notebook_path / "output"
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / f"{notebook_path.name}-guide{ext}"
        
        output_path.write_text(content, encoding="utf-8")
        rprint(f"[green]✓ Guide saved to:[/green] {output_path}")
        
    finally:
        generator.close()


@main.command()
@click.argument("notebook", type=click.Path(exists=True))
@click.option("--template", "-t",
              type=click.Choice(["summary_card", "topic_hierarchy", "stats_card"]),
              default="summary_card",
              help="Infographic template")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output HTML path")
@click.option("--png", "to_png", is_flag=True, help="Also render to PNG (requires playwright)")
@click.option("--width", default=1200, help="PNG viewport width")
@click.option("--height", default=1600, help="PNG viewport height")
def infographic(notebook: str, template: str, output: str, to_png: bool, width: int, height: int):
    """Generate an infographic from PDFs (HTML + optional PNG)"""
    from .config import Config
    from .pdf import parse_pdf
    from .infographic import InfographicGenerator, render_html_to_png
    
    config = Config()
    notebook_path = Path(notebook)
    
    # Find PDFs
    pdfs = list(notebook_path.glob("*.pdf"))
    if not pdfs:
        rprint("[red]No PDFs found in notebook[/red]")
        return
    
    rprint(f"[green]Found {len(pdfs)} PDF(s)[/green]")
    
    generator = InfographicGenerator(
        chat_model=config.get("models", "chat", default="qwen3.5:cloud"),
    )
    
    try:
        # Combine text from all PDFs
        all_text = ""
        sources = []
        for pdf in pdfs:
            rprint(f"[blue]Processing:[/blue] {pdf.name}")
            all_text_pdf = "\n\n".join(t for t in parse_pdf(pdf) if t)
            if all_text_pdf:
                all_text += f"\n\n=== {pdf.name} ===\n\n" + all_text_pdf
                sources.append(pdf.name)
            else:
                rprint(f"[yellow]⚠ No text extracted from {pdf.name}[/yellow]")

        if not all_text.strip():
            rprint("[red]No text extracted from any PDFs[/red]")
            return

        rprint(f"[dim]Generating {template} infographic...[/dim]")
        info = generator.generate(
            all_text,
            template=template,
            title=notebook_path.name,
            sources=sources,
        )
        
        # Determine output paths
        if output:
            html_path = Path(output)
        else:
            output_dir = notebook_path / "output"
            output_dir.mkdir(exist_ok=True)
            html_path = output_dir / f"{notebook_path.name}-{template}.html"
        
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(info.html_content, encoding="utf-8")
        info.output_path = html_path
        
        rprint(f"[green]✓ HTML saved:[/green] {html_path}")
        
        # Optionally render to PNG
        if to_png:
            png_path = html_path.with_suffix(".png")
            try:
                rprint(f"[dim]Rendering to PNG (viewport: {width}x{height})...[/dim]")
                render_html_to_png(html_path, png_path, width=width, height=height)
                info.png_path = png_path
                rprint(f"[green]✓ PNG saved:[/green] {png_path}")
            except ImportError as e:
                rprint(f"[red]✗ PNG render failed:[/red] {e}")
                rprint("[yellow]Tip:[/yellow] pip install playwright && playwright install chromium")
            except Exception as e:
                rprint(f"[red]✗ PNG render failed:[/red] {e}")
        
    except (ValueError, RuntimeError) as e:
        rprint(f"[red]✗ Generation failed:[/red] {e}")
    finally:
        generator.close()


@main.command()
@click.argument("notebook", type=click.Path(exists=True))
@click.option("--max", "max_tables", default=3, help="Maximum number of tables to extract")
@click.option("--format", "fmt",
              type=click.Choice(["markdown", "csv", "json", "html"]),
              default="markdown", help="Output format")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
def tables(notebook: str, max_tables: int, fmt: str, output: str):
    """Extract data tables from PDFs (comparisons, statistics, lists, timelines)"""
    from .config import Config
    from .pdf import parse_pdf
    from .tables import TableExtractor
    
    config = Config()
    notebook_path = Path(notebook)
    
    # Find PDFs
    pdfs = list(notebook_path.glob("*.pdf"))
    if not pdfs:
        rprint("[red]No PDFs found in notebook[/red]")
        return
    
    rprint(f"[green]Found {len(pdfs)} PDF(s)[/green]")
    
    extractor = TableExtractor(
        chat_model=config.get("models", "chat", default="qwen3.5:cloud"),
    )
    
    all_tables = []
    try:
        for pdf in pdfs:
            rprint(f"[blue]Processing:[/blue] {pdf.name}")
            all_text = "\n\n".join(t for t in parse_pdf(pdf) if t)

            if not all_text.strip():
                rprint(f"[yellow]⚠ No text extracted from {pdf.name}[/yellow]")
                continue
            
            rprint(f"[dim]Extracting up to {max_tables} tables...[/dim]")
            try:
                tables_found = extractor.extract(all_text, max_tables=max_tables, source=pdf.name)
            except RuntimeError as e:
                rprint(f"[red]✗ Extraction failed for {pdf.name}:[/red] {e}")
                continue
            
            if tables_found:
                rprint(f"[green]✓ Found {len(tables_found)} table(s) in {pdf.name}[/green]")
                all_tables.extend(tables_found)
            else:
                rprint(f"[yellow]⚠ No tables found in {pdf.name}[/yellow]")
        
        if not all_tables:
            rprint("[yellow]⚠ No tables extracted from any PDFs[/yellow]")
            return
        
        rprint(f"[green]✓ Total: {len(all_tables)} table(s)[/green]")
        
        # Render output
        if fmt == "markdown":
            content = "# Data Tables\n\n"
            content += f"_Extracted from {len(pdfs)} PDF(s)._\n\n"
            for t in all_tables:
                content += t.to_markdown() + "\n"
            ext = ".md"
        elif fmt == "csv":
            # CSV can only meaningfully hold one table — use the first,
            # but include metadata in the header.
            content = "# Data Tables (CSV format — first table only)\n\n"
            content += all_tables[0].to_csv()
            if len(all_tables) > 1:
                content += f"\n\n# Note: {len(all_tables) - 1} additional table(s) not included in CSV. Use --format json or markdown for all tables.\n"
            ext = ".csv"
        elif fmt == "json":
            content = json.dumps(
                [t.to_dict() for t in all_tables],
                indent=2,
                ensure_ascii=False,
            )
            ext = ".json"
        elif fmt == "html":
            content = "<!DOCTYPE html>\n<html><head><meta charset='UTF-8'>\n"
            content += "<title>Data Tables</title>\n<style>\n"
            content += "table.data-table { border-collapse: collapse; margin: 1em 0; }\n"
            content += "table.data-table th, table.data-table td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; }\n"
            content += "table.data-table th { background: #f0f0f0; }\n"
            content += "table.data-table caption { font-weight: bold; margin-bottom: 0.5em; }\n"
            content += "</style>\n</head>\n<body>\n"
            content += "<h1>Data Tables</h1>\n"
            for t in all_tables:
                content += t.to_html() + "\n"
            content += "</body></html>\n"
            ext = ".html"
        
        # Write to file
        if output:
            output_path = Path(output)
        else:
            output_dir = notebook_path / "output"
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / f"{notebook_path.name}-tables{ext}"
        
        output_path.write_text(content, encoding="utf-8")
        rprint(f"[green]✓ Tables saved to:[/green] {output_path}")
        
    except (ValueError, RuntimeError) as e:
        rprint(f"[red]✗ Tables extraction failed:[/red] {e}")
    finally:
        extractor.close()


if __name__ == "__main__":
    main()
