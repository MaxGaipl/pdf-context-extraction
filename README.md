# PDF Context Extraction (Vision LLM)

Tooling scaffold to extract structured fields from PDFs using a vision-capable LLM (OpenAI gpt-4o) and save results to Excel.

## Prerequisites
- Python >= 3.13
- OpenAI API key available as `OPENAI_API_KEY` (and `OPENAI_BASE_URL` if using a custom endpoint).
- `uv` for dependency/env management.

## Setup
```bash
uv venv .venv
source .venv/bin/activate
uv sync
```

## Usage (CLI)
Currently PDF-only; PPTX and others are not yet supported.

```bash
uv run python main.py \
  --schema "Extract invoice_number (string), invoice_date (date), total_amount (money), status (enum: Paid, Open)" \
  --output outputs/extractions.xlsx \
  docs/sample.pdf
```

Flags:
- `--schema/-s`: user instructions describing fields to extract (free text; a schema agent normalizes this to allowed types).
- `--percent-scale`: percent normalization (`0-1` default or `0-100`).
- `--output/-o`: Excel path (a `.log` is written alongside).
- `--log-level`: logging verbosity (`DEBUG/INFO/WARNING/ERROR`).

Output:
- Excel sheet `extractions` with columns `document_name`, `status`, `error`, and one column per extracted field.
- Log file next to the Excel output (same stem, `.log` extension).

## Sample schema + fixture
- Sample schema: `Extract invoice_number (string), invoice_date (date), total_amount (money), status (enum: Paid, Open)`
- Sample fixture PDF: `tests/fixtures/sample_invoice.pdf`

Example:
```bash
uv run python main.py \
  --schema "Extract invoice_number (string), invoice_date (date), total_amount (money), status (enum: Paid, Open)" \
  --output outputs/extractions.xlsx \
  tests/fixtures/sample_invoice.pdf
```

## How it works (current state)
- A schema agent (OpenAI via pydanticAI) turns `--schema` text into a validated Pydantic model (allowed types: str, bool, int, float, decimal, date, datetime, percent, enum, money).
- PDF preprocessing renders pages (PyMuPDF) to text + images.
- An extraction agent (OpenAI vision via pydanticAI) uses the model to return structured data per document.
- Results are combined and written to Excel; per-document errors are captured.

## Roadmap
- Add PPTX support.
- Per-field error surfacing in Excel.
- Tracing/log redaction toggles.
- Tests with mocked OpenAI calls and preprocessing fixtures.
