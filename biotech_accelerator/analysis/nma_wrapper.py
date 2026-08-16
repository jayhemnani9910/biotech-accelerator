"""
Wrapper around nobel-dataintelligence NMA (Normal Mode Analysis).

This module provides a clean interface to the ANM/GNM analysis
from the nobel-dataintelligence project.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np

from ..domain.protein_models import FlexibilityMetrics, NMAResult

logger = logging.getLogger(__name__)

# Add nobel-dataintelligence to path if not installed
NOBEL_PATH = Path.home() / "jh-core" / "projects" / "nobel_dataintelligence"
if NOBEL_PATH.exists() and str(NOBEL_PATH) not in sys.path:
    sys.path.insert(0, str(NOBEL_PATH))


class NMAAnalyzer:
    """
    Normal Mode Analysis wrapper.

    Uses ANM (Anisotropic Network Model) from nobel-dataintelligence
    to analyze protein dynamics and flexibility.
    """

    def __init__(self, n_modes: int = 100, cutoff: float = 15.0):
        """
        Initialize NMA analyzer.

        Args:
            n_modes: Number of normal modes to compute (default 100)
            cutoff: Distance cutoff for spring network in Angstroms (default 15.0)
        """
        self.n_modes = n_modes
        self.cutoff = cutoff
        self._prody_available = False
        self._check_dependencies()

    def _check_dependencies(self):
        """Check if ProDy is available."""
        try:
            import prody

            self._prody_available = True
            prody.confProDy(verbosity="none")  # Reduce logging
        except ImportError:
            logger.warning("ProDy not installed. NMA analysis will be limited.")
            self._prody_available = False

    def analyze(self, pdb_path: Path) -> NMAResult:
        """
        Perform Normal Mode Analysis on a protein structure.

        Args:
            pdb_path: Path to PDB file

        Returns:
            NMAResult with eigenvalues, eigenvectors, and flexibility metrics
        """
        if not self._prody_available:
            raise RuntimeError("ProDy is required for NMA analysis")

        import prody

        # Parse structure
        logger.info(f"Loading structure: {pdb_path}")
        structure = prody.parsePDB(str(pdb_path))

        # Get C-alpha atoms for coarse-grained analysis
        calphas = structure.select("calpha")
        if calphas is None:
            raise ValueError(f"No C-alpha atoms found in {pdb_path}")

        n_atoms = len(calphas)
        logger.info(f"Found {n_atoms} C-alpha atoms")

        # Deposited numbering — index i of every array below is resnums[i], which
        # is NOT i itself for any structure with gaps or multiple chains.
        resnums = calphas.getResnums()
        chain_ids = calphas.getChids()

        # Build ANM model
        anm = prody.ANM(f"ANM_{pdb_path.stem}")
        anm.buildHessian(calphas, cutoff=self.cutoff)

        # Calculate modes
        n_modes = min(self.n_modes, 3 * n_atoms - 6)
        anm.calcModes(n_modes=n_modes)

        # Extract results
        eigenvalues = anm.getEigvals()
        eigenvectors = anm.getEigvecs()

        # Calculate per-residue fluctuations (B-factors)
        fluctuations = prody.calcSqFlucts(anm)

        # Calculate collectivity for each mode
        collectivity = np.array([prody.calcCollectivity(anm[i]) for i in range(len(anm))])

        # Calculate vibrational entropy
        temp = 300  # Kelvin
        kb = 0.001987  # kcal/(mol·K)

        # S_vib = kb * sum(ln(eigenvalue))
        positive_eigenvalues = eigenvalues[eigenvalues > 0]
        vibrational_entropy = kb * temp * np.sum(np.log(positive_eigenvalues))

        # Identify flexible and rigid regions
        flexibility = self._analyze_flexibility(fluctuations, resnums, chain_ids)

        pdb_id = pdb_path.stem.upper()[:4]

        return NMAResult(
            pdb_id=pdb_id,
            n_modes=n_modes,
            eigenvalues=eigenvalues,
            eigenvectors=eigenvectors,
            fluctuations=fluctuations,
            collectivity=collectivity,
            vibrational_entropy=vibrational_entropy,
            flexibility=flexibility,
            residue_numbers=[int(r) for r in resnums],
            chain_ids=[str(c) for c in chain_ids],
        )

    def _analyze_flexibility(
        self,
        fluctuations: np.ndarray,
        resnums: np.ndarray,
        chain_ids: np.ndarray,
        threshold_high: float = 1.5,
        threshold_low: float = 0.5,
        min_region_size: int = 3,
    ) -> FlexibilityMetrics:
        """
        Analyze flexibility from fluctuation profile.

        Args:
            fluctuations: Per-residue fluctuations, in Ca-array order
            resnums: Deposited residue number for each entry in `fluctuations`
            chain_ids: Chain ID for each entry in `fluctuations`
            threshold_high: Multiplier of mean for flexible regions
            threshold_low: Multiplier of mean for rigid regions
            min_region_size: Minimum consecutive residues for a region

        Returns:
            FlexibilityMetrics, with every position expressed as a deposited
            residue number rather than an index into the Ca array.
        """
        mean_fluct = np.mean(fluctuations)
        normalized = fluctuations / mean_fluct

        # Find flexible regions (above threshold)
        flexible_mask = normalized > threshold_high
        flexible_regions = self._find_regions(flexible_mask, resnums, chain_ids, min_region_size)

        # Find rigid regions (below threshold)
        rigid_mask = normalized < threshold_low
        rigid_regions = self._find_regions(rigid_mask, resnums, chain_ids, min_region_size)

        # Find hinge residues (high gradient in fluctuation)
        gradient = np.abs(np.gradient(normalized))
        hinge_threshold = np.percentile(gradient, 90)
        hinge_residues = [int(resnums[i]) for i in np.where(gradient > hinge_threshold)[0]]

        return FlexibilityMetrics(
            mean_fluctuation=float(mean_fluct),
            max_fluctuation=float(np.max(fluctuations)),
            flexible_regions=flexible_regions,
            rigid_regions=rigid_regions,
            hinge_residues=hinge_residues,
        )

    @staticmethod
    def _find_regions(
        mask: np.ndarray,
        resnums: np.ndarray,
        chain_ids: np.ndarray,
        min_size: int,
    ) -> list[tuple[int, int]]:
        """Find contiguous regions in a boolean mask, as (start, end) resnum pairs.

        A run is broken not only where the mask goes false, but also where the
        structure itself is discontinuous — an unresolved stretch (resnum jump)
        or a chain boundary. Without that, a reported span would cover residues
        that are not in the region, or not even in the same chain.
        """
        regions: list[tuple[int, int]] = []
        start: Optional[int] = None

        def close(begin: int, end_exclusive: int) -> None:
            if end_exclusive - begin >= min_size:
                regions.append((int(resnums[begin]), int(resnums[end_exclusive - 1])))

        for i, val in enumerate(mask):
            adjacent = (
                i > 0 and resnums[i] == resnums[i - 1] + 1 and chain_ids[i] == chain_ids[i - 1]
            )
            if not val:
                if start is not None:
                    close(start, i)
                    start = None
            elif start is None:
                start = i
            elif not adjacent:
                close(start, i)
                start = i

        if start is not None:
            close(start, len(mask))

        return regions

    async def analyze_async(self, pdb_path: Path) -> NMAResult:
        """Async wrapper for analyze (runs in thread pool)."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.analyze, pdb_path)
