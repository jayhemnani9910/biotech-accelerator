"""PubMed adapter for scientific literature search."""

import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from datetime import date
from typing import Optional

from ..ports.literature import Citation, LiteratureSearchResult
from .base import AdapterError, AdapterParseError, BaseAdapter

logger = logging.getLogger(__name__)


class PubMedAdapter(BaseAdapter):
    """Adapter for NCBI PubMed literature database."""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    _REQUEST_INTERVAL = 0.4  # 400ms between requests (NCBI rate limit)

    def __init__(self, email: Optional[str] = None, api_key: Optional[str] = None):
        super().__init__()
        self.email = email or "biotech-accelerator@example.com"
        self.api_key = api_key
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

    async def search(
        self,
        query: str,
        max_results: int = 20,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> LiteratureSearchResult:
        """Search PubMed for papers."""
        empty = LiteratureSearchResult(citations=[], total_count=0, query=query)

        date_filter = ""
        if date_from:
            date_filter += f" AND {date_from.strftime('%Y/%m/%d')}[PDAT]"
        if date_to:
            date_filter += f" : {date_to.strftime('%Y/%m/%d')}[PDAT]"

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
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            raise AdapterParseError(url, f"Invalid XML: {e}") from e

        citations = []
        for article in root.findall(".//PubmedArticle"):
            citation = self._parse_article(article)
            if citation:
                citations.append(citation)
        return citations

    def _parse_article(self, article: ET.Element) -> Optional[Citation]:
        """Parse a PubmedArticle XML element into a Citation."""
        try:
            medline = article.find(".//MedlineCitation")
            if medline is None:
                return None

            pmid_elem = medline.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else None

            article_elem = medline.find(".//Article")
            if article_elem is None:
                return None

            title_elem = article_elem.find(".//ArticleTitle")
            title = (title_elem.text or "") if title_elem is not None else ""

            abstract_elem = article_elem.find(".//Abstract/AbstractText")
            abstract = abstract_elem.text if abstract_elem is not None else None

            authors: list[str] = []
            for author in article_elem.findall(".//Author"):
                last_name = author.find("LastName")
                first_name = author.find("ForeName")
                if last_name is not None and last_name.text:
                    name = last_name.text
                    if first_name is not None and first_name.text:
                        name = f"{first_name.text} {name}"
                    authors.append(name)

            journal_elem = article_elem.find(".//Journal/Title")
            journal = (journal_elem.text or "") if journal_elem is not None else ""

            year = None
            year_elem = article_elem.find(".//PubDate/Year")
            if year_elem is not None and year_elem.text:
                try:
                    year = int(year_elem.text)
                except ValueError:
                    pass

            doi = None
            for id_elem in article.findall(".//ArticleId"):
                if id_elem.get("IdType") == "doi":
                    doi = id_elem.text
                    break

            return Citation(
                pmid=pmid,
                doi=doi,
                title=title,
                authors=authors,
                journal=journal,
                year=year,
                abstract=abstract,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
            )

        except (AttributeError, TypeError, KeyError) as e:
            logger.warning(f"Failed to parse article: {e}")
            return None

    async def get_paper(self, identifier: str) -> Citation:
        """Get a specific paper by PMID or DOI."""
        if identifier.startswith("10."):
            query = f"{identifier}[doi]"
        else:
            query = f"{identifier}[pmid]"

        result = await self.search(query, max_results=1)
        if result.citations:
            return result.citations[0]
        raise ValueError(f"Paper not found: {identifier}")

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
