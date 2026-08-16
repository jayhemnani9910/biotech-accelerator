# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- NMA reported Cα-array indices as deposited residue numbers. `getResnums()` was
  never called, so the two agreed only for a gapless structure starting at index 0;
  on 6OIM "residues 117-119" meant 120-122. Regions now also break at numbering
  gaps and chain boundaries.
- Mutation cross-referencing compared those indices against residue positions
  parsed from abstracts, producing confident wet-lab directives from a mismatch.
  Mutations at residues absent from the structure are no longer called "stable".
- Structural data was flattened to markdown and regex-parsed back out, where a
  missed pattern returned `[]` — indistinguishable from "no hinges found".
  Downstream nodes read the typed NMA results directly.
- Potency classification did not recognise U+03BC GREEK SMALL LETTER MU, so
  micromolar values from ChEMBL were graded on the nanomolar scale — a weak 5 µM
  hit was reported as "highly potent (<10 nM)". Ranking now sorts on a common scale.
- `PUBMED_EMAIL`, `PUBMED_API_KEY` and `PDB_CACHE_DIR` were documented but read by
  nothing; the adapters now read them.
- The CLI and MCP server used separate serialisers that disagreed. Enums leaked
  Python internals and numpy arrays were stringified into elided reprs.
- A `date_to` with no `date_from` produced a PubMed filter with no `AND`, silently
  returning unfiltered results.
- Structured abstracts lost everything after the first section, including RESULTS
  where mutations are reported; titles truncated at the first inline markup tag.
- `chain_ids` was hardcoded empty; `StructureAnalysisResult.structure` was assigned
  `None` despite a non-Optional annotation.

### Changed
- Migrated to `mcp` 2.x (`MCPServer` replaces `FastMCP`). The server now reports
  its version to clients.
- Dropped ten declared-but-unimported dependencies (~3.8 GB of unused CUDA-enabled
  torch among them); install is 5.2 GB → 553 MB.
- PubMed responses parse via `defusedxml`; that parse runs on bytes off the network.
- `run_nma` omits the eigenvector matrix and reports its shape — payload 1.5 MB → 16 KB.
- Docker image installs non-editable and runs as a non-root user.
- Version is single-sourced from `biotech_accelerator/version.py`.

### Added
- `search_structures`, `cache_stats` and `clear_cache` MCP tools. The response
  cache previously had no way to be inspected or cleared.
- Test suite grown from 51 to 153, including coverage of the MCP protocol surface.

### Removed
- 17 unreferenced public symbols and two unused domain classes.
- The unused `config.Settings` tree, replaced by per-adapter environment reads.

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
