"""Compound and drug-related domain models."""

from dataclasses import dataclass
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
