# Repository Guidelines

## Project Structure & Module Organization
- Root contains the entry point `main.py` and project metadata in `pyproject.toml`.
- Add new modules under a `pdf_context_extraction/` package to keep imports clean; mirror that layout in `tests/` for parity.
- Keep assets (sample PDFs, fixtures) in `assets/` or `tests/fixtures/` with small, shareable files only.

## Package & Dependency Management (uv only)
- Create/refresh the env: `uv venv .venv && source .venv/bin/activate` (Windows: `.venv\\Scripts\\activate`).
- Install deps from `pyproject.toml`: `uv sync` (keeps lock in sync).
- Add or remove deps: `uv add package-name` / `uv remove package-name`; use extras as needed (`uv add pdfminer.six`).
- Run commands in the env without manual activation: `uv run python main.py`, `uv run pytest -q`.

## Build, Test, and Development Commands
- Run the app: `uv run python main.py` (replace with module entry points as the codebase grows).
- Run tests: `uv run pytest -q` from the repo root.

## Coding Style & Naming Conventions
- Target Python `>=3.13` (per `pyproject.toml`); use 4-space indentation and PEP 8 defaults.
- Prefer typed function signatures for new code; keep names descriptive (`extract_context`, `parse_metadata`).
- Keep modules focused: extraction logic in `pdf_context_extraction/extract.py`, I/O helpers in `pdf_context_extraction/io.py`, etc.
- If you add formatters/linters (e.g., `ruff`, `black`), commit their config and run them before publishing changes.

## Testing Guidelines
- Use `pytest`; place tests in `tests/` mirroring package paths (e.g., `tests/test_extract.py`).
- Aim for fast, isolated tests; use small fixture PDFs under `tests/fixtures/`.
- Name tests with behavior intent (`test_extracts_text_blocks`, `test_handles_empty_page`).
- Add regression tests alongside bug fixes to prevent repeats.

## Commit & Pull Request Guidelines
- Use Conventional Commits: `<type>(<scope>): <subject>` in imperative, 72-char subject limit; common types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `style`.
- Keep one logical change per commit; avoid mixing refactors with feature work without clear rationale.
- PRs should explain the problem, the approach, and any trade-offs; link issues when available.
- Include testing notes in PRs (`pytest -q`, manual checks) and call out known gaps or follow-ups.
