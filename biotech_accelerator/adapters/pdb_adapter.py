"""PDB (Protein Data Bank) adapter for fetching protein structures."""

import gzip
import logging
import re
from pathlib import Path
from typing import Optional

import httpx

from ..domain.protein_models import PDBStructure, ProteinInfo, ProteinSource
from ..ports.structure import StructureNotFoundError
from .base import AdapterNotFound, BaseAdapter

logger = logging.getLogger(__name__)

PDB_ID_PATTERN = re.compile(r"^[0-9][A-Za-z0-9]{3}$")


class PDBAdapter(BaseAdapter):
    """Adapter for the RCSB Protein Data Bank."""

    BASE_URL = "https://files.rcsb.org/download"
    SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"

    def __init__(self, cache_dir: Optional[Path] = None):
        super().__init__()
        if cache_dir is None:
            cache_dir = Path.home() / ".biotech-accelerator" / "pdb_cache"
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_dir(self) -> Path:
        return self._cache_dir

    async def fetch_structure(self, pdb_id: str) -> PDBStructure:
        """Fetch a protein structure by PDB ID."""
        pdb_id = pdb_id.upper().strip()

        if not PDB_ID_PATTERN.match(pdb_id):
            raise ValueError(
                f"Invalid PDB ID format: {pdb_id}. Must be 4 characters starting with digit."
            )

        file_path = await self.get_structure_file(pdb_id)
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

        await self._download_structure(pdb_id, local_path)
        return local_path

    async def _download_structure(self, pdb_id: str, local_path: Path) -> None:
        """Download PDB structure file (binary/gzip, outside the JSON retry path)."""
        url = f"{self.BASE_URL}/{pdb_id}.pdb.gz"
        logger.info(f"Downloading structure: {url}")

        try:
            response = await self._client.get(url)

            if response.status_code == 404:
                url = f"{self.BASE_URL}/{pdb_id}.pdb"
                response = await self._client.get(url)

            response.raise_for_status()

            if url.endswith(".gz"):
                content = gzip.decompress(response.content)
            else:
                content = response.content

            local_path.write_bytes(content)
            logger.info(f"Downloaded structure to: {local_path}")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise StructureNotFoundError(pdb_id) from e
            raise

    async def _fetch_metadata(self, pdb_id: str) -> dict:
        """Fetch structure metadata from RCSB GraphQL API."""
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
            data = await self._post_json(
                "https://data.rcsb.org/graphql",
                json={"query": query, "variables": {"pdb_id": pdb_id}},
            )
        except AdapterNotFound:
            return {}

        entry = data.get("data", {}).get("entry")
        if not entry:
            return {}

        info = entry.get("rcsb_entry_info", {})
        num_residues = 0
        for entity in entry.get("polymer_entities", []):
            seq = entity.get("entity_poly", {}).get("pdbx_seq_one_letter_code_can", "")
            num_residues += len(seq)

        return {
            "resolution": info.get("resolution_combined", [None])[0]
            if info.get("resolution_combined")
            else None,
            "method": info.get("experimental_method"),
            "chain_ids": [],
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
        nodes: list[dict] = [
            {
                "type": "terminal",
                "service": "full_text",
                "parameters": {"value": query},
            }
        ]
        search_query: dict = {
            "query": {
                "type": "group",
                "logical_operator": "and",
                "nodes": nodes,
            },
            "return_type": "entry",
            "request_options": {
                "paginate": {"start": 0, "rows": max_results},
                "sort": [{"sort_by": "score", "direction": "desc"}],
            },
        }

        if resolution_cutoff is not None:
            nodes.append(
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
            data = await self._post_json(self.SEARCH_URL, json=search_query)
        except AdapterNotFound:
            return []

        return [
            ProteinInfo(name=hit.get("identifier", ""), pdb_id=hit.get("identifier", ""))
            for hit in data.get("result_set", [])
        ]
