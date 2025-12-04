import logging
from pathlib import Path
from typing import List

from dotenv import load_dotenv
import typer

from pdf_context_extraction.agents import ExtractionAgent, SchemaAgent
from pdf_context_extraction.orchestrator import ExtractionOrchestrator
from pdf_context_extraction.preprocess import PDFPreprocessor

load_dotenv()


app = typer.Typer(add_completion=False)


@app.command()
def process(
    files: List[Path],
    schema_instructions: str = typer.Option(
        ..., "--schema", "-s", help="User instructions describing fields to extract"
    ),
    percent_scale: str = typer.Option(
        "0-1",
        "--percent-scale",
        help="Percent normalization scale ('0-1' or '0-100')",
    ),
    output: Path = typer.Option(
        Path("extractions.xlsx"),
        "--output",
        "-o",
        help="Output Excel file path",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    ),
):
    """
    Run the extraction orchestrator for the provided documents.

    Current implementation is scaffold-only; agents are not wired to the LLM yet.
    """
    log_path = output.with_suffix(".log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path),
        ],
    )
    logger = logging.getLogger(__name__)
    logger.info("Logging to %s", log_path)

    orchestrator = ExtractionOrchestrator(
        schema_agent=SchemaAgent(),
        extraction_agent=ExtractionAgent(),
        pdf_preprocessor=PDFPreprocessor(),
    )
    results = orchestrator.process(
        files=files,
        user_schema_instructions=schema_instructions,
        percent_scale=percent_scale,
    )
    orchestrator.to_excel(results, output)
    for result in results:
        typer.echo(f"{result.document.name}: {result.status} ({result.error or 'ok'})")
    typer.echo(f"Wrote results to {output}")


def main():
    app()


if __name__ == "__main__":
    main()
