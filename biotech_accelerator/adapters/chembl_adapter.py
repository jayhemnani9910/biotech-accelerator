"""ChEMBL adapter for drug/compound data."""

import logging
from json import JSONDecodeError
from typing import Optional

import httpx
from httpx import ConnectError, HTTPStatusError, TimeoutException

from ..domain.compound_models import CompoundInfo
from ..ports.compound import BioactivityData, CompoundPort
from ..utils.cache import get_cache

logger = logging.getLogger(__name__)


class ChEMBLAdapter(CompoundPort):
    """
    Adapter for ChEMBL drug database.

    Provides access to compound data, bioactivity measurements,
    and target-based drug discovery data.
    """

    BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        self._cache = get_cache()

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

    async def get_compound(self, identifier: str) -> CompoundInfo:
        """
        Get compound by ChEMBL ID or name.

        Args:
            identifier: ChEMBL ID (e.g., CHEMBL25) or compound name

        Returns:
            CompoundInfo with structure and properties
        """
        # Check if it's a ChEMBL ID
        if identifier.upper().startswith("CHEMBL"):
            return await self._get_by_chembl_id(identifier.upper())
        else:
            # Search by name
            return await self._search_by_name(identifier)

    async def _get_by_chembl_id(self, chembl_id: str) -> CompoundInfo:
        """Get compound by ChEMBL ID."""
        url = f"{self.BASE_URL}/molecule/{chembl_id}.json"

        try:
            response = await self._client.get(url)
            response.raise_for_status()
            data = response.json()

            return self._parse_molecule(data)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Compound not found: {chembl_id}")
            raise

    async def _search_by_name(self, name: str) -> CompoundInfo:
        """Search for compound by name."""
        url = f"{self.BASE_URL}/molecule/search.json"
        params = {"q": name, "limit": 1}

        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
        except HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {url}")
            raise ValueError(f"Compound not found: {name}")
        except TimeoutException:
            logger.error(f"Request timed out: {url}")
            raise ValueError(f"Compound not found: {name}")
        except ConnectError as e:
            logger.error(f"Connection failed: {e}")
            raise ValueError(f"Compound not found: {name}")

        try:
            data = response.json()
        except JSONDecodeError as e:
            logger.error(f"Invalid JSON response from {url}: {e}")
            raise ValueError(f"Compound not found: {name}")

        molecules = data.get("molecules", [])
        if not molecules:
            raise ValueError(f"Compound not found: {name}")

        return self._parse_molecule(molecules[0])

    def _parse_molecule(self, data: dict) -> CompoundInfo:
        """Parse ChEMBL molecule response."""
        props = data.get("molecule_properties", {}) or {}
        structures = data.get("molecule_structures", {}) or {}

        # Get preferred name
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
        """
        Search for compounds active against a target.

        Args:
            target_name: Target protein name (e.g., "EGFR") or UniProt ID
            activity_type: Filter by IC50, Ki, Kd, EC50
            max_results: Maximum results

        Returns:
            List of bioactivity data sorted by potency
        """
        # First, find the target
        target = await self._find_target(target_name)
        if not target:
            logger.warning(f"Target not found: {target_name}")
            return []

        target_chembl_id = target.get("target_chembl_id")
        target_pref_name = target.get("pref_name", target_name)

        # Get activities for this target
        url = f"{self.BASE_URL}/activity.json"
        params = {
            "target_chembl_id": target_chembl_id,
            "limit": max_results,
            "order_by": "standard_value",  # Sort by activity value
        }

        if activity_type:
            params["standard_type"] = activity_type.upper()
        else:
            # Default to IC50 as most common
            params["standard_type__in"] = "IC50,Ki,Kd,EC50"

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

        activities = data.get("activities", [])
        results = []

        for act in activities:
            # Skip if no compound or activity value
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
                    target_uniprot=target.get("target_components", [{}])[0].get("accession")
                    if target.get("target_components")
                    else None,
                    activity_type=act.get("standard_type", ""),
                    activity_value=float(act.get("standard_value", 0)),
                    activity_unit=act.get("standard_units", "nM"),
                    assay_type=act.get("assay_type"),
                )
            )

        # Sort by activity value (lower is more potent)
        results.sort(key=lambda x: x.activity_value)

        return results[:max_results]

    async def _find_target(self, target_name: str) -> Optional[dict]:
        """Find target by name or UniProt ID."""
        # Check cache first
        cache_key = f"target:{target_name.lower()}"
        cached = self._cache.get("chembl", cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for target: {target_name}")
            return cached if cached != "NOT_FOUND" else None

        # Try searching by name first
        url = f"{self.BASE_URL}/target/search.json"
        params = {"q": target_name, "limit": 5}

        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
        except HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {url}")
            return None
        except TimeoutException:
            logger.error(f"Request timed out: {url}")
            return None
        except ConnectError as e:
            logger.error(f"Connection failed: {e}")
            return None

        try:
            data = response.json()
        except JSONDecodeError as e:
            logger.error(f"Invalid JSON response from {url}: {e}")
            return None

        targets = data.get("targets", [])
        if targets:
            # Cache and return first match
            self._cache.set("chembl", cache_key, targets[0], ttl=86400)  # 24h
            return targets[0]

        # If not found, try as UniProt ID
        url = f"{self.BASE_URL}/target.json"
        params = {"target_components__accession": target_name, "limit": 1}

        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
        except HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {url}")
            return None
        except TimeoutException:
            logger.error(f"Request timed out: {url}")
            return None
        except ConnectError as e:
            logger.error(f"Connection failed: {e}")
            return None

        try:
            data = response.json()
        except JSONDecodeError as e:
            logger.error(f"Invalid JSON response from {url}: {e}")
            return None

        targets = data.get("targets", [])
        result = targets[0] if targets else None

        # Cache result (or "NOT_FOUND" if not found)
        self._cache.set("chembl", cache_key, result if result else "NOT_FOUND", ttl=86400)
        return result

    async def get_bioactivity(
        self,
        compound_id: str,
        target: Optional[str] = None,
    ) -> list[BioactivityData]:
        """
        Get bioactivity data for a compound.

        Args:
            compound_id: ChEMBL ID
            target: Optional target filter

        Returns:
            List of bioactivity measurements
        """
        url = f"{self.BASE_URL}/activity.json"
        params = {
            "molecule_chembl_id": compound_id.upper(),
            "limit": 100,
        }

        if target:
            # First find target ChEMBL ID
            target_data = await self._find_target(target)
            if target_data:
                params["target_chembl_id"] = target_data.get("target_chembl_id")

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

        activities = data.get("activities", [])
        results = []

        for act in activities:
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
        """
        Search for similar compounds by structure.

        Args:
            smiles: SMILES string
            similarity_threshold: Tanimoto similarity (0.7 = 70%)
            max_results: Maximum results

        Returns:
            List of similar compounds
        """
        url = f"{self.BASE_URL}/similarity/{smiles}/{int(similarity_threshold * 100)}.json"
        params = {"limit": max_results}

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

        molecules = data.get("molecules", [])
        return [self._parse_molecule(mol) for mol in molecules]

    async def get_approved_drugs_for_target(
        self,
        target_name: str,
        max_results: int = 10,
    ) -> list[CompoundInfo]:
        """
        Get approved drugs that target a specific protein.

        Args:
            target_name: Target protein name
            max_results: Maximum results

        Returns:
            List of approved drugs
        """
        # Find target
        target = await self._find_target(target_name)
        if not target:
            return []

        target_chembl_id = target.get("target_chembl_id")

        # Search for approved drugs with activity
        url = f"{self.BASE_URL}/mechanism.json"
        params = {
            "target_chembl_id": target_chembl_id,
            "limit": max_results,
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

        mechanisms = data.get("mechanisms", [])
        compounds = []

        for mech in mechanisms:
            chembl_id = mech.get("molecule_chembl_id")
            if chembl_id:
                try:
                    compound = await self._get_by_chembl_id(chembl_id)
                    compounds.append(compound)
                except (ValueError, HTTPStatusError, TimeoutException, ConnectError):
                    pass

        return compounds[:max_results]

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
