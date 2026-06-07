"""
shootHighLM CLI — Chinese-first, multi-LLM CLI alternative to Google NotebookLM
"""

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
@click.option("--format", "fmt", type=click.Choice(["markdown", "opml", "html", "freemind", "xmind"]), default="markdown")
@click.option("--tui", is_flag=True, help="Open interactive TUI")
def mindmap(notebook: str, fmt: str, tui: bool):
    """Generate mind map from PDFs"""
    rprint(f"[green]Generating mind map:[/green] {notebook} ({fmt})")
    if tui:
        rprint("[yellow]TUI coming soon...[/yellow]")
    rprint("[yellow]Mind map extraction coming soon...[/yellow]")


@main.command()
@click.argument("notebook", type=click.Path(exists=True))
def flashcard(notebook: str):
    """Generate flashcards from PDFs"""
    rprint(f"[green]Generating flashcards:[/green] {notebook}")
    rprint("[yellow]Flashcard generation coming soon...[/yellow]")


@main.command()
@click.argument("notebook", type=click.Path(exists=True))
def podcast(notebook: str):
    """Generate podcast from PDFs"""
    rprint(f"[green]Generating podcast:[/green] {notebook}")
    rprint("[yellow]Podcast generation coming soon...[/yellow]")


if __name__ == "__main__":
    main()
