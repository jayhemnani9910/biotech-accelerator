"""Data models for protein sequences."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SequenceInfo:
    """Protein sequence with annotations."""

    uniprot_id: str
    name: str
    sequence: str
    organism: str
    gene_name: Optional[str] = None
    function: Optional[str] = None
    pdb_ids: list[str] = field(default_factory=list)

    @property
    def length(self) -> int:
        return len(self.sequence)


class SequenceNotFoundError(Exception):
    """Raised when a sequence cannot be found."""

    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"Sequence not found: {identifier}")
