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


@dataclass
class FlexibilityMetrics:
    """Protein flexibility analysis results.

    All positions are deposited residue numbers, not indices into the Ca array.
    """

    mean_fluctuation: float
    max_fluctuation: float
    flexible_regions: list[tuple[int, int]]  # (start, end) residue numbers, inclusive
    rigid_regions: list[tuple[int, int]]
    hinge_residues: list[int]


@dataclass
class NMAResult:
    """Normal Mode Analysis result."""

    pdb_id: str
    n_modes: int
    eigenvalues: np.ndarray
    eigenvectors: np.ndarray
    fluctuations: np.ndarray  # Per-residue fluctuations, in Ca-array order
    collectivity: np.ndarray  # Mode collectivity
    vibrational_entropy: float
    flexibility: FlexibilityMetrics
    # Deposited residue number / chain ID for each entry in `fluctuations`.
    residue_numbers: list[int] = field(default_factory=list)
    chain_ids: list[str] = field(default_factory=list)
