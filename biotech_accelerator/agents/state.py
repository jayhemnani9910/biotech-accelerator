"""
Biotech Research State

Extended state for biotech-specific research combining
literature evidence with computational analysis.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from ..domain.compound_models import BindingPrediction, CompoundInfo
from ..domain.protein_models import MutationPrediction, NMAResult, PDBStructure
from ..ports.literature import Citation
from ..ports.sequence import SequenceInfo


@dataclass
class ProteinContext:
    """Context about a protein being researched."""

    name: str
    pdb_id: Optional[str] = None
    uniprot_id: Optional[str] = None
    sequence_info: Optional[SequenceInfo] = None
    structure: Optional[PDBStructure] = None
    nma_result: Optional[NMAResult] = None


@dataclass
class Evidence:
    """Evidence from literature or computation."""

    source: str  # "literature" or "computational"
    content: str
    confidence: float = 0.5
    citation: Optional[Citation] = None
    supports_hypothesis: bool = True


@dataclass
class BiotechResearchState:
    """
    State for biotech research workflow.

    Tracks proteins, literature, and computational results.
    """

    # Query
    query: str = ""
    research_goal: str = ""

    # Proteins being researched
    target_proteins: list[ProteinContext] = field(default_factory=list)
    pdb_ids: list[str] = field(default_factory=list)
    uniprot_ids: list[str] = field(default_factory=list)

    # Literature evidence
    literature_citations: list[Citation] = field(default_factory=list)
    supporting_evidence: list[Evidence] = field(default_factory=list)
    contradicting_evidence: list[Evidence] = field(default_factory=list)

    # Computational results
    structure_analyses: dict[str, NMAResult] = field(default_factory=dict)
    mutation_predictions: list[MutationPrediction] = field(default_factory=list)
    binding_predictions: list[BindingPrediction] = field(default_factory=list)

    # Compounds (for drug discovery)
    target_compounds: list[CompoundInfo] = field(default_factory=list)

    # Control flow
    current_phase: str = "init"  # init, literature, structure, synthesis, done
    recursion_depth: int = 0
    max_depth: int = 3

    # Results
    synthesis: str = ""
    final_report: str = ""
    error: Optional[str] = None

    def add_protein(self, protein: ProteinContext) -> None:
        """Add a protein to the research context."""
        self.target_proteins.append(protein)
        if protein.pdb_id:
            self.pdb_ids.append(protein.pdb_id)
        if protein.uniprot_id:
            self.uniprot_ids.append(protein.uniprot_id)

    def add_evidence(self, evidence: Evidence) -> None:
        """Add evidence to appropriate list."""
        if evidence.supports_hypothesis:
            self.supporting_evidence.append(evidence)
        else:
            self.contradicting_evidence.append(evidence)

    def get_protein_by_pdb(self, pdb_id: str) -> Optional[ProteinContext]:
        """Get protein context by PDB ID."""
        for protein in self.target_proteins:
            if protein.pdb_id == pdb_id:
                return protein
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for LangGraph."""
        return {
            "query": self.query,
            "research_goal": self.research_goal,
            "target_proteins": self.target_proteins,
            "pdb_ids": self.pdb_ids,
            "uniprot_ids": self.uniprot_ids,
            "literature_citations": self.literature_citations,
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "structure_analyses": self.structure_analyses,
            "mutation_predictions": self.mutation_predictions,
            "current_phase": self.current_phase,
            "synthesis": self.synthesis,
            "final_report": self.final_report,
            "error": self.error,
        }


def create_initial_state(query: str, max_depth: int = 3) -> dict[str, Any]:
    """Create initial state dictionary for LangGraph."""
    return {
        "query": query,
        "root_query": query,
        "research_goal": "",
        "target_proteins": [],
        "pdb_ids": [],
        "uniprot_ids": [],
        "literature_citations": [],
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "structure_analyses": {},
        "mutation_predictions": [],
        "current_phase": "init",
        "recursion_depth": 0,
        "max_depth": max_depth,
        "synthesis": "",
        "final_report": "",
        "error": None,
    }
