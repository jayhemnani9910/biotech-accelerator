"""Protein-related domain models."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np


class ProteinSource(Enum):
    """Source of protein structure."""

    PDB = "pdb"
    ALPHAFOLD = "alphafold"
    COMPUTED = "computed"


@dataclass
class ProteinInfo:
    """Basic protein information."""

    name: str
    pdb_id: Optional[str] = None
    uniprot_id: Optional[str] = None
    sequence: Optional[str] = None
    organism: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self):
        if self.pdb_id:
            self.pdb_id = self.pdb_id.upper()


@dataclass
class PDBStructure:
    """Protein structure from PDB."""

    pdb_id: str
    file_path: Path
    resolution: Optional[float] = None
    method: Optional[str] = None  # X-RAY, NMR, CRYO-EM
    chain_ids: list[str] = field(default_factory=list)
    num_residues: int = 0
    source: ProteinSource = ProteinSource.PDB

    @property
    def is_high_resolution(self) -> bool:
        """Check if structure is high resolution (< 2.5 Å)."""
        return self.resolution is not None and self.resolution < 2.5


@dataclass
class FlexibilityMetrics:
    """Protein flexibility analysis results."""

    mean_fluctuation: float
    max_fluctuation: float
    flexible_regions: list[tuple[int, int]]  # (start, end) residue indices
    rigid_regions: list[tuple[int, int]]
    hinge_residues: list[int]


@dataclass
class NMAResult:
    """Normal Mode Analysis result."""

    pdb_id: str
    n_modes: int
    eigenvalues: np.ndarray
    eigenvectors: np.ndarray
    fluctuations: np.ndarray  # Per-residue fluctuations
    collectivity: np.ndarray  # Mode collectivity
    vibrational_entropy: float
    flexibility: FlexibilityMetrics

    def get_mode(self, mode_index: int) -> np.ndarray:
        """Get eigenvector for a specific mode."""
        return self.eigenvectors[:, mode_index]

    def get_top_modes(self, n: int = 10) -> list[tuple[int, float, np.ndarray]]:
        """Get top N modes by collectivity."""
        indices = np.argsort(self.collectivity)[::-1][:n]
        return [(i, self.collectivity[i], self.eigenvectors[:, i]) for i in indices]


@dataclass
class MutationPrediction:
    """Prediction of mutation effect."""

    wild_type: str  # e.g., "A" for Alanine
    mutant: str  # e.g., "G" for Glycine
    position: int  # Residue number
    ddg: float  # Predicted change in stability (kcal/mol)
    confidence: float  # 0-1 confidence score
    effect: str  # "stabilizing", "destabilizing", "neutral"

    @property
    def mutation_string(self) -> str:
        """Return mutation in standard notation (e.g., A42G)."""
        return f"{self.wild_type}{self.position}{self.mutant}"

    @classmethod
    def classify_effect(cls, ddg: float, threshold: float = 1.0) -> str:
        """Classify mutation effect based on ΔΔG."""
        if ddg < -threshold:
            return "stabilizing"
        elif ddg > threshold:
            return "destabilizing"
        return "neutral"
