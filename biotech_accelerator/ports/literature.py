"""Data models for scientific literature."""

from dataclasses import dataclass, field
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
