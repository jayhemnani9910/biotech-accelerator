# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-15

Initial release.

### Added
- LangGraph pipeline orchestrating parse → resolve → literature → structure → drug → synthesis nodes.
- PubMed adapter with query construction, mutation extraction, relevance scoring, rate limiting, and retry.
- RCSB PDB adapter with structure fetching and caching.
- UniProt adapter for protein name → UniProt ID → PDB mapping.
- ChEMBL adapter for bioactivity search and potency classification.
- ProDy ANM/GNM wrapper for flexibility profiling and hinge residue identification.
- Synthesis node cross-referencing literature mutations with structural flexibility.
- Experiment suggester producing actionable next-step recommendations.
- 24-hour response cache across API adapters.
- `BaseAdapter` centralizing HTTP client management.
- Dockerfile for reproducible installs (avoids native ProDy/RDKit build issues).
- GitHub Pages interactive demo.

[0.1.0]: https://github.com/jayhemnani9910/biotech-accelerator/releases/tag/v0.1.0
