from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

import fitz  # PyMuPDF
from PIL import Image

from .agents import DocumentContext


@dataclass
class PDFPreprocessor:
    """
    Extracts text blocks and renders page images for a PDF.
    """

    max_pages: int | None = None
    dpi: int = 150

    def load(self, file_path: Path) -> DocumentContext:
        doc = fitz.open(file_path)
        text_blocks: List[str] = []
        images: List[Image.Image] = []

        for page_index in range(len(doc)):
            if self.max_pages is not None and page_index >= self.max_pages:
                break
            page = doc.load_page(page_index)
            text_blocks.append(page.get_text("text"))

            pix = page.get_pixmap(dpi=self.dpi)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)

        metadata = {
            "pages": len(doc),
            "file": file_path.name,
            "type": "pdf",
        }
        return DocumentContext(
            file_path=file_path,
            text_blocks=text_blocks,
            images=images,
            metadata=metadata,
        )
