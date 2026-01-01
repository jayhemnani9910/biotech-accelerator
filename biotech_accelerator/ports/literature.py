"""Abstract interface for scientific literature providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Citation:
    """Scientific paper citation."""

    pmid: Optional[str] = None
    doi: Optional[str] = None
    title: str = ""
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    year: Optional[int] = None
    abstract: Optional[str] = None
    url: Optional[str] = None

    @property
    def first_author(self) -> str:
        return self.authors[0] if self.authors else "Unknown"

    def to_citation_string(self) -> str:
        """Format as standard citation."""
        author_str = self.first_author + " et al." if len(self.authors) > 1 else self.first_author
        return f"{author_str} ({self.year}). {self.title}. {self.journal}."


@dataclass
class LiteratureSearchResult:
    """Result from literature search."""

    citations: list[Citation]
    total_count: int
    query: str


class LiteraturePort(ABC):
    """Abstract interface for scientific literature search."""

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 20,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> LiteratureSearchResult:
        """
        Search scientific literature.

        Args:
            query: Search query
            max_results: Maximum results
            date_from: Filter by publication date
            date_to: Filter by publication date

        Returns:
            LiteratureSearchResult with citations
        """
        pass

    @abstractmethod
    async def get_paper(self, identifier: str) -> Citation:
        """
        Get a specific paper by PMID or DOI.

        Args:
            identifier: PMID or DOI

        Returns:
            Citation with full details
        """
        pass

    @abstractmethod
    async def search_by_protein(
        self,
        protein_name: str,
        topic: Optional[str] = None,
        max_results: int = 20,
    ) -> LiteratureSearchResult:
        """
        Search for papers about a specific protein.

        Args:
            protein_name: Protein name or gene
            topic: Optional topic filter (e.g., "mutation", "stability")
            max_results: Maximum results

        Returns:
            LiteratureSearchResult
        """
        pass
