"""Compound and drug-related domain models."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CompoundInfo:
    """Chemical compound information."""

    name: str
    smiles: Optional[str] = None
    inchi: Optional[str] = None
    chembl_id: Optional[str] = None
    pubchem_cid: Optional[int] = None
    molecular_weight: Optional[float] = None
    logp: Optional[float] = None

    @property
    def is_drug_like(self) -> bool:
        """Check Lipinski's Rule of Five (simplified)."""
        if self.molecular_weight is None or self.logp is None:
            return False
        return self.molecular_weight <= 500 and self.logp <= 5


@dataclass
class BindingPrediction:
    """Compound-protein binding prediction."""

    compound: CompoundInfo
    protein_pdb_id: str
    binding_affinity: float  # pKd or pIC50
    binding_site_residues: list[int] = field(default_factory=list)
    confidence: float = 0.0
    source: str = "predicted"  # or "experimental"

    @property
    def affinity_nm(self) -> float:
        """Convert pKd/pIC50 to nanomolar."""
        return 10 ** (9 - self.binding_affinity)
