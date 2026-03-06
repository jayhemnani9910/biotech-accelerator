"""PubMed adapter for scientific literature search."""

import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from datetime import date
from json import JSONDecodeError
from typing import Optional

import httpx
from httpx import ConnectError, HTTPStatusError, TimeoutException

from ..ports.literature import Citation, LiteraturePort, LiteratureSearchResult

logger = logging.getLogger(__name__)

# Rate limiting for NCBI API (max 3 requests per second without API key)
_request_interval = 0.4  # 400ms between requests


class PubMedAdapter(LiteraturePort):
    """
    Adapter for NCBI PubMed literature database.

    Uses the E-utilities API for searching and fetching papers.
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, email: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize PubMed adapter.

        Args:
            email: Email for NCBI API (recommended)
            api_key: NCBI API key for higher rate limits
        """
        self.email = email or "biotech-accelerator@example.com"
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=30.0)
        self._max_retries = 3
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time = 0.0

    def __del__(self):
        """Cleanup HTTP client on garbage collection."""
        if hasattr(self, "_client") and self._client:
            try:
                import asyncio

                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._client.aclose())
                except RuntimeError:
                    pass  # No running loop, client will be cleaned up
            except Exception:
                pass

    def _build_params(self, **kwargs) -> dict:
        """Build request parameters with common fields."""
        params = {"email": self.email, **kwargs}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    async def _rate_limited_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make a rate-limited request with retry logic."""
        for attempt in range(self._max_retries):
            # Rate limiting with async lock
            async with self._rate_limit_lock:
                elapsed = time.time() - self._last_request_time
                if elapsed < _request_interval:
                    await asyncio.sleep(_request_interval - elapsed)
                self._last_request_time = time.time()

            try:
                if method == "GET":
                    response = await self._client.get(url, **kwargs)
                else:
                    response = await self._client.post(url, **kwargs)

                # Handle rate limiting
                if response.status_code == 429:
                    wait_time = (attempt + 1) * 2  # Exponential backoff
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                    continue

                return response

            except TimeoutException:
                if attempt < self._max_retries - 1:
                    logger.warning(f"Request timed out, retrying: {url}")
                    await asyncio.sleep(1)
                else:
                    raise
            except ConnectError as e:
                if attempt < self._max_retries - 1:
                    logger.warning(f"Connection failed, retrying: {e}")
                    await asyncio.sleep(1)
                else:
                    raise

        raise RuntimeError("Max retries exceeded")

    async def search(
        self,
        query: str,
        max_results: int = 20,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> LiteratureSearchResult:
        """Search PubMed for papers."""
        # Build date filter
        date_filter = ""
        if date_from:
            date_filter += f" AND {date_from.strftime('%Y/%m/%d')}[PDAT]"
        if date_to:
            date_filter += f" : {date_to.strftime('%Y/%m/%d')}[PDAT]"

        full_query = query + date_filter

        # Search for PMIDs
        search_url = f"{self.BASE_URL}/esearch.fcgi"
        params = self._build_params(
            db="pubmed",
            term=full_query,
            retmax=max_results,
            retmode="json",
            sort="relevance",
        )

        try:
            response = await self._rate_limited_request("GET", search_url, params=params)
            response.raise_for_status()
        except HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {search_url}")
            return LiteratureSearchResult(citations=[], total_count=0, query=query)
        except TimeoutException:
            logger.error(f"Request timed out: {search_url}")
            return LiteratureSearchResult(citations=[], total_count=0, query=query)
        except ConnectError as e:
            logger.error(f"Connection failed: {e}")
            return LiteratureSearchResult(citations=[], total_count=0, query=query)
        except RuntimeError as e:
            logger.error(f"PubMed search failed: {e}")
            return LiteratureSearchResult(citations=[], total_count=0, query=query)

        try:
            data = response.json()
        except JSONDecodeError as e:
            logger.error(f"Invalid JSON response from {search_url}: {e}")
            return LiteratureSearchResult(citations=[], total_count=0, query=query)

        result = data.get("esearchresult", {})
        pmids = result.get("idlist", [])
        total_count = int(result.get("count", 0))

        if not pmids:
            return LiteratureSearchResult(
                citations=[],
                total_count=total_count,
                query=query,
            )

        # Fetch details for each PMID
        citations = await self._fetch_details(pmids)

        return LiteratureSearchResult(
            citations=citations,
            total_count=total_count,
            query=query,
        )

    async def _fetch_details(self, pmids: list[str]) -> list[Citation]:
        """Fetch paper details for a list of PMIDs."""
        if not pmids:
            return []

        fetch_url = f"{self.BASE_URL}/efetch.fcgi"
        params = self._build_params(
            db="pubmed",
            id=",".join(pmids),
            retmode="xml",
        )

        try:
            response = await self._rate_limited_request("GET", fetch_url, params=params)
            response.raise_for_status()
        except HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {fetch_url}")
            return []
        except TimeoutException:
            logger.error(f"Request timed out: {fetch_url}")
            return []
        except ConnectError as e:
            logger.error(f"Connection failed: {e}")
            return []
        except RuntimeError as e:
            logger.error(f"Failed to fetch paper details: {e}")
            return []

        try:
            # Parse XML response
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            logger.error(f"Invalid XML response from {fetch_url}: {e}")
            return []

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

            # PMID
            pmid_elem = medline.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else None

            # Article info
            article_elem = medline.find(".//Article")
            if article_elem is None:
                return None

            # Title
            title_elem = article_elem.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else ""

            # Abstract
            abstract_elem = article_elem.find(".//Abstract/AbstractText")
            abstract = abstract_elem.text if abstract_elem is not None else None

            # Authors
            authors = []
            for author in article_elem.findall(".//Author"):
                last_name = author.find("LastName")
                first_name = author.find("ForeName")
                if last_name is not None:
                    name = last_name.text
                    if first_name is not None:
                        name = f"{first_name.text} {name}"
                    authors.append(name)

            # Journal
            journal_elem = article_elem.find(".//Journal/Title")
            journal = journal_elem.text if journal_elem is not None else ""

            # Year
            year = None
            year_elem = article_elem.find(".//PubDate/Year")
            if year_elem is not None and year_elem.text:
                try:
                    year = int(year_elem.text)
                except ValueError:
                    pass

            # DOI
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
        # Determine if it's a PMID or DOI
        if identifier.startswith("10."):
            # It's a DOI
            query = f"{identifier}[doi]"
        else:
            # Assume PMID
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
        # Build MeSH-aware query
        query_parts = [f'"{protein_name}"[Title/Abstract]']

        if topic:
            # Handle OR/AND in topic properly - don't quote the whole thing
            # Split by OR and wrap each term individually
            if " OR " in topic:
                or_terms = topic.split(" OR ")
                or_clause = " OR ".join(f"{t.strip()}[Title/Abstract]" for t in or_terms)
                query_parts.append(f"({or_clause})")
            else:
                query_parts.append(f"{topic}[Title/Abstract]")

        query = " AND ".join(query_parts)

        return await self.search(query, max_results=max_results)

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
