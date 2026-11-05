# Contributing

I try to reply to issues within a few days.

## Dev setup

```bash
git clone https://github.com/jayhemnani9910/biotech-accelerator.git
cd biotech-accelerator
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

No API keys are needed. The optional settings are in `.env.example`.

## Tests

```bash
pytest                 # unit tests, no network, run in CI
pytest -m integration  # hits live PubMed, PDB, UniProt and ChEMBL
```

## Style

Ruff handles lint and formatting, mypy handles types. CI runs all of these on Python 3.10, 3.11 and 3.12, so run them before you push:

```bash
ruff check .
ruff format --check .
mypy biotech_accelerator
```

Type hints on new code, dataclasses for data models.

## Branches and pull requests

1. Fork and branch from `main` (`fix/...`, `feat/...`).
2. One concern per PR.
3. Add or update tests for behaviour changes.
4. Run the integration tests if you touched an adapter.
5. Link the issue in the PR body (`Fixes #N`).

## Bugs and ideas

Open an issue with the bug or feature template. For a bug, include the exact query or command, what you expected, what you got, and your version and OS. Results that look scientifically wrong count as bugs.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
