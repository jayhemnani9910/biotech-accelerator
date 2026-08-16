"""PubMed adapter for scientific literature search."""

import asyncio
import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import date
from typing import Optional

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring as defused_fromstring

from ..ports.literature import Citation, LiteratureSearchResult
from .base import AdapterError, AdapterParseError, BaseAdapter

logger = logging.getLogger(__name__)


class PubMedAdapter(BaseAdapter):
    """Adapter for NCBI PubMed literature database."""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    _REQUEST_INTERVAL = 0.4  # 400ms between requests (NCBI rate limit)
    DEFAULT_EMAIL = "biotech-accelerator@example.com"

    def __init__(self, email: Optional[str] = None, api_key: Optional[str] = None):
        """Explicit arguments win; otherwise read the documented env vars.

        NCBI attributes rate limits to the contact email, so leaving every
        install on the placeholder address gets them throttled together.
        """
        super().__init__()
        self.email = email or os.getenv("PUBMED_EMAIL") or self.DEFAULT_EMAIL
        self.api_key = api_key or os.getenv("PUBMED_API_KEY")
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time = 0.0

    def _build_params(self, **kwargs) -> dict:
        """Build request parameters with common fields."""
        params = {"email": self.email, **kwargs}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    async def _before_request(self) -> None:
        """Serialize concurrent requests to respect NCBI's rate limit."""
        async with self._rate_limit_lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._REQUEST_INTERVAL:
                await asyncio.sleep(self._REQUEST_INTERVAL - elapsed)
            self._last_request_time = time.time()

    # Sentinels for a half-open range. E-utilities has no "unbounded" token, so
    # a bound the caller left off becomes a date far outside any real record.
    _MIN_PDAT = "1000/01/01"
    _MAX_PDAT = "3000/01/01"

    @classmethod
    def _date_filter(cls, date_from: Optional[date], date_to: Optional[date]) -> str:
        """Build the [PDAT] clause for any combination of bounds.

        Must be assembled as one clause: building it from two independent
        branches put the AND on the lower bound and a bare ':' on the upper one,
        so an upper-bound-only search appended a fragment PubMed ignored — and
        returned unfiltered results that looked filtered.
        """
        if date_from is None and date_to is None:
            return ""

        lower = date_from.strftime("%Y/%m/%d") if date_from else cls._MIN_PDAT
        upper = date_to.strftime("%Y/%m/%d") if date_to else cls._MAX_PDAT
        return f" AND {lower}:{upper}[PDAT]"

    async def search(
        self,
        query: str,
        max_results: int = 20,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> LiteratureSearchResult:
        """Search PubMed for papers."""
        empty = LiteratureSearchResult(citations=[], total_count=0, query=query)

        date_filter = self._date_filter(date_from, date_to)

        params = self._build_params(
            db="pubmed",
            term=query + date_filter,
            retmax=max_results,
            retmode="json",
            sort="relevance",
        )

        try:
            data = await self._get_json(f"{self.BASE_URL}/esearch.fcgi", params=params)
        except AdapterError as e:
            logger.error(f"PubMed search failed: {e}")
            return empty

        result = data.get("esearchresult", {})
        pmids = result.get("idlist", [])
        total_count = int(result.get("count", 0))

        if not pmids:
            return LiteratureSearchResult(citations=[], total_count=total_count, query=query)

        citations = await self._fetch_details(pmids)
        return LiteratureSearchResult(citations=citations, total_count=total_count, query=query)

    async def _fetch_details(self, pmids: list[str]) -> list[Citation]:
        """Fetch paper details for a list of PMIDs (XML response)."""
        if not pmids:
            return []

        params = self._build_params(db="pubmed", id=",".join(pmids), retmode="xml")
        url = f"{self.BASE_URL}/efetch.fcgi"

        try:
            response = await self._request("GET", url, params=params)
        except AdapterError as e:
            logger.error(f"Failed to fetch paper details: {e}")
            return []

        try:
            root = self._parse_xml(response.content)
        except (ET.ParseError, DefusedXmlException) as e:
            raise AdapterParseError(url, f"Invalid XML: {e}") from e

        citations = []
        for article in root.findall(".//PubmedArticle"):
            citation = self._parse_article(article)
            if citation:
                citations.append(citation)
        return citations

    @staticmethod
    def _parse_xml(payload) -> ET.Element:
        """Parse an efetch response.

        Uses defusedxml rather than the stdlib parser: this runs on bytes taken
        straight off the network, and stdlib ElementTree expands internal
        entities, so a hostile or compromised response can exhaust memory before
        anything gets a chance to validate it.
        """
        return defused_fromstring(payload)

    @staticmethod
    def _text_of(element: Optional[ET.Element]) -> str:
        """Full text of an element, including anything after inline markup.

        PubMed titles and abstracts carry <i>, <sub>, <sup> and friends. Reading
        `.text` stops at the first child, so "Effects of <i>KRAS</i> G12C" came
        back as "Effects of ".
        """
        if element is None:
            return ""
        return "".join(element.itertext()).strip()

    @classmethod
    def _abstract_of(cls, article_elem: ET.Element) -> Optional[str]:
        """Join every section of an abstract, labels included.

        Biomedical abstracts are usually structured — several AbstractText
        elements labelled BACKGROUND / METHODS / RESULTS / CONCLUSIONS. Taking
        only the first one dropped RESULTS, which is where mutations are
        reported, so downstream extraction never saw them.
        """
        sections = []
        for node in article_elem.findall(".//Abstract/AbstractText"):
            text = cls._text_of(node)
            if not text:
                continue
            label = node.get("Label") or node.get("NlmCategory")
            sections.append(f"{label.strip()}: {text}" if label else text)

        return "\n\n".join(sections) if sections else None

    @classmethod
    def _authors_of(cls, article_elem: ET.Element) -> list[str]:
        authors: list[str] = []
        for author in article_elem.findall(".//Author"):
            last_name = cls._text_of(author.find("LastName"))
            if not last_name:
                # Consortium/group authorship carries a CollectiveName instead.
                collective = cls._text_of(author.find("CollectiveName"))
                if collective:
                    authors.append(collective)
                continue
            first_name = cls._text_of(author.find("ForeName"))
            authors.append(f"{first_name} {last_name}" if first_name else last_name)
        return authors

    @classmethod
    def _year_of(cls, article_elem: ET.Element) -> Optional[int]:
        year = cls._text_of(article_elem.find(".//PubDate/Year"))
        if not year:
            # Some records carry only "2024 Mar-Apr" in MedlineDate.
            medline_date = cls._text_of(article_elem.find(".//PubDate/MedlineDate"))
            year = medline_date[:4]
        try:
            return int(year)
        except ValueError:
            return None

    def _parse_article(self, article: ET.Element) -> Optional[Citation]:
        """Parse a PubmedArticle XML element into a Citation."""
        try:
            medline = article.find(".//MedlineCitation")
            if medline is None:
                return None

            article_elem = medline.find(".//Article")
            if article_elem is None:
                return None

            pmid = self._text_of(medline.find(".//PMID")) or None

            doi = None
            for id_elem in article.findall(".//ArticleId"):
                if id_elem.get("IdType") == "doi":
                    doi = self._text_of(id_elem) or None
                    break

            return Citation(
                pmid=pmid,
                doi=doi,
                title=self._text_of(article_elem.find(".//ArticleTitle")),
                authors=self._authors_of(article_elem),
                journal=self._text_of(article_elem.find(".//Journal/Title")),
                year=self._year_of(article_elem),
                abstract=self._abstract_of(article_elem),
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
            )

        except (AttributeError, TypeError, KeyError) as e:
            logger.warning(f"Failed to parse article: {e}")
            return None

    async def search_by_protein(
        self,
        protein_name: str,
        topic: Optional[str] = None,
        max_results: int = 20,
    ) -> LiteratureSearchResult:
        """Search for papers about a specific protein."""
        query_parts = [f'"{protein_name}"[Title/Abstract]']

        if topic:
            if " OR " in topic:
                or_terms = topic.split(" OR ")
                or_clause = " OR ".join(f"{t.strip()}[Title/Abstract]" for t in or_terms)
                query_parts.append(f"({or_clause})")
            else:
                query_parts.append(f"{topic}[Title/Abstract]")

        return await self.search(" AND ".join(query_parts), max_results=max_results)
