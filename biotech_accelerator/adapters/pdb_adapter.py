"""PDB (Protein Data Bank) adapter for fetching protein structures."""

import gzip
import logging
import re
from json import JSONDecodeError
from pathlib import Path
from typing import Optional

import httpx
from httpx import ConnectError, HTTPStatusError, TimeoutException

from ..domain.protein_models import PDBStructure, ProteinInfo, ProteinSource
from ..ports.structure import StructureNotFoundError, StructurePort

logger = logging.getLogger(__name__)

# PDB ID format: 4 characters, starting with a digit
PDB_ID_PATTERN = re.compile(r"^[0-9][A-Za-z0-9]{3}$")


class PDBAdapter(StructurePort):
    """
    Adapter for the RCSB Protein Data Bank.

    Fetches protein structures and metadata from rcsb.org.
    """

    BASE_URL = "https://files.rcsb.org/download"
    SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize PDB adapter.

        Args:
            cache_dir: Directory to cache downloaded structures.
                      Defaults to ~/.biotech-accelerator/pdb_cache
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".biotech-accelerator" / "pdb_cache"

        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
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

    def get_cache_dir(self) -> Path:
        return self._cache_dir

    async def fetch_structure(self, pdb_id: str) -> PDBStructure:
        """Fetch a protein structure by PDB ID."""
        pdb_id = pdb_id.upper().strip()

        if not PDB_ID_PATTERN.match(pdb_id):
            raise ValueError(
                f"Invalid PDB ID format: {pdb_id}. Must be 4 characters starting with digit."
            )

        # Get file path (download if needed)
        file_path = await self.get_structure_file(pdb_id)

        # Fetch metadata
        metadata = await self._fetch_metadata(pdb_id)

        return PDBStructure(
            pdb_id=pdb_id,
            file_path=file_path,
            resolution=metadata.get("resolution"),
            method=metadata.get("method"),
            chain_ids=metadata.get("chain_ids", []),
            num_residues=metadata.get("num_residues", 0),
            source=ProteinSource.PDB,
        )

    async def get_structure_file(self, pdb_id: str) -> Path:
        """Get local file path for PDB structure, downloading if needed."""
        pdb_id = pdb_id.upper().strip()
        local_path = self._cache_dir / f"{pdb_id}.pdb"

        if local_path.exists():
            logger.debug(f"Using cached structure: {local_path}")
            return local_path

        # Download the structure
        await self._download_structure(pdb_id, local_path)
        return local_path

    async def _download_structure(self, pdb_id: str, local_path: Path) -> None:
        """Download PDB structure file."""
        # Try .pdb.gz first (compressed)
        url = f"{self.BASE_URL}/{pdb_id}.pdb.gz"
        logger.info(f"Downloading structure: {url}")

        try:
            response = await self._client.get(url)

            if response.status_code == 404:
                # Try .pdb (uncompressed)
                url = f"{self.BASE_URL}/{pdb_id}.pdb"
                response = await self._client.get(url)

            response.raise_for_status()

            # Handle gzipped content
            if url.endswith(".gz"):
                content = gzip.decompress(response.content)
            else:
                content = response.content

            local_path.write_bytes(content)
            logger.info(f"Downloaded structure to: {local_path}")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise StructureNotFoundError(pdb_id)
            raise

    async def _fetch_metadata(self, pdb_id: str) -> dict:
        """Fetch structure metadata from RCSB GraphQL API."""
        graphql_url = "https://data.rcsb.org/graphql"

        query = """
        query getStructure($pdb_id: String!) {
            entry(entry_id: $pdb_id) {
                rcsb_entry_info {
                    resolution_combined
                    experimental_method
                    deposited_polymer_entity_instance_count
                }
                polymer_entities {
                    rcsb_polymer_entity {
                        pdbx_number_of_molecules
                    }
                    entity_poly {
                        pdbx_seq_one_letter_code_can
                    }
                }
                struct {
                    title
                }
            }
        }
        """

        try:
            response = await self._client.post(
                graphql_url,
                json={"query": query, "variables": {"pdb_id": pdb_id}},
            )
            response.raise_for_status()
        except HTTPStatusError as e:
            logger.warning(f"HTTP error {e.response.status_code} fetching metadata for {pdb_id}")
            return {}
        except TimeoutException:
            logger.warning(f"Request timed out fetching metadata for {pdb_id}")
            return {}
        except ConnectError as e:
            logger.warning(f"Connection failed fetching metadata for {pdb_id}: {e}")
            return {}

        try:
            data = response.json()
        except JSONDecodeError as e:
            logger.warning(f"Invalid JSON response for metadata {pdb_id}: {e}")
            return {}

        entry = data.get("data", {}).get("entry")
        if not entry:
            return {}

        info = entry.get("rcsb_entry_info", {})

        # Get chain IDs (approximate)
        chain_ids = []
        num_residues = 0
        for entity in entry.get("polymer_entities", []):
            poly = entity.get("entity_poly", {})
            seq = poly.get("pdbx_seq_one_letter_code_can", "")
            num_residues += len(seq)

        return {
            "resolution": info.get("resolution_combined", [None])[0]
            if info.get("resolution_combined")
            else None,
            "method": info.get("experimental_method"),
            "chain_ids": chain_ids,
            "num_residues": num_residues,
            "title": entry.get("struct", {}).get("title"),
        }

    async def search_structures(
        self,
        query: str,
        max_results: int = 10,
        resolution_cutoff: Optional[float] = 2.5,
    ) -> list[ProteinInfo]:
        """Search for protein structures by keyword."""
        # Build RCSB search query
        search_query = {
            "query": {
                "type": "group",
                "logical_operator": "and",
                "nodes": [
                    {
                        "type": "terminal",
                        "service": "full_text",
                        "parameters": {"value": query},
                    }
                ],
            },
            "return_type": "entry",
            "request_options": {
                "paginate": {"start": 0, "rows": max_results},
                "sort": [{"sort_by": "score", "direction": "desc"}],
            },
        }

        # Add resolution filter if specified
        if resolution_cutoff is not None:
            search_query["query"]["nodes"].append(
                {
                    "type": "terminal",
                    "service": "text",
                    "parameters": {
                        "attribute": "rcsb_entry_info.resolution_combined",
                        "operator": "less_or_equal",
                        "value": resolution_cutoff,
                    },
                }
            )

        try:
            response = await self._client.post(self.SEARCH_URL, json=search_query)
            response.raise_for_status()
        except HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for PDB search")
            return []
        except TimeoutException:
            logger.error("Request timed out for PDB search")
            return []
        except ConnectError as e:
            logger.error(f"Connection failed for PDB search: {e}")
            return []

        try:
            data = response.json()
        except JSONDecodeError as e:
            logger.error(f"Invalid JSON response from PDB search: {e}")
            return []

        results = []
        for hit in data.get("result_set", []):
            pdb_id = hit.get("identifier", "")
            results.append(
                ProteinInfo(
                    name=pdb_id,  # Will be enriched with title later
                    pdb_id=pdb_id,
                )
            )

        return results

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
