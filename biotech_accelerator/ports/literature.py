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


@dataclass
class LiteratureSearchResult:
    """Result from literature search."""

    citations: list[Citation]
    total_count: int
    query: str
