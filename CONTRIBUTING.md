# Contributing

Thanks for your interest in improving Biotech Research Accelerator.

## Dev setup

```bash
git clone https://github.com/jayhemnani9910/biotech-accelerator.git
cd biotech-accelerator
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and fill in required API keys (OpenAI / Groq) before running integration tests or the pipeline.

## Running tests

```bash
# Unit tests (no network, run in CI)
pytest

# Integration tests (hit live PubMed / PDB / UniProt / ChEMBL)
pytest -m integration
```

## Style

- Formatter + linter: [ruff](https://docs.astral.sh/ruff/) — config in `pyproject.toml`
- Python 3.10+, type hints encouraged, pydantic for data models
- Before pushing: `ruff check . && ruff format --check .`

## Pull requests

1. Fork and create a topic branch (`fix/…`, `feat/…`)
2. Keep PRs focused — one concern per PR
3. Update/add tests where it makes sense
4. Ensure CI is green
5. Reference any related issue in the PR body (`Fixes #N`)

## Reporting bugs / requesting features

Open an issue using the provided templates in `.github/ISSUE_TEMPLATE/`.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
