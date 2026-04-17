# API Reference

Public surface of the four data-source adapters. All methods are `async` unless noted and return dataclasses from `biotech_accelerator.ports.*` or `biotech_accelerator.domain.*`.

## `PDBAdapter` — `biotech_accelerator.adapters.pdb_adapter`

RCSB Protein Data Bank client. Cached downloads under `~/.biotech-accelerator/pdb_cache/` by default.

| Method | Signature | Returns |
|--------|-----------|---------|
| `fetch_structure` | `(pdb_id: str) -> PDBStructure` | Full structure + metadata (resolution, method, residue count) |
| `get_structure_file` | `(pdb_id: str) -> Path` | Local path to `.pdb` file; downloads + caches if missing |
| `search_structures` | `(query: str, max_results: int = 10, resolution_cutoff: Optional[float] = 2.5) -> list[ProteinInfo]` | Full-text search against RCSB |
| `get_cache_dir` | `() -> Path` *(sync)* | Cache directory path |
| `close` | `() -> None` | Close the underlying httpx client |

Raises `StructureNotFoundError` on 404, `ValueError` on invalid PDB ID format.

## `PubMedAdapter` — `biotech_accelerator.adapters.pubmed_adapter`

NCBI E-utilities client with rate limiting + retry with exponential backoff.

| Method | Signature | Returns |
|--------|-----------|---------|
| `search` | `(query: str, max_results: int = 20, date_from: Optional[date] = None, date_to: Optional[date] = None) -> LiteratureSearchResult` | Full-text PubMed search with date filter |
| `search_by_protein` | `(protein_name: str, topic: Optional[str] = None, max_results: int = 20) -> LiteratureSearchResult` | Protein-scoped search over title/abstract; `topic` may contain ` OR ` |
| `get_paper` | `(identifier: str) -> Citation` | Fetch by PMID or DOI (DOI detected by `10.` prefix) |
| `close` | `() -> None` | Close the underlying httpx client |

Set `PUBMED_EMAIL` to avoid rate-limit throttling.

## `UniProtAdapter` — `biotech_accelerator.adapters.uniprot_adapter`

UniProt REST client. No API key required.

| Method | Signature | Returns |
|--------|-----------|---------|
| `get_sequence` | `(uniprot_id: str) -> SequenceInfo` | Name, sequence, organism, gene, function, cross-referenced PDB IDs |
| `search_sequences` | `(query: str, organism: Optional[str] = None, max_results: int = 10) -> list[SequenceInfo]` | Free-text search; optional organism filter |
| `get_pdb_mapping` | `(uniprot_id: str) -> list[str]` | PDB IDs mapped to a UniProt accession (empty list if not found) |
| `close` | `() -> None` | Close the underlying httpx client |

Raises `SequenceNotFoundError` from `get_sequence` on missing entries.

## `ChEMBLAdapter` — `biotech_accelerator.adapters.chembl_adapter`

ChEMBL bioactivity client. Target lookup is cached for 24h.

| Method | Signature | Returns |
|--------|-----------|---------|
| `get_compound` | `(identifier: str) -> CompoundInfo` | Resolves ChEMBL ID or compound name to full record |
| `search_by_target` | `(target_name: str, activity_type: Optional[str] = None, max_results: int = 20) -> list[BioactivityData]` | IC50/Ki/Kd/EC50 activities sorted by potency; `activity_type` restricts type |
| `get_bioactivity` | `(compound_id: str, target: Optional[str] = None) -> list[BioactivityData]` | All activities for a compound, optionally scoped to a target |
| `search_similar` | `(smiles: str, similarity_threshold: float = 0.7, max_results: int = 20) -> list[CompoundInfo]` | Structural similarity search |
| `get_approved_drugs_for_target` | `(target_name: str, max_results: int = 10) -> list[CompoundInfo]` | Approved drugs targeting a protein |
| `close` | `() -> None` | Close the underlying httpx client |

Activity values are returned in their original units; `DrugBindingAgent._classify_potency` normalizes across nM/µM/pM.

## Lifecycle

All adapters subclass `BaseAdapter` and support async context management:

```python
async with PubMedAdapter() as pubmed:
    result = await pubmed.search_by_protein("lysozyme", topic="mutation")
```

Without `async with`, call `await adapter.close()` when done.

## Agents

Agents are callables returning graph-state fragments. See `biotech_accelerator.agents.nodes.*` for:

- `StructureAnalystAgent` — PDB fetch + ProDy ANM/GNM flexibility analysis
- `BioLiteratureAgent` — PubMed search + mutation extraction
- `DrugBindingAgent` — ChEMBL target lookup + potency classification
- `SynthesisAgent` — cross-reference literature mutations with structural flexibility

Entry point for the full pipeline: `biotech_accelerator.graph.biotech_graph.run_research(query: str) -> dict`.
