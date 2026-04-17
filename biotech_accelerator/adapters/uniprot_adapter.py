"""UniProt adapter for protein sequences and annotations."""

import logging
from typing import Optional

from ..ports.sequence import SequenceInfo, SequenceNotFoundError
from .base import AdapterNotFound, BaseAdapter

logger = logging.getLogger(__name__)


class UniProtAdapter(BaseAdapter):
    """Adapter for UniProt protein database."""

    BASE_URL = "https://rest.uniprot.org"

    @staticmethod
    def _extract_protein_name(data: dict) -> str:
        """Extract protein name from UniProt entry data."""
        if "proteinDescription" in data:
            rec_name = data["proteinDescription"].get("recommendedName", {})
            if rec_name:
                return rec_name.get("fullName", {}).get("value", "")
        return ""

    @staticmethod
    def _extract_gene_name(data: dict) -> Optional[str]:
        """Extract gene name from UniProt entry data."""
        if "genes" in data and data["genes"]:
            return data["genes"][0].get("geneName", {}).get("value")
        return None

    async def get_sequence(self, uniprot_id: str) -> SequenceInfo:
        """Get protein sequence by UniProt ID."""
        try:
            data = await self._get_json(f"{self.BASE_URL}/uniprotkb/{uniprot_id}.json")
        except AdapterNotFound as e:
            raise SequenceNotFoundError(uniprot_id) from e

        sequence = data.get("sequence", {}).get("value", "")
        protein_name = self._extract_protein_name(data)

        organism = ""
        if "organism" in data:
            organism = data["organism"].get("scientificName", "")

        gene_name = self._extract_gene_name(data)

        function = None
        for comment in data.get("comments", []):
            if comment.get("commentType") == "FUNCTION":
                texts = comment.get("texts", [])
                if texts:
                    function = texts[0].get("value")
                break

        pdb_ids = [
            xref.get("id")
            for xref in data.get("uniProtKBCrossReferences", [])
            if xref.get("database") == "PDB"
        ]

        return SequenceInfo(
            uniprot_id=uniprot_id,
            name=protein_name,
            sequence=sequence,
            organism=organism,
            gene_name=gene_name,
            function=function,
            pdb_ids=pdb_ids,
        )

    async def search_sequences(
        self,
        query: str,
        organism: Optional[str] = None,
        max_results: int = 10,
    ) -> list[SequenceInfo]:
        """Search for protein sequences."""
        search_query = query
        if organism:
            search_query = f"{query} AND organism_name:{organism}"

        try:
            data = await self._get_json(
                f"{self.BASE_URL}/uniprotkb/search",
                params={
                    "query": search_query,
                    "format": "json",
                    "size": max_results,
                    "fields": "accession,protein_name,organism_name,gene_names,sequence",
                },
            )
        except AdapterNotFound:
            return []

        results = []
        for entry in data.get("results", []):
            protein_name = self._extract_protein_name(entry)
            gene_name = self._extract_gene_name(entry)

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
