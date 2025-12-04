# Vision Document Extraction Project

## Objective
- Build a tool that ingests a list of documents (initially PDF, then PPTX), accepts a user-defined list of values/fields to extract, and produces an Excel file with one row per document and one column per requested value (plus document name and status).

## Functional Requirements
- Accept multiple files per run; reject unsupported types with a clear message.
- Let users define extraction schema (field names, short descriptions/examples) at runtime.
- Use a vision-capable LLM so layout/visual context (tables, headers, signatures, embedded images) are considered.
- Return a single Excel workbook: sheet `extractions` with columns `[document_name, status, <fields...>]`.
- Capture and report per-document errors without aborting the batch.
- Log prompts/responses (with redaction options for PII/secrets) for troubleshooting.

## Out of Scope (for now)
- Fine-tuning or custom model training.
- Web UI; we start with CLI/SDK-style usage.
- Long-term storage of documents or outputs (process-in/place, then discard).
- OCR for scanned documents beyond what the chosen vision LLM provides; can be added later with Tesseract/Surya if needed.

## Architecture Overview
- **Ingestion**: Validate file types; normalize names; compute simple hashes; store in temp workspace.
- **Preprocessing**:
  - PDF: render pages to images and collect basic text spans for grounding (using PyMuPDF); fall back to text-only path for faster runs.
  - PPTX: parse slide structure; optionally convert to PDF then reuse PDF pipeline if LibreOffice is available; otherwise, extract text + slide thumbnails.
- **Prompting**: Build a consistent system/user prompt using the user-provided schema plus optional exemplars; include extracted text snippets and page thumbnails.
- **Schema handling**: Create a Pydantic model dynamically from user instructions (field names, descriptions, target types/enums); enforce normalization/validation and return per-field errors when parsing LLM output.
- **LLM Client**: Thin wrapper to call a vision model with retries, rate-limit/backoff, and audit logging; pluggable providers.
- **Orchestrator**: For each document, run preprocess -> prompt -> LLM call -> parse/validate response -> collect row data.
- **Output**: Build a DataFrame and write to Excel (`extractions` sheet) with the exact column order; include status/error message columns.
- **Tracing/Logging**: Structured logs to stdout and optional JSONL trace file for debugging.

## Proposed Dependencies (uv-managed; Python ≥3.13)
- **LLM client**: `openai` (or `litellm` for provider abstraction; supports OpenAI/Azure/Anthropic/Vertex). Default: OpenAI `gpt-4o` via `openai`/`litellm`.
- **Document handling**:
  - `pymupdf` (PyMuPDF) for PDF parsing and page-to-image rendering.
  - `python-pptx` for PPTX text/structure; optional external `libreoffice` CLI for PPTX→PDF when available.
  - `Pillow` for image handling.
- **Data & schema**: `pydantic` for typed request/response schemas and validation.
- **Output**: `pandas` + `openpyxl` for Excel writing.
- **CLI & UX**: `typer` + `rich` for a friendly CLI with progress and colored logs.
- **Reliability**: `tenacity` for retries with backoff.
- **Testing**: `pytest`, `pytest-mock`; fixtures under `tests/fixtures/` (small PDFs/PPTX).

## Configuration & Secrets
- Env vars: `LLM_PROVIDER` (`openai`/`azure-openai`/etc.), `LLM_MODEL` (e.g., `gpt-4o`), `LLM_API_KEY`, `LLM_API_BASE` (if needed), `LOG_LEVEL`.
- CLI flags for toggles: `--text-only` (skip images), `--max-pages`, `--concurrency`, `--output`.
- Keep redaction toggle for prompt/response logging (`--redact-prompts`).

## Delivery Plan (initial milestones)
1) Scaffold package: `pdf_context_extraction/` with modules `ingest.py`, `preprocess.py`, `prompt.py`, `llm.py`, `extract.py`, `output.py`, plus `tests/`.
2) Add deps via `uv add`: `litellm`, `pymupdf`, `python-pptx`, `Pillow`, `pydantic`, `pandas`, `openpyxl`, `typer`, `rich`, `tenacity`; add test deps.
3) Implement CLI entry (`uv run python -m pdf_context_extraction`): accepts files + schema JSON/YAML path and writes Excel.
4) Build PDF pipeline: render pages, craft prompt, call vision model, parse JSON response into Pydantic model, write Excel.
5) Add PPTX support: text-first, and PDF-conversion path when LibreOffice present; extend tests/fixtures.
6) Hardening: error handling, logging/redaction, concurrency/rate limits, sample assets, regression tests.

## Schema Agent Decisions
- Allowed field types: `str`, `bool`, `int`, `float`, `decimal`, `date` (enforce `YYYY-MM-DD`), `datetime` (ISO 8601), `percent` (normalize to float 0–1 unless requested otherwise), `enum` (strict), `money` (normalized to `amount` Decimal + `currency` ISO 4217).
- Enum handling: strict; unknown values trigger validation errors and are reported per-field.
- Money handling: split into `amount` (Decimal) + `currency` (ISO 4217); currency inferred from symbol/name when possible, else error.
- Prompting: user supplies field specs (name + description + optional examples/type hints). LLM maps to allowed types and returns JSON; we build a Pydantic model via `pydantic.create_model` with our type mappings—no LLM-generated code.
- Validation: Pydantic enforces types; per-field errors captured and surfaced in Excel status/error columns.

### Schema Agent Prompt Plan
- System message establishes role: “You map user field requests to a strict JSON schema using these allowed types only: ...”
- Input from user: list of fields with names/descriptions/examples/hints; global options (percent scale, currency locale).
- Output format: JSON with fields: `name`, `description`, `type` (one of allowed), `enum_values` (when type is enum), `money` config (optional currency hints), `required` (bool).
- Guardrails: refuse to invent new types; reject unsafe instructions; ensure names are safe (alphanumerics/underscores).
- Optional confirmation step: echo schema back to user for approval in interactive mode.

### Pydantic Schema Builder (planned API)
- Module: `pdf_context_extraction/schema.py`.
- Function: `build_model(field_specs: list[FieldSpec], percent_scale: Literal["0-1","0-100"]="0-1") -> type[BaseModel]`.
- `FieldSpec` dataclass: `name`, `description`, `type`, `enum_values` (optional), `required` (bool), `examples` (list), `currency_hint` (optional).
- Internals: map allowed types to Python types/validators; for `money`, create a nested model `{amount: Decimal, currency: constr(to_upper=True, min_length=3, max_length=3)}`; for `percent`, normalize to 0–1 float when scale is `0-100`.
- Validation errors are captured per field to annotate Excel output.

### Next Implementation Steps
- Add `schema.py` with `FieldSpec` and `build_model`.
- Draft the schema-agent prompt template and a small helper to call it (pure text, no code generation).
- Add a unit test to verify `build_model` type/validation behavior (dates, enums strictness, percent normalization, money split).

## End-to-End Flow (pydanticAI Agents)
- **Schema Agent (LLM)**: Takes user input (field names/descriptions/examples/type hints) → returns normalized `FieldSpec` list constrained to allowed types/enums → we build a Pydantic model via `build_model`.
- **Extraction Agent (pydanticAI)**: For each document, constructs context (text snippets + page thumbnails/metadata) and uses the generated Pydantic model as the output schema. The agent:
  - Receives the model class and a task prompt describing the document and expected fields.
  - Calls OpenAI vision (`gpt-4o`) with images/text to fill the model.
  - Parses with pydanticAI into the Pydantic model; validation errors are captured per field.
- **Orchestrator**:
  - Inputs: list of file paths + user field spec input (YAML/JSON/CLI).
  - Steps: run Schema Agent → build model → iterate documents → preprocess (PDF/PPTX) → call Extraction Agent → collect rows.
  - Outputs: Excel (`extractions` sheet) with columns `[document_name, status, error, <fields...>]`, plus optional JSONL trace of prompts/responses.
- **Error handling**: Per-document isolation; validation errors stored alongside outputs; failed docs keep their errors in the Excel status column.

## Open Questions / Choices
- PPTX handling: Is installing `libreoffice` acceptable for PPTX→PDF rendering, or should we stay text-only for slides initially?
- Expected field types: strings only, or typed (dates/numbers) with validation/normalization?
- Typical document size and page counts? Influences paging strategy and cost controls.
- Should we store traces (prompts/responses) on disk by default, or only when `--trace` is set?
