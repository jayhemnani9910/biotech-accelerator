"""
Structure Analyst Agent

Fetches protein structures and runs Normal Mode Analysis to
understand protein dynamics and flexibility.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ...adapters.pdb_adapter import PDBAdapter
from ...analysis.nma_wrapper import NMAAnalyzer
from ...domain.protein_models import NMAResult, PDBStructure

logger = logging.getLogger(__name__)


@dataclass
class StructureAnalysisResult:
    """Result from structure analysis."""

    pdb_id: str
    structure: PDBStructure
    nma_result: Optional[NMAResult] = None
    summary: str = ""
    error: Optional[str] = None


@dataclass
class StructureAnalystState:
    """State for structure analyst agent."""

    query: str = ""
    pdb_ids: list[str] = field(default_factory=list)
    analysis_results: list[StructureAnalysisResult] = field(default_factory=list)
    error: Optional[str] = None


class StructureAnalystAgent:
    """
    Agent that analyzes protein structures.

    Capabilities:
    - Parse PDB IDs from text
    - Fetch structures from PDB
    - Run ANM/GNM analysis
    - Summarize flexibility and dynamics
    """

    # Common PDB ID pattern
    PDB_ID_PATTERN = re.compile(r"\b([0-9][A-Z0-9]{3})\b", re.IGNORECASE)

    def __init__(
        self,
        pdb_adapter: Optional[PDBAdapter] = None,
        nma_analyzer: Optional[NMAAnalyzer] = None,
    ):
        """
        Initialize agent.

        Args:
            pdb_adapter: PDB structure fetcher (default: creates new)
            nma_analyzer: NMA analyzer (default: creates new)
        """
        self.pdb_adapter = pdb_adapter or PDBAdapter()
        self.nma_analyzer = nma_analyzer or NMAAnalyzer()

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        LangGraph node entry point.

        Args:
            state: Current graph state with 'query' field

        Returns:
            Updated state with structure analysis
        """
        query = state.get("query", "") or state.get("root_query", "")

        # Extract PDB IDs from query
        pdb_ids = self.extract_pdb_ids(query)

        if not pdb_ids:
            logger.warning("No PDB IDs found in query")
            return {
                "structure_analysis": None,
                "structure_error": "No PDB IDs found in query. Please specify a 4-character PDB ID.",
            }

        # Analyze each structure
        results = []
        for pdb_id in pdb_ids:
            result = await self.analyze_structure(pdb_id)
            results.append(result)

        # Generate summary
        summary = self._generate_summary(results)

        return {
            "structure_analysis": results,
            "structure_summary": summary,
            "analyzed_pdb_ids": pdb_ids,
        }

    def extract_pdb_ids(self, text: str) -> list[str]:
        """
        Extract PDB IDs from text.

        Args:
            text: Text that may contain PDB IDs

        Returns:
            List of unique PDB IDs found
        """
        matches = self.PDB_ID_PATTERN.findall(text)
        # Normalize to uppercase and remove duplicates
        return list(dict.fromkeys(m.upper() for m in matches))

    async def analyze_structure(self, pdb_id: str) -> StructureAnalysisResult:
        """
        Fetch and analyze a protein structure.

        Args:
            pdb_id: 4-character PDB ID

        Returns:
            StructureAnalysisResult with structure and NMA data
        """
        try:
            # Fetch structure
            logger.info(f"Fetching structure: {pdb_id}")
            structure = await self.pdb_adapter.fetch_structure(pdb_id)

            # Run NMA analysis
            logger.info(f"Running NMA analysis on {pdb_id}")
            nma_result = await self.nma_analyzer.analyze_async(structure.file_path)

            # Generate summary
            summary = self._summarize_nma(pdb_id, nma_result)

            return StructureAnalysisResult(
                pdb_id=pdb_id,
                structure=structure,
                nma_result=nma_result,
                summary=summary,
            )

        except Exception as e:
            logger.error(f"Failed to analyze {pdb_id}: {e}")
            return StructureAnalysisResult(
                pdb_id=pdb_id,
                structure=None,
                error=str(e),
            )

    def _summarize_nma(self, pdb_id: str, nma: NMAResult) -> str:
        """Generate human-readable summary of NMA results."""
        flex = nma.flexibility

        # Format flexible regions
        flex_regions = (
            ", ".join(
                f"residues {start}-{end}"
                for start, end in flex.flexible_regions[:3]  # Top 3
            )
            or "none identified"
        )

        # Format rigid regions
        rigid_regions = (
            ", ".join(f"residues {start}-{end}" for start, end in flex.rigid_regions[:3])
            or "none identified"
        )

        # Format hinge residues
        hinges = ", ".join(str(r) for r in flex.hinge_residues[:5]) or "none"

        return f"""
## Structure Analysis: {pdb_id}

**Flexibility Profile:**
- Mean fluctuation: {flex.mean_fluctuation:.3f} Å²
- Max fluctuation: {flex.max_fluctuation:.3f} Å²

**Flexible Regions** (high mobility):
{flex_regions}

**Rigid Core Regions** (stable):
{rigid_regions}

**Hinge Residues** (potential motion points):
{hinges}

**Vibrational Entropy**: {nma.vibrational_entropy:.2f} kcal/(mol·K)

**Analysis Notes:**
- Computed {nma.n_modes} normal modes
- Flexible regions may be important for function/binding
- Rigid regions typically form the structural core
- Hinge residues can be targets for engineering stability
""".strip()

    def _generate_summary(self, results: list[StructureAnalysisResult]) -> str:
        """Generate overall summary from multiple analyses."""
        successful = [r for r in results if r.nma_result is not None]
        failed = [r for r in results if r.error is not None]

        parts = []

        if successful:
            parts.append(f"Successfully analyzed {len(successful)} structure(s):\n")
            for r in successful:
                parts.append(r.summary)
                parts.append("\n---\n")

        if failed:
            parts.append(f"\nFailed to analyze {len(failed)} structure(s):")
            for r in failed:
                parts.append(f"- {r.pdb_id}: {r.error}")

        return "\n".join(parts)


# Standalone function for simpler usage
async def analyze_protein_structure(pdb_id: str) -> StructureAnalysisResult:
    """
    Convenience function to analyze a single protein.

    Args:
        pdb_id: 4-character PDB ID

    Returns:
        StructureAnalysisResult
    """
    agent = StructureAnalystAgent()
    return await agent.analyze_structure(pdb_id)
