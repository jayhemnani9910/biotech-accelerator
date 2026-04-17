"""MCP server exposing the biotech pipeline as tools for coding agents.

Run with: `biotech-mcp` (entry point) or `python -m biotech_accelerator.mcp_server`.

Designed to be consumed by Claude Code (or any MCP-compatible client). Each
tool is a thin, composable wrapper over the existing adapters and agents —
no embedded LLM calls; reasoning happens in the client.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from .adapters.chembl_adapter import ChEMBLAdapter, CompoundNotFoundError
from .adapters.pdb_adapter import PDBAdapter
from .adapters.pubmed_adapter import PubMedAdapter
from .adapters.uniprot_adapter import UniProtAdapter
from .agents.nodes.structure_analyst import StructureAnalystAgent
from .agents.nodes.synthesis import SynthesisAgent
from .graph.biotech_graph import run_research as run_research_pipeline
from .ports.sequence import SequenceNotFoundError
from .ports.structure import StructureNotFoundError

mcp = FastMCP("biotech-accelerator")


# --- lazy adapter cache (one instance per process) -------------------------


_adapters: dict[str, Any] = {}


def _adapter(key: str, factory):
    if key not in _adapters:
        _adapters[key] = factory()
    return _adapters[key]


def _serialize(obj: Any) -> Any:
    """Recursively convert dataclasses / iterables to JSON-friendly structures."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        # Enums, pathlib.Path, etc. — fall back to str.
        try:
            return {k: _serialize(v) for k, v in vars(obj).items()}
        except TypeError:
            return str(obj)
    # Path, Enum, etc.
    if hasattr(obj, "value"):
        return obj.value
    return obj


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


@mcp.tool()
async def run_nma(pdb_id: str) -> dict:
    """Run Normal Mode Analysis on a PDB structure.

    Returns flexibility profile (mean/max fluctuation), flexible regions,
    rigid regions, hinge residues, and vibrational entropy. Uses ProDy ANM/GNM.
    """
    agent: StructureAnalystAgent = _adapter("structure", StructureAnalystAgent)
    result = await agent.analyze_structure(pdb_id)
    return _serialize(result)


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

    class _Fake:
        def __init__(self, t):
            self.abstract = t
            self.title = ""
            self.pmid = "text"

    muts = agent._extract_mutations_from_literature([_Fake(text)])
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


def main() -> None:
    """Entry point for the biotech-mcp console script."""
    mcp.run()


if __name__ == "__main__":
    main()
