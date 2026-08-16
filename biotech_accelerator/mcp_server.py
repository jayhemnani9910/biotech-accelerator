"""MCP server exposing the biotech pipeline as tools for coding agents.

Run with: `biotech-mcp` (entry point) or `python -m biotech_accelerator.mcp_server`.

Designed to be consumed by Claude Code (or any MCP-compatible client). Each
tool is a thin, composable wrapper over the existing adapters and agents —
no embedded LLM calls; reasoning happens in the client.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Optional

import numpy as np
from mcp.server.mcpserver import MCPServer

from .adapters.chembl_adapter import ChEMBLAdapter, CompoundNotFoundError
from .adapters.pdb_adapter import PDBAdapter
from .adapters.pubmed_adapter import PubMedAdapter
from .adapters.uniprot_adapter import UniProtAdapter
from .agents.nodes.structure_analyst import StructureAnalystAgent
from .agents.nodes.synthesis import SynthesisAgent
from .graph.biotech_graph import run_research as run_research_pipeline
from .ports.literature import Citation
from .ports.sequence import SequenceNotFoundError
from .ports.structure import StructureNotFoundError
from .utils.cache import get_cache
from .utils.serialization import to_jsonable as _serialize
from .version import __version__

logger = logging.getLogger(__name__)

# --- lazy adapter cache (one instance per process) -------------------------


_adapters: dict[str, Any] = {}


def _adapter(key: str, factory):
    if key not in _adapters:
        _adapters[key] = factory()
    return _adapters[key]


@asynccontextmanager
async def _lifespan(server: MCPServer) -> AsyncIterator[None]:
    """Close the cached adapters when the server shuts down.

    Each adapter holds an httpx.AsyncClient that nothing was closing. Cleanup is
    best-effort: shutdown is exactly when a connection is most likely to be gone
    already, and one adapter failing must not strand the rest.
    """
    try:
        yield
    finally:
        for key, adapter in list(_adapters.items()):
            close = getattr(adapter, "close", None)
            if close is None:
                continue
            try:
                await close()
            except Exception as e:  # noqa: BLE001 - best-effort shutdown
                logger.warning(f"Failed to close {key} adapter: {e}")
        _adapters.clear()


mcp = MCPServer("biotech-accelerator", version=__version__, lifespan=_lifespan)


# --- Literature ------------------------------------------------------------


@mcp.tool()
async def search_literature(
    query: str,
    max_results: int = 20,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict:
    """Search PubMed for scientific literature.

    Returns a list of citations with PMID, title, authors, journal, year,
    abstract, and URL. Dates may be provided as ISO strings (YYYY-MM-DD).
    """
    from datetime import date as _date

    adapter: PubMedAdapter = _adapter("pubmed", PubMedAdapter)
    df = _date.fromisoformat(date_from) if date_from else None
    dt = _date.fromisoformat(date_to) if date_to else None
    result = await adapter.search(query, max_results=max_results, date_from=df, date_to=dt)
    return _serialize(result)


@mcp.tool()
async def search_literature_by_protein(
    protein_name: str,
    topic: Optional[str] = None,
    max_results: int = 20,
) -> dict:
    """Search PubMed for papers about a specific protein, optionally filtered by topic."""
    adapter: PubMedAdapter = _adapter("pubmed", PubMedAdapter)
    result = await adapter.search_by_protein(protein_name, topic=topic, max_results=max_results)
    return _serialize(result)


# --- Proteins / structures -------------------------------------------------


@mcp.tool()
async def resolve_protein(name: str) -> Optional[dict]:
    """Resolve a protein name to UniProt ID, sequence, and mapped PDB IDs.

    Returns None if no match was found.
    """
    adapter: UniProtAdapter = _adapter("uniprot", UniProtAdapter)
    results = await adapter.search_sequences(name, max_results=1)
    if not results:
        return None
    top = results[0]
    if top.uniprot_id:
        try:
            full = await adapter.get_sequence(top.uniprot_id)
            return _serialize(full)
        except SequenceNotFoundError:
            pass
    return _serialize(top)


@mcp.tool()
async def fetch_structure(pdb_id: str) -> dict:
    """Fetch a PDB structure's metadata (resolution, method, residue count) and cache the file locally."""
    adapter: PDBAdapter = _adapter("pdb", PDBAdapter)
    try:
        structure = await adapter.fetch_structure(pdb_id)
    except StructureNotFoundError as e:
        return {"error": "not_found", "pdb_id": pdb_id, "message": str(e)}
    return _serialize(structure)


def _nma_response(result) -> dict:
    """Shape an NMA result for an MCP client.

    Everything is sent except the eigenvector matrix, which is 3N x n_modes —
    around 50,000 floats for a small protein. It is not something a language
    model can use, and at ~1.5 MB it would crowd out the rest of the client's
    context. Its shape is reported so the omission is visible rather than silent;
    the full matrix is available from the Python API via NMAAnalyzer.analyze().
    """
    payload = _serialize(result)
    nma = payload.get("nma_result")
    if nma is not None:
        eigenvectors = nma.pop("eigenvectors", None)
        nma["eigenvectors_shape"] = (
            list(np.shape(eigenvectors)) if eigenvectors is not None else None
        )
        nma["eigenvectors_note"] = (
            "Omitted — too large for an MCP payload. Use the Python API for the full matrix."
        )
    return payload


@mcp.tool()
async def run_nma(pdb_id: str) -> dict:
    """Run Normal Mode Analysis on a PDB structure.

    Returns the flexibility profile (mean/max fluctuation), flexible regions,
    rigid regions, hinge residues and vibrational entropy. Uses ProDy ANM/GNM.

    All residue positions are deposited PDB residue numbers. Per-residue arrays
    (`fluctuations`) are aligned with `residue_numbers` and `chain_ids`.
    """
    agent: StructureAnalystAgent = _adapter("structure", StructureAnalystAgent)
    result = await agent.analyze_structure(pdb_id)
    return _nma_response(result)


@mcp.tool()
async def search_structures(
    query: str,
    max_results: int = 10,
    resolution_cutoff: Optional[float] = 2.5,
) -> list[dict]:
    """Search RCSB PDB for structures by keyword.

    Use when a protein has no UniProt-to-PDB mapping, or to find higher-resolution
    alternatives to a known entry. Pass resolution_cutoff=None to disable the
    resolution filter (useful for cryo-EM and NMR entries).
    """
    adapter: PDBAdapter = _adapter("pdb", PDBAdapter)
    results = await adapter.search_structures(
        query, max_results=max_results, resolution_cutoff=resolution_cutoff
    )
    return [_serialize(r) for r in results]


# --- Compounds -------------------------------------------------------------


@mcp.tool()
async def search_compounds_by_target(
    target_name: str,
    activity_type: Optional[str] = None,
    max_results: int = 20,
) -> list[dict]:
    """Search ChEMBL for compounds active against a given target.

    activity_type may be one of IC50, Ki, Kd, EC50 (case insensitive). Default
    searches across all four. Results are sorted by potency.
    """
    adapter: ChEMBLAdapter = _adapter("chembl", ChEMBLAdapter)
    results = await adapter.search_by_target(
        target_name, activity_type=activity_type, max_results=max_results
    )
    return [_serialize(r) for r in results]


@mcp.tool()
async def get_compound(identifier: str) -> dict:
    """Look up a compound by ChEMBL ID (e.g. CHEMBL25) or name (e.g. aspirin)."""
    adapter: ChEMBLAdapter = _adapter("chembl", ChEMBLAdapter)
    try:
        compound = await adapter.get_compound(identifier)
    except CompoundNotFoundError as e:
        return {"error": "not_found", "identifier": identifier, "message": str(e)}
    return _serialize(compound)


@mcp.tool()
async def get_approved_drugs_for_target(target_name: str, max_results: int = 10) -> list[dict]:
    """Return approved drugs that mechanistically target the named protein."""
    adapter: ChEMBLAdapter = _adapter("chembl", ChEMBLAdapter)
    results = await adapter.get_approved_drugs_for_target(target_name, max_results=max_results)
    return [_serialize(r) for r in results]


# --- Text analysis ---------------------------------------------------------


@mcp.tool()
def extract_mutations(text: str) -> list[dict]:
    """Extract amino-acid mutations from arbitrary text.

    Recognizes single-letter (V600E), three-letter (Ala42Gly), and HGVS
    (p.V600E) notations. Returns a list of {original, position, mutant} dicts.
    """
    agent = SynthesisAgent()
    muts = agent._extract_mutations_from_literature([Citation(pmid="text", abstract=text)])
    return [_serialize(m) for m in muts]


@mcp.tool()
def cross_reference_mutations(
    mutations: list[dict],
    flexible_regions: list[list[int]],
    hinge_residues: list[int],
) -> list[dict]:
    """Cross-reference a list of mutations with structural flexibility data.

    - mutations: list of {"original": str, "position": int, "mutant": str, ...}
    - flexible_regions: list of [start, end] residue ranges (inclusive)
    - hinge_residues: list of residue positions

    Returns insights (in_flexible_region, is_hinge_residue, recommendation) per mutation.
    """
    from .agents.nodes.synthesis import MutationInfo

    mut_infos = [
        MutationInfo(
            original=m["original"],
            position=int(m["position"]),
            mutant=m["mutant"],
            source=m.get("source", ""),
            context=m.get("context", ""),
        )
        for m in mutations
    ]
    flex_regions = [(int(a), int(b)) for a, b in flexible_regions]
    agent = SynthesisAgent()
    insights = agent._generate_insights(mut_infos, hinge_residues, flex_regions)
    return [_serialize(i) for i in insights]


# --- Full pipeline ---------------------------------------------------------


@mcp.tool()
async def run_research(query: str) -> dict:
    """Run the full biotech research pipeline end-to-end.

    Parses the query, resolves proteins, searches literature, runs structure
    analysis, searches compounds (if drug-related), and cross-references
    mutations with flexibility data. Returns the complete state including a
    markdown final_report.
    """
    state = await run_research_pipeline(query)
    return _serialize(state)


# --- Cache management ------------------------------------------------------


@mcp.tool()
def cache_stats() -> dict:
    """Report on the on-disk response cache.

    Returns entry counts (total / valid / expired) and total size in MB. The
    cache has no eviction, so it grows until something clears it.
    """
    return get_cache().stats()


@mcp.tool()
def clear_cache(namespace: Optional[str] = None) -> dict:
    """Delete cached API responses.

    Pass a namespace ("chembl", "pubmed", "uniprot", "pdb") to clear just that
    source; omit it to clear everything. Returns how many entries were removed.
    Structure files in the PDB cache directory are not touched.
    """
    cache = get_cache()
    removed = cache.clear_namespace(namespace) if namespace else cache.clear_all()
    return {"removed": removed, "namespace": namespace or "*"}


def main() -> None:
    """Entry point for the biotech-mcp console script."""
    mcp.run()


if __name__ == "__main__":
    main()
