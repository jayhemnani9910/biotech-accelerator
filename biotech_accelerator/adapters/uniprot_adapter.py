"""UniProt adapter for protein sequences and annotations."""

import logging
from json import JSONDecodeError
from typing import Optional

import httpx
from httpx import ConnectError, HTTPStatusError, TimeoutException

from ..ports.sequence import SequenceInfo, SequenceNotFoundError, SequencePort

logger = logging.getLogger(__name__)


class UniProtAdapter(SequencePort):
    """
    Adapter for UniProt protein database.

    Fetches sequences, annotations, and cross-references.
    """

    BASE_URL = "https://rest.uniprot.org"

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)

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

    async def get_sequence(self, uniprot_id: str) -> SequenceInfo:
        """Get protein sequence by UniProt ID."""
        url = f"{self.BASE_URL}/uniprotkb/{uniprot_id}.json"

        try:
            response = await self._client.get(url)

            if response.status_code == 404:
                raise SequenceNotFoundError(uniprot_id)

            response.raise_for_status()
            data = response.json()

            # Extract sequence
            sequence = data.get("sequence", {}).get("value", "")

            # Extract protein name
            protein_name = ""
            if "proteinDescription" in data:
                rec_name = data["proteinDescription"].get("recommendedName", {})
                if rec_name:
                    protein_name = rec_name.get("fullName", {}).get("value", "")

            # Extract organism
            organism = ""
            if "organism" in data:
                organism = data["organism"].get("scientificName", "")

            # Extract gene name
            gene_name = None
            if "genes" in data and data["genes"]:
                gene_name = data["genes"][0].get("geneName", {}).get("value")

            # Extract function
            function = None
            for comment in data.get("comments", []):
                if comment.get("commentType") == "FUNCTION":
                    texts = comment.get("texts", [])
                    if texts:
                        function = texts[0].get("value")
                    break

            # Extract PDB cross-references
            pdb_ids = []
            for xref in data.get("uniProtKBCrossReferences", []):
                if xref.get("database") == "PDB":
                    pdb_ids.append(xref.get("id"))

            return SequenceInfo(
                uniprot_id=uniprot_id,
                name=protein_name,
                sequence=sequence,
                organism=organism,
                gene_name=gene_name,
                function=function,
                pdb_ids=pdb_ids,
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SequenceNotFoundError(uniprot_id)
            raise

    async def search_sequences(
        self,
        query: str,
        organism: Optional[str] = None,
        max_results: int = 10,
    ) -> list[SequenceInfo]:
        """Search for protein sequences."""
        # Build query
        search_query = query
        if organism:
            search_query = f"{query} AND organism_name:{organism}"

        url = f"{self.BASE_URL}/uniprotkb/search"
        params = {
            "query": search_query,
            "format": "json",
            "size": max_results,
            "fields": "accession,protein_name,organism_name,gene_names,sequence",
        }

        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
        except HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {url}")
            return []
        except TimeoutException:
            logger.error(f"Request timed out: {url}")
            return []
        except ConnectError as e:
            logger.error(f"Connection failed: {e}")
            return []

        try:
            data = response.json()
        except JSONDecodeError as e:
            logger.error(f"Invalid JSON response from {url}: {e}")
            return []

        results = []
        for entry in data.get("results", []):
            # Extract protein name
            protein_name = ""
            if "proteinDescription" in entry:
                rec_name = entry["proteinDescription"].get("recommendedName", {})
                if rec_name:
                    protein_name = rec_name.get("fullName", {}).get("value", "")

            # Extract gene name
            gene_name = None
            if "genes" in entry and entry["genes"]:
                gene_name = entry["genes"][0].get("geneName", {}).get("value")

            results.append(
                SequenceInfo(
                    uniprot_id=entry.get("primaryAccession", ""),
                    name=protein_name,
                    sequence=entry.get("sequence", {}).get("value", ""),
                    organism=entry.get("organism", {}).get("scientificName", ""),
                    gene_name=gene_name,
                )
            )

        return results

    async def get_pdb_mapping(self, uniprot_id: str) -> list[str]:
        """Get PDB IDs mapped to a UniProt accession."""
        try:
            info = await self.get_sequence(uniprot_id)
            return info.pdb_ids
        except SequenceNotFoundError:
            return []

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
