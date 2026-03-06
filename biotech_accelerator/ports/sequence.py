"""Abstract interface for protein sequence providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
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
    pdb_ids: list[str] = None

    def __post_init__(self):
        if self.pdb_ids is None:
            self.pdb_ids = []

    @property
    def length(self) -> int:
        return len(self.sequence)


class SequencePort(ABC):
    """Abstract interface for protein sequence data."""

    @abstractmethod
    async def get_sequence(self, uniprot_id: str) -> SequenceInfo:
        """
        Get protein sequence by UniProt ID.

        Args:
            uniprot_id: UniProt accession (e.g., "P00698")

        Returns:
            SequenceInfo with sequence and annotations
        """
        pass

    @abstractmethod
    async def search_sequences(
        self,
        query: str,
        organism: Optional[str] = None,
        max_results: int = 10,
    ) -> list[SequenceInfo]:
        """
        Search for protein sequences.

        Args:
            query: Search query (protein name, gene, keyword)
            organism: Optional organism filter
            max_results: Maximum results to return

        Returns:
            List of matching sequences
        """
        pass

    @abstractmethod
    async def get_pdb_mapping(self, uniprot_id: str) -> list[str]:
        """
        Get PDB IDs mapped to a UniProt accession.

        Args:
            uniprot_id: UniProt accession

        Returns:
            List of PDB IDs
        """
        pass


class SequenceNotFoundError(Exception):
    """Raised when a sequence cannot be found."""

    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"Sequence not found: {identifier}")
