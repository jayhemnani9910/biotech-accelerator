"""ChEMBL adapter for drug/compound data."""

import logging
from typing import Optional

from ..domain.compound_models import CompoundInfo
from ..ports.compound import BioactivityData
from ..utils.cache import get_cache
from .base import AdapterError, AdapterNotFound, BaseAdapter

logger = logging.getLogger(__name__)


class CompoundNotFoundError(Exception):
    """Raised when a compound cannot be found in ChEMBL."""

    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"Compound not found: {identifier}")


class ChEMBLAdapter(BaseAdapter):
    """Adapter for ChEMBL drug database."""

    BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"

    def __init__(self):
        super().__init__()
        self._cache = get_cache()

    async def get_compound(self, identifier: str) -> CompoundInfo:
        """Get compound by ChEMBL ID or name."""
        if identifier.upper().startswith("CHEMBL"):
            return await self._get_by_chembl_id(identifier.upper())
        return await self._search_by_name(identifier)

    async def _get_by_chembl_id(self, chembl_id: str) -> CompoundInfo:
        """Get compound by ChEMBL ID."""
        url = f"{self.BASE_URL}/molecule/{chembl_id}.json"
        try:
            data = await self._get_json(url)
        except AdapterNotFound as e:
            raise CompoundNotFoundError(chembl_id) from e
        return self._parse_molecule(data)

    async def _search_by_name(self, name: str) -> CompoundInfo:
        """Search for compound by name."""
        url = f"{self.BASE_URL}/molecule/search.json"
        try:
            data = await self._get_json(url, params={"q": name, "limit": 1})
        except AdapterNotFound as e:
            raise CompoundNotFoundError(name) from e

        molecules = data.get("molecules", [])
        if not molecules:
            raise CompoundNotFoundError(name)
        return self._parse_molecule(molecules[0])

    def _parse_molecule(self, data: dict) -> CompoundInfo:
        """Parse ChEMBL molecule response."""
        props = data.get("molecule_properties", {}) or {}
        structures = data.get("molecule_structures", {}) or {}
        name = data.get("pref_name") or data.get("molecule_chembl_id", "Unknown")

        return CompoundInfo(
            name=name,
            chembl_id=data.get("molecule_chembl_id"),
            smiles=structures.get("canonical_smiles"),
            inchi=structures.get("standard_inchi"),
            molecular_weight=float(props.get("full_mwt", 0)) if props.get("full_mwt") else None,
            logp=float(props.get("alogp", 0)) if props.get("alogp") else None,
        )

    async def search_by_target(
        self,
        target_name: str,
        activity_type: Optional[str] = None,
        max_results: int = 20,
    ) -> list[BioactivityData]:
        """Search for compounds active against a target."""
        target = await self._find_target(target_name)
        if not target:
            logger.warning(f"Target not found: {target_name}")
            return []

        target_chembl_id = target.get("target_chembl_id")
        target_pref_name = target.get("pref_name", target_name)

        params = {
            "target_chembl_id": target_chembl_id,
            "limit": max_results,
            "order_by": "standard_value",
        }
        if activity_type:
            params["standard_type"] = activity_type.upper()
        else:
            params["standard_type__in"] = "IC50,Ki,Kd,EC50"

        try:
            data = await self._get_json(f"{self.BASE_URL}/activity.json", params=params)
        except AdapterNotFound:
            return []

        results = []
        for act in data.get("activities", []):
            if not act.get("molecule_chembl_id") or not act.get("standard_value"):
                continue

            compound = CompoundInfo(
                name=act.get("molecule_pref_name") or act.get("molecule_chembl_id"),
                chembl_id=act.get("molecule_chembl_id"),
                smiles=act.get("canonical_smiles"),
            )
            results.append(
                BioactivityData(
                    compound=compound,
                    target_name=target_pref_name,
                    target_uniprot=act.get("target_components", [{}])[0].get("accession")
                    if target.get("target_components")
                    else None,
                    activity_type=act.get("standard_type", ""),
                    activity_value=float(act.get("standard_value", 0)),
                    activity_unit=act.get("standard_units", "nM"),
                    assay_type=act.get("assay_type"),
                )
            )

        results.sort(key=lambda x: x.activity_value)
        return results[:max_results]

    async def _find_target(self, target_name: str) -> Optional[dict]:
        """Find target by name or UniProt ID. Returns None if not found."""
        cache_key = f"target:{target_name.lower()}"
        cached = self._cache.get("chembl", cache_key)
        if cached is not None:
            return cached if cached != "NOT_FOUND" else None

        # Try by name
        try:
            data = await self._get_json(
                f"{self.BASE_URL}/target/search.json",
                params={"q": target_name, "limit": 5},
            )
        except AdapterNotFound:
            data = {}

        targets = data.get("targets", [])
        if targets:
            self._cache.set("chembl", cache_key, targets[0], ttl=86400)
            return targets[0]

        # Try as UniProt ID
        try:
            data = await self._get_json(
                f"{self.BASE_URL}/target.json",
                params={"target_components__accession": target_name, "limit": 1},
            )
        except AdapterNotFound:
            data = {}

        targets = data.get("targets", [])
        result = targets[0] if targets else None
        self._cache.set("chembl", cache_key, result if result else "NOT_FOUND", ttl=86400)
        return result

    async def get_bioactivity(
        self,
        compound_id: str,
        target: Optional[str] = None,
    ) -> list[BioactivityData]:
        """Get bioactivity data for a compound."""
        params = {"molecule_chembl_id": compound_id.upper(), "limit": 100}

        if target:
            target_data = await self._find_target(target)
            if target_data:
                params["target_chembl_id"] = target_data.get("target_chembl_id")

        try:
            data = await self._get_json(f"{self.BASE_URL}/activity.json", params=params)
        except AdapterNotFound:
            return []

        results = []
        for act in data.get("activities", []):
            if not act.get("standard_value"):
                continue
            compound = CompoundInfo(
                name=act.get("molecule_pref_name") or compound_id,
                chembl_id=compound_id,
            )
            results.append(
                BioactivityData(
                    compound=compound,
                    target_name=act.get("target_pref_name", "Unknown"),
                    target_uniprot=act.get("target_organism"),
                    activity_type=act.get("standard_type", ""),
                    activity_value=float(act.get("standard_value", 0)),
                    activity_unit=act.get("standard_units", "nM"),
                    assay_type=act.get("assay_type"),
                )
            )
        return results

    async def search_similar(
        self,
        smiles: str,
        similarity_threshold: float = 0.7,
        max_results: int = 20,
    ) -> list[CompoundInfo]:
        """Search for similar compounds by structure."""
        url = f"{self.BASE_URL}/similarity/{smiles}/{int(similarity_threshold * 100)}.json"
        try:
            data = await self._get_json(url, params={"limit": max_results})
        except AdapterNotFound:
            return []
        return [self._parse_molecule(mol) for mol in data.get("molecules", [])]

    async def get_approved_drugs_for_target(
        self,
        target_name: str,
        max_results: int = 10,
    ) -> list[CompoundInfo]:
        """Get approved drugs that target a specific protein."""
        target = await self._find_target(target_name)
        if not target:
            return []

        try:
            data = await self._get_json(
                f"{self.BASE_URL}/mechanism.json",
                params={"target_chembl_id": target.get("target_chembl_id"), "limit": max_results},
            )
        except AdapterNotFound:
            return []

        compounds = []
        for mech in data.get("mechanisms", []):
            chembl_id = mech.get("molecule_chembl_id")
            if chembl_id:
                try:
                    compound = await self._get_by_chembl_id(chembl_id)
                    compounds.append(compound)
                except (CompoundNotFoundError, AdapterError):
                    continue
        return compounds[:max_results]
