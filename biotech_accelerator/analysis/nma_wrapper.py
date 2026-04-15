"""
Wrapper around nobel-dataintelligence NMA (Normal Mode Analysis).

This module provides a clean interface to the ANM/GNM analysis
from the nobel-dataintelligence project.
"""

import logging
import sys
from pathlib import Path

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
        flexibility = self._analyze_flexibility(fluctuations)

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
        )

    def _analyze_flexibility(
        self,
        fluctuations: np.ndarray,
        threshold_high: float = 1.5,
        threshold_low: float = 0.5,
        min_region_size: int = 3,
    ) -> FlexibilityMetrics:
        """
        Analyze flexibility from fluctuation profile.

        Args:
            fluctuations: Per-residue fluctuations
            threshold_high: Multiplier of mean for flexible regions
            threshold_low: Multiplier of mean for rigid regions
            min_region_size: Minimum consecutive residues for a region

        Returns:
            FlexibilityMetrics
        """
        mean_fluct = np.mean(fluctuations)
        normalized = fluctuations / mean_fluct

        # Find flexible regions (above threshold)
        flexible_mask = normalized > threshold_high
        flexible_regions = self._find_regions(flexible_mask, min_region_size)

        # Find rigid regions (below threshold)
        rigid_mask = normalized < threshold_low
        rigid_regions = self._find_regions(rigid_mask, min_region_size)

        # Find hinge residues (high gradient in fluctuation)
        gradient = np.abs(np.gradient(normalized))
        hinge_threshold = np.percentile(gradient, 90)
        hinge_residues = list(np.where(gradient > hinge_threshold)[0])

        return FlexibilityMetrics(
            mean_fluctuation=float(mean_fluct),
            max_fluctuation=float(np.max(fluctuations)),
            flexible_regions=flexible_regions,
            rigid_regions=rigid_regions,
            hinge_residues=hinge_residues,
        )

    def _find_regions(
        self,
        mask: np.ndarray,
        min_size: int,
    ) -> list[tuple[int, int]]:
        """Find contiguous regions in a boolean mask."""
        regions = []
        in_region = False
        start = 0

        for i, val in enumerate(mask):
            if val and not in_region:
                start = i
                in_region = True
            elif not val and in_region:
                if i - start >= min_size:
                    regions.append((start, i - 1))
                in_region = False

        # Handle region at end
        if in_region and len(mask) - start >= min_size:
            regions.append((start, len(mask) - 1))

        return regions

    async def analyze_async(self, pdb_path: Path) -> NMAResult:
        """Async wrapper for analyze (runs in thread pool)."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.analyze, pdb_path)
