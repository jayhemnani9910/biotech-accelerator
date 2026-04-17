"""Biotech Research Accelerator.

A LangGraph-based pipeline for biotech research that orchestrates PubMed,
RCSB PDB, UniProt, and ChEMBL adapters plus ProDy normal-mode analysis.
Exposed as an MCP server (`biotech-mcp`), a CLI (`biotech`), and a Python
API so coding agents (Claude Code and peers) can drive the analysis.
"""

from .adapters.chembl_adapter import ChEMBLAdapter, CompoundNotFoundError
from .adapters.pdb_adapter import PDBAdapter
from .adapters.pubmed_adapter import PubMedAdapter
from .adapters.uniprot_adapter import UniProtAdapter
from .graph.biotech_graph import BiotechState, build_biotech_graph, run_research
from .ports.sequence import SequenceNotFoundError
from .ports.structure import StructureNotFoundError

__version__ = "0.1.0"

__all__ = [
    "BiotechState",
    "ChEMBLAdapter",
    "CompoundNotFoundError",
    "PDBAdapter",
    "PubMedAdapter",
    "SequenceNotFoundError",
    "StructureNotFoundError",
    "UniProtAdapter",
    "build_biotech_graph",
    "run_research",
    "__version__",
]
