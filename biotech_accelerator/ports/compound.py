"""Data models for compound/drug data."""

from dataclasses import dataclass
from typing import Optional

from ..domain.compound_models import CompoundInfo


@dataclass
class BioactivityData:
    """Bioactivity measurement for a compound-target pair."""

    compound: CompoundInfo
    target_name: str
    target_uniprot: Optional[str] = None
    activity_type: str = ""  # IC50, Ki, Kd, EC50
    activity_value: float = 0.0
    activity_unit: str = "nM"
    assay_type: Optional[str] = None
