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
            text_gen = parse_pdf(pdf)
            text = next(text_gen, "")
            if not text:
                rprint(f"[yellow]⚠ No text extracted from {pdf.name}[/yellow]")
                continue
            
            chunks = list(chunk_text(
                text,
                str(pdf),
                chunk_size=config.get("rag", "chunk_size", default=4096),
                chunk_overlap=config.get("rag", "chunk_overlap", default=200),
            ))
            
            rprint(f"  Extracted {len(chunks)} chunks")
            
            # Embed and store
            for i, chunk in enumerate(chunks):
                if i % 10 == 0:
                    rprint(f"  Embedding chunk {i}/{len(chunks)}...")
                embedding = embedder.embed(chunk.text)
                store.add(chunk.chunk_id, chunk.text, chunk.source, embedding)
            
            rprint(f"[green]✓ Indexed:[/green] {pdf.name}")
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
        
        text_gen = parse_pdf(pdf)
        text = next(text_gen, "")
        
        if not text:
            rprint(f"[yellow]⚠ No text extracted from {pdf.name}[/yellow]")
            return
        
        rprint("[dim]Extracting mind map...[/dim]")
        mindmap_tree = extractor.extract(text, title=pdf.stem)
        
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
        
        text_gen = parse_pdf(pdf)
        text = next(text_gen, "")
        
        if not text:
            rprint(f"[yellow]⚠ No text extracted from {pdf.name}[/yellow]")
            return
        
        rprint(f"[dim]Generating {num} flashcards...[/dim]")
        cards = generator.generate(text, num_cards=num, source=pdf.name)
        
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
        
        text_gen = parse_pdf(pdf)
        text = next(text_gen, "")
        
        if not text:
            rprint(f"[yellow]⚠ No text extracted from {pdf.name}[/yellow]")
            return
        
        rprint(f"[dim]Generating {duration}-minute podcast script...[/dim]")
        script = generator.generate(text, title=pdf.stem, duration_minutes=duration)
        
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


if __name__ == "__main__":
    main()
