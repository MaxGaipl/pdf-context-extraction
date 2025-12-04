from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Literal, Sequence, Type

import pandas as pd
from pydantic import BaseModel

from .agents import DocumentContext, ExtractionAgent, SchemaAgent
from .schema import FieldSpec
from .preprocess import PDFPreprocessor

logger = logging.getLogger(__name__)


@dataclass
class DocumentResult:
    document: Path
    status: Literal["ok", "error", "skipped"]
    data: dict[str, Any] | None = None
    error: str | None = None


class ExtractionOrchestrator:
    """
    Coordinates schema creation and per-document extraction.
    """

    def __init__(
        self,
        schema_agent: SchemaAgent,
        extraction_agent: ExtractionAgent,
        pdf_preprocessor: PDFPreprocessor | None = None,
    ):
        self.schema_agent = schema_agent
        self.extraction_agent = extraction_agent
        self.pdf_preprocessor = pdf_preprocessor or PDFPreprocessor()

    def _preprocess(self, file_path: Path) -> DocumentContext:
        """
        Basic preprocessing that handles PDFs; PPTX and others can be added later.
        """
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            return self.pdf_preprocessor.load(file_path)
        raise ValueError(f"Unsupported file type: {suffix}")

    def process(
        self,
        files: Sequence[Path],
        user_schema_instructions: str,
        *,
        percent_scale: str = "0-1",
        instructions: str = "Extract the requested fields from the document.",
    ) -> List[DocumentResult]:
        """
        Run schema generation once, then extract fields for each document.
        """
        try:
            logger.info("Running schema agent")
            field_specs: List[FieldSpec] = self.schema_agent.run(user_schema_instructions)
        except Exception as exc:
            logger.exception("Schema agent failed")
            return [
                DocumentResult(
                    document=Path(f),
                    status="error",
                    error=f"Schema agent error: {exc}",
                    data=None,
                )
                for f in files
            ]

        model: Type[BaseModel] = self.schema_agent.build_pydantic_model(
            field_specs, percent_scale=percent_scale
        )

        results: List[DocumentResult] = []
        for file_path in files:
            path = Path(file_path)
            logger.info("Preprocessing %s", path)
            context = self._preprocess(path)
            try:
                logger.info("Extracting fields for %s", path.name)
                record: BaseModel = self.extraction_agent.run(
                    model=model,
                    document=context,
                    instructions=instructions,
                )
                results.append(
                    DocumentResult(
                        document=path,
                        status="ok",
                        data=record.model_dump(),
                        error=None,
                    )
                )
            except Exception as exc:  # pragma: no cover - placeholder for future logging
                logger.exception("Extraction failed for %s", path.name)
                results.append(
                    DocumentResult(
                        document=path,
                        status="error",
                        error=str(exc),
                        data=None,
                    )
                )
        return results

    def to_dataframe(self, results: Sequence[DocumentResult]) -> pd.DataFrame:
        """
        Convert extraction results into a flat DataFrame.

        Columns: document_name, status, error, <fields...>
        """
        rows: List[dict[str, Any]] = []
        for res in results:
            row: dict[str, Any] = {
                "document_name": res.document.name,
                "status": res.status,
                "error": res.error,
            }
            if res.data:
                row.update(res.data)
            rows.append(row)
        return pd.DataFrame(rows)

    def to_excel(self, results: Sequence[DocumentResult], output_path: Path) -> None:
        """
        Write results to an Excel file with sheet 'extractions'.
        """
        df = self.to_dataframe(results)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Writing results to %s", output_path)
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="extractions", index=False)
