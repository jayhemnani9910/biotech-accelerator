"""Abstract interface for protein structure providers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ..domain.protein_models import PDBStructure, ProteinInfo


class StructurePort(ABC):
    """Abstract interface for fetching protein structures."""

    @abstractmethod
    async def fetch_structure(self, pdb_id: str) -> PDBStructure:
        """
        Fetch a protein structure by PDB ID.

        Args:
            pdb_id: 4-character PDB identifier (e.g., "1LYZ")

        Returns:
            PDBStructure with file path and metadata

        Raises:
            StructureNotFoundError: If PDB ID doesn't exist
        """
        pass

    @abstractmethod
    async def search_structures(
        self,
        query: str,
        max_results: int = 10,
        resolution_cutoff: Optional[float] = 2.5,
    ) -> list[ProteinInfo]:
        """
        Search for protein structures by keyword or sequence.

        Args:
            query: Search query (protein name, gene, or sequence)
            max_results: Maximum number of results
            resolution_cutoff: Only return structures with resolution <= cutoff

        Returns:
            List of matching protein info
        """
        pass

    @abstractmethod
    async def get_structure_file(self, pdb_id: str) -> Path:
        """
        Get the local file path for a PDB structure.

        Downloads if not cached locally.

        Args:
            pdb_id: 4-character PDB identifier

        Returns:
            Path to the local PDB file
        """
        pass

    @abstractmethod
    def get_cache_dir(self) -> Path:
        """Return the directory where structures are cached."""
        pass


class StructureNotFoundError(Exception):
    """Raised when a structure cannot be found."""

    def __init__(self, pdb_id: str):
        self.pdb_id = pdb_id
        super().__init__(f"Structure not found: {pdb_id}")
