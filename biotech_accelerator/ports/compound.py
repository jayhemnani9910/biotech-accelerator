"""Abstract interface for compound/drug data providers."""

from abc import ABC, abstractmethod
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


class CompoundPort(ABC):
    """Abstract interface for compound/drug data."""

    @abstractmethod
    async def get_compound(self, identifier: str) -> CompoundInfo:
        """
        Get compound by ChEMBL ID, PubChem CID, or name.

        Args:
            identifier: Compound identifier

        Returns:
            CompoundInfo with structure and properties
        """
        pass

    @abstractmethod
    async def search_by_target(
        self,
        target_name: str,
        activity_type: Optional[str] = None,
        max_results: int = 20,
    ) -> list[BioactivityData]:
        """
        Search for compounds active against a target.

        Args:
            target_name: Target protein name or UniProt ID
            activity_type: Filter by activity type (IC50, Ki, etc.)
            max_results: Maximum results

        Returns:
            List of bioactivity data
        """
        pass

    @abstractmethod
    async def get_bioactivity(
        self,
        compound_id: str,
        target: Optional[str] = None,
    ) -> list[BioactivityData]:
        """
        Get bioactivity data for a compound.

        Args:
            compound_id: Compound identifier
            target: Optional target filter

        Returns:
            List of bioactivity measurements
        """
        pass

    @abstractmethod
    async def search_similar(
        self,
        smiles: str,
        similarity_threshold: float = 0.7,
        max_results: int = 20,
    ) -> list[CompoundInfo]:
        """
        Search for similar compounds by structure.

        Args:
            smiles: SMILES string of query compound
            similarity_threshold: Tanimoto similarity threshold
            max_results: Maximum results

        Returns:
            List of similar compounds
        """
        pass
