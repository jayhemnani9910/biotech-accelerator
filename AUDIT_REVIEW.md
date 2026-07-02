# Audit Review — biotech-accelerator

**Audited commit:** `b68fd0e` (branch `main`)
**Repo:** `jayhemnani9910/biotech-accelerator`
**Scope:** Full-folder audit — inventory every file, verify behaviour by running it
(static checks, unit + integration tests, live API calls, NMA, LangGraph pipeline,
MCP server), document findings, then fix confirmed defects on branch `audit-fixes`.

> This document is written by the audit and does not necessarily reflect the
> original authors' intent. "Verified" means I ran it and observed the stated
> behaviour; "as designed" means the code matches its own documentation.

---

## 1. Executive summary

The project is a **deterministic** (non-LLM) multi-agent pipeline for molecular-biology
research: it parses a query, resolves proteins via UniProt, searches PubMed, fetches PDB
structures and runs ProDy Normal Mode Analysis, searches ChEMBL for bioactivity, and
synthesises a markdown report with experiment suggestions. It ships two entry points
(`biotech` CLI, `biotech-mcp` MCP server) plus a Python API.

Overall the codebase is **in good shape**: clean hexagonal (ports/adapters) architecture,
typed error hierarchy, retry/backoff, disk caching, and a real test suite.

- **Static analysis:** all 22 modules import; `ruff check`, `ruff format --check`, and
  `mypy` (32 files) all pass with zero findings.
- **Tests:** **48 passed, 6 deselected** (integration tests) once a sandbox-specific
  proxy quirk is accounted for (see F1 — *not* a project defect). Integration tests pass
  against live APIs.
- **Live behaviour:** PDB, UniProt, PubMed adapters, ProDy NMA, the full LangGraph
  pipeline, and all 11 MCP tools work end-to-end.

**One functional defect found (HIGH): ChEMBL target resolution** returns empty results
for common target names ("EGFR", etc.) because it picks the first raw search hit — often a
protein–protein-interaction *complex* with ~0 activities — instead of the canonical single
protein. This silently breaks the headline "Find EGFR inhibitors" feature. Fixed in
`179b555` on `audit-fixes` and verified end-to-end (§6).

The remaining findings are documentation/config drift and minor data-fidelity issues.

### Findings at a glance

| ID | Severity | Area | One-line |
|----|----------|------|----------|
| F1 | Not a defect (env) | tests | 25 test "failures" are a sandbox SOCKS-proxy artifact, not project bugs |
| F2 | **HIGH** | chembl_adapter | Target lookup picks a PPI complex over the canonical single protein → 0 activities |
| F3 | MEDIUM | .env.example | Advertises `LLM_*` / `TAVILY_*` / `MAX_RECURSION_*` vars that **no code reads** (contradicts README) |
| F4 | LOW | chembl_adapter | `get_bioactivity` puts `target_organism` into the `target_uniprot` field |
| F5 | LOW | pdb_adapter | `PDBStructure.chain_ids` is always `[]` (metadata query never populates it) |
| F6 | LOW | tests | Integration tests `return True/False` instead of asserting → pytest return-value warnings |
| F7 | LOW | .claude/commands | Slash commands hardcode `/usr/bin/python3` (fails where system python lacks the package) |
| F8 | INFO | nma_wrapper | Dead `sys.path` shim for a `~/jh-core/...` path that never exists (harmless, misleading) |

---

## 2. File inventory

77 tracked files. Source is `biotech_accelerator/` (~4,215 LOC across 32 `.py` files).

### Source package (`biotech_accelerator/`)

| File | LOC | Purpose | Status |
|------|-----|---------|--------|
| `__init__.py` | 31 | Package exports (`run_research`, adapters, errors) | OK |
| `main.py` | 185 | `biotech` CLI: full-pipeline & `--pdb` modes, `--json` output | OK (verified) |
| `mcp_server.py` | 260 | `biotech-mcp` FastMCP server, 11 tools | OK (verified) |
| `config/settings.py` | 80 | Dataclass settings; reads `PUBMED_EMAIL`, `PUBMED_API_KEY`, `PDB_CACHE_DIR` | OK |
| `domain/protein_models.py` | 110 | `ProteinInfo`, `PDBStructure`, `NMAResult`, `MutationPrediction`, `FlexibilityMetrics` | OK |
| `domain/compound_models.py` | 41 | `CompoundInfo` (Lipinski), `BindingPrediction` | OK |
| `ports/structure.py` | 9 | `StructureNotFoundError` | OK |
| `ports/sequence.py` | 29 | `SequenceInfo`, `SequenceNotFoundError` | OK |
| `ports/literature.py` | 36 | `Citation`, `LiteratureSearchResult` | OK |
| `ports/compound.py` | 19 | `BioactivityData` | OK |
| `adapters/base.py` | 149 | `BaseAdapter`: async httpx, retry/backoff, typed errors | OK |
| `adapters/pdb_adapter.py` | 198 | RCSB fetch + GraphQL metadata + search | OK; see F5 |
| `adapters/pubmed_adapter.py` | 201 | NCBI E-utilities, rate limit, XML parse | OK (verified) |
| `adapters/uniprot_adapter.py` | 119 | UniProt REST: sequence, search, PDB mapping | OK (verified) |
| `adapters/chembl_adapter.py` | 246 | ChEMBL: compound, target, bioactivity | **F2 (HIGH)**, F4 |
| `analysis/nma_wrapper.py` | 198 | ProDy ANM wrapper → `NMAResult` | OK (verified); see F8 |
| `utils/cache.py` | 203 | Disk cache, atomic writes, TTL, legacy-format read | OK (verified) |
| `agents/nodes/structure_analyst.py` | 236 | Fetch + NMA + summary | OK (verified) |
| `agents/nodes/bio_literature.py` | 262 | PubMed search + relevance + mutation flags | OK (verified) |
| `agents/nodes/drug_binding.py` | 329 | ChEMBL search + potency classify | OK logic; blocked by F2 upstream |
| `agents/nodes/experiment_suggester.py` | 313 | Heuristic experiment suggestions | OK |
| `agents/nodes/synthesis.py` | 425 | Mutation extraction + cross-ref + report | OK (verified) |
| `graph/biotech_graph.py` | 448 | LangGraph assembly, `run_research`, query parsing | OK (verified) |

### Tests (`tests/`, 772 LOC)

| File | Purpose | Result |
|------|---------|--------|
| `test_unit.py` | Pure-function logic (parse, potency, targets, mutations) | pass |
| `test_adapters.py` | Error-path via `httpx.MockTransport` + cache | pass |
| `test_basic.py` | Domain-model / import smoke tests | pass |
| `test_mcp_server.py` | MCP tool registration / serialization | pass |
| `test_full_pipeline.py` | Live end-to-end (marked `integration`) | pass live; see F6 |

### Docs / config / CI

`README.md`, `docs/api.md`, `docs/index.html` + `docs/js/*` + `docs/diagrams/*` (demo site),
`CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`,
`pyproject.toml`, `uv.lock`, `Dockerfile`, `.github/workflows/ci.yml`,
`.github/ISSUE_TEMPLATE/*`, `.mcp.json`, `.env.example` (**F3**),
`.claude/commands/*.md` (**F7**), `example_walkthrough.py`, `examples/run_examples.py`,
`chats.md` (stray scratch note).

---

## 3. Verification performed

- **Import smoke-test:** all 22 modules import cleanly.
- **Static:** `ruff check .` → *All checks passed*; `ruff format --check .` → *40 files already
  formatted*; `mypy` → *no issues in 32 source files*.
- **Unit/error tests:** `pytest -q` → 48 passed, 6 deselected (after F1 proxy fix).
- **Live adapters** (known inputs):
  - PDB `1LYZ`: resolution 2.0 Å, X-ray, 129 residues, file cached. Search "lysozyme" → 3 hits.
  - UniProt `P00698`: "Lysozyme C", *Gallus gallus*, gene LYZ, 147 aa, 1306 PDB xrefs, function present.
  - PubMed `search_by_protein("lysozyme", topic="mutation OR stability")`: returns citations with PMIDs/years.
  - ChEMBL `get_compound("CHEMBL25")` → ASPIRIN, MW 180.16, logP 1.31. **`search_by_target("EGFR")` → 0** (F2).
- **NMA:** ProDy ANM on `1LYZ` (20 modes): mean fluctuation, 4 flexible regions, 13 hinge residues, vib. entropy computed.
- **Graph:** `run_research("Analyze flexibility of PDB 1LYZ")` → completes, 3.2 KB report.
  `run_research("Find EGFR inhibitors")` → completes but `drug_insights=0` (F2 through the full pipeline).
- **MCP:** 11 tools registered (names match README exactly); `extract_mutations`,
  `cross_reference_mutations`, `fetch_structure`, `get_compound` all verified correct.

---

## 4. Findings (detail)

### F1 — Test "failures" are a sandbox proxy artifact — NOT A DEFECT
Running `pytest` in the audit sandbox first showed **25 failed**, all with
`ImportError: Using SOCKS proxy, but the 'socksio' package is not installed`. Root cause:
the sandbox exports `ALL_PROXY=socks5h://…`, and `httpx.AsyncClient()` trusts environment
proxies by default, so every adapter construction tried to build a SOCKS transport.
Clearing `ALL_PROXY` (or installing `httpx[socks]`) yields **48 passed, 6 deselected**.
The project's own CI has no SOCKS proxy, so this never occurs there. **No code change
warranted** — documented here so the discrepancy isn't mistaken for a bug.

### F2 — ChEMBL target lookup returns a PPI complex instead of the canonical protein — **HIGH**
`ChEMBLAdapter._find_target()` does `target/search.json?q=<name>` and returns `targets[0]`.
For "EGFR", ChEMBL ranks by text score and returns, in order:

```
CHEMBL4523747  PROTEIN-PROTEIN INTERACTION  Homo sapiens  score 17  'EGFR/PPP1CA'   ← picked
CHEMBL5465557  PROTEIN-PROTEIN INTERACTION  Homo sapiens  score 17  'CCN2-EGFR'
CHEMBL3608     SINGLE PROTEIN               Mus musculus  score 15
CHEMBL203      SINGLE PROTEIN               Homo sapiens  score 11  'Epidermal growth factor receptor'  ← wanted
```

The picked complex `CHEMBL4523747` has ~0 activities; the canonical human EGFR `CHEMBL203`
has **26,600 IC50 records**. Result: `search_by_target`, `get_approved_drugs_for_target`,
and the entire drug-discovery node return empty for common target names — the headline
"Find EGFR inhibitors" feature silently produces nothing.
**Fix:** prefer `SINGLE PROTEIN` targets (and, where possible, *Homo sapiens*) over other
target types when selecting from search results. Fixed in `179b555` (see §6).

### F3 — `.env.example` advertises variables no code reads — MEDIUM (doc/config drift)
`.env.example` lists `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `SEARCH_PROVIDER`,
`TAVILY_API_KEY`, `MAX_RECURSION_DEPTH`, `MAX_INVESTIGATIONS_PER_EDGE`, `OUTPUT_DIR`,
`LOG_LEVEL`. A full grep of the package shows the code reads **only** `PUBMED_EMAIL`,
`PUBMED_API_KEY`, `PDB_CACHE_DIR`. There is no LLM/Tavily/OpenAI/Groq client anywhere; the
MCP server docstring explicitly says *"no embedded LLM calls; reasoning happens in the
client."* The README's own Configuration section is correct ("does not require an LLM API
key"), so `.env.example` **contradicts the README** and will mislead users into setting keys
that do nothing. **Fix:** rewrite `.env.example` to list only the variables the code
consumes, with a note that LLM-powered nodes are a future iteration. Fixed in `fb97406` (see §6).

### F4 — `get_bioactivity` mislabels organism as UniProt accession — LOW (data fidelity)
In `ChEMBLAdapter.get_bioactivity`, `BioactivityData.target_uniprot=act.get("target_organism")`
— the organism string is stored in the UniProt-ID field. (The sibling `search_by_target`
correctly derives it from `target_components[…].accession`.) **Fix:** stop populating
`target_uniprot` from `target_organism` (set `None`; the activity payload has no accession).
Fixed in `56953f8` (see §6).

### F5 — `PDBStructure.chain_ids` is always empty — LOW
`_fetch_metadata` hardcodes `"chain_ids": []`; the GraphQL query never requests chain/asym
identifiers, so `PDBStructure.chain_ids` is always `[]`. Nothing downstream depends on it,
so impact is cosmetic. **Documented, not fixed** (would require extending the GraphQL query
and validating a new response shape — out of scope for a defect-fix pass). Left as a known
limitation.

### F6 — Integration tests use `return` instead of `assert` — LOW
`tests/test_full_pipeline.py` functions `return True/False`. Pytest treats a non-None return
as a warning (`PytestReturnNotNoneWarning`) and cannot fail on `return False`. They still
exercise the live pipeline but don't assert outcomes. **Documented, not changed** to avoid
altering the authors' intended manual-inspection harness; noted as a hardening opportunity.

### F7 — Slash commands hardcode `/usr/bin/python3` — LOW
`.claude/commands/{research,find-mutations,analyze-pdb}.md` invoke
`/usr/bin/python3 -m biotech_accelerator.main …`. On a machine where the package is installed
in a venv (the documented install path) but not in system Python, these fail with
`ModuleNotFoundError`. **Documented, not changed** (environment-specific; the CLI itself and
`.mcp.json`'s `uv run` path both work). Recommend switching to `uv run biotech …` or
`python3 -m …` against the active interpreter.

### F8 — Dead `sys.path` shim in nma_wrapper — INFO
`nma_wrapper.py` inserts `~/jh-core/projects/nobel_dataintelligence` onto `sys.path` if it
exists. That path does not exist in this checkout and NMA uses ProDy directly, so the shim is
dead code. Harmless but misleading (implies an external dependency that isn't used).
**Documented, not changed.**

---

## 5. Note on the requested "wire in DeepSeek + Tavily" deliverable

The audit brief asks for an end-to-end run "with the DeepSeek LLM and Tavily search wired
in." **The current codebase has no LLM or web-search integration point** — every node is
deterministic regex/heuristics over PubMed/PDB/UniProt/ChEMBL, and this matches the README's
stated design. There is therefore nothing in the existing architecture that a DeepSeek key or
Tavily key plugs into; adding one would be a *feature addition*, not a defect fix, and would
change the project's documented "deterministic, no API key required" contract.

This audit's fix pass keeps that contract and instead **corrects the misleading
`.env.example`** (F3). The end-to-end verification below is run with the real external science
APIs (the pipeline's actual data sources). See §6 for the DeepSeek/Tavily decision.

---

## 6. Fix status & end-to-end results

### Fixes applied on `audit-fixes` (branched from `b68fd0e`)

| ID | Severity | Commit | Change |
|----|----------|--------|--------|
| F2 | HIGH | `179b555` | `_select_best_target` prefers SINGLE PROTEIN + Homo sapiens; widen search to 25 hits. + 3 unit tests. |
| F4 | LOW | `56953f8` | `get_bioactivity` no longer stores `target_organism` in `target_uniprot` (set `None`). |
| F3 | MEDIUM | `fb97406` | `.env.example` rewritten to list only the vars the code reads. |
| F9 | LOW | `01fe432` | `test_basic.py::test_nma_analysis` made a self-contained pytest test (was erroring as a missing-fixture on integration collection). |

**F9** was discovered during the post-fix integration run (it did not appear in the
default suite because it is `integration`-marked). Added here for completeness.

**Documented, not fixed** (out of scope / environment-specific, see §4): F5 (empty
`chain_ids`), F6 (integration tests use `return` not `assert`), F7 (`.claude/commands`
hardcode `/usr/bin/python3`), F8 (dead `sys.path` shim).

**DeepSeek + Tavily:** per the maintainer's decision, the deterministic design is kept and
no LLM/web-search layer was added (there is no integration point in the current
architecture; §5). The provided keys are unused. `.env.example` now reflects this honestly.

### Verification after fixes

- **Static:** `ruff check` ✅ · `ruff format --check` ✅ (40 files) · `mypy` ✅ (32 files).
- **Unit/error suite:** **51 passed, 6 deselected** (was 48; +3 F2 regression tests).
- **Integration suite (live APIs):** **6 passed, 51 deselected** (was 5 passed + 1 error; F9 fixed).
- **F2 proven end-to-end** — "Find EGFR inhibitors":
  - Pre-fix: `drug_insights = 0`, `target_compounds = 0`.
  - Post-fix: `drug_insights = 15`, `target_compounds = 10`, 4.6 KB report; logs confirm the
    activity query now hits `target_chembl_id=CHEMBL203` (canonical human EGFR).

### End-to-end runs (the shipped product)

- **CLI — structure mode:** `python -m biotech_accelerator.main --pdb 1LYZ --json` →
  100 NMA modes, mean fluctuation 0.145 Å², no error.
- **CLI — full pipeline:** `python -m biotech_accelerator.main "Find EGFR inhibitors" --json` →
  phase `done`, 15 live PubMed papers, ChEMBL drug analysis populated, 4.6 KB markdown report.
- **MCP server:** driving the FastMCP tool interface directly —
  `fetch_structure("1LYZ")`, `search_compounds_by_target("EGFR", "IC50")` (3 results),
  and `run_research("Find EGFR inhibitors")` (report generated) all succeed; all 11 tools
  are registered and match the README.

> **Sandbox note (not a project issue):** these runs require dropping the audit sandbox's
> `ALL_PROXY=socks5h://…` so `httpx` uses the http-scheme proxy (no `socksio` needed). On a
> normal machine / the project's CI there is no SOCKS proxy and no such step is needed.

