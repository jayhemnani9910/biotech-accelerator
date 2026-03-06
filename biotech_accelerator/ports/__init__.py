"""Abstract interfaces (ports) for biotech adapters."""

from .compound import CompoundPort
from .literature import LiteraturePort
from .sequence import SequencePort
from .structure import StructurePort

__all__ = [
    "StructurePort",
    "SequencePort",
    "LiteraturePort",
    "CompoundPort",
]
