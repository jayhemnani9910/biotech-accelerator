"""Domain models for biotech research."""

from .compound_models import BindingPrediction, CompoundInfo
from .protein_models import (
    FlexibilityMetrics,
    MutationPrediction,
    NMAResult,
    PDBStructure,
    ProteinInfo,
)

__all__ = [
    "ProteinInfo",
    "PDBStructure",
    "NMAResult",
    "MutationPrediction",
    "FlexibilityMetrics",
    "CompoundInfo",
    "BindingPrediction",
]
