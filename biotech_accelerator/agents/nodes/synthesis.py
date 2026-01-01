"""
Synthesis Agent

Synthesizes literature evidence with computational structural analysis.
Extracts mutations from papers and cross-references with flexibility data.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from .experiment_suggester import ExperimentSuggester

logger = logging.getLogger(__name__)


@dataclass
class MutationInfo:
    """Information about a mutation mentioned in literature."""

    original: str  # Original amino acid (single letter)
    position: int  # Residue position
    mutant: str  # Mutant amino acid (single letter)
    source: str  # Where it was found (paper title/PMID)
    context: str  # Sentence context


@dataclass
class MutationInsight:
    """Insight from cross-referencing mutation with structure."""

    mutation: MutationInfo
    in_flexible_region: bool
    is_hinge_residue: bool
    flexibility_score: Optional[float]
    recommendation: str


class SynthesisAgent:
    """
    Synthesizes literature + computational evidence.

    Capabilities:
    - Extract mutations from paper abstracts
    - Cross-reference mutations with structural flexibility data
    - Generate actionable insights for protein engineering
    """

    # Multiple patterns to match mutations in various notations
    MUTATION_PATTERNS = [
        # Single letter: A42G, R206W
        re.compile(r"\b([A-Z])(\d+)([A-Z])\b"),
        # Three letter: Ala42Gly (case insensitive)
        re.compile(
            r"\b(Ala|Arg|Asn|Asp|Cys|Gln|Glu|Gly|His|Ile|Leu|Lys|Met|Phe|Pro|Ser|Thr|Trp|Tyr|Val)(\d+)(Ala|Arg|Asn|Asp|Cys|Gln|Glu|Gly|His|Ile|Leu|Lys|Met|Phe|Pro|Ser|Thr|Trp|Tyr|Val)\b",
            re.IGNORECASE,
        ),
        # HGVS notation: p.V600E, p.Ala42Gly
        re.compile(r"p\.([A-Z][a-z]{0,2})(\d+)([A-Z][a-z]{0,2})"),
    ]

    # Three-letter to single-letter conversion
    THREE_TO_ONE = {
        "ala": "A",
        "arg": "R",
        "asn": "N",
        "asp": "D",
        "cys": "C",
        "gln": "Q",
        "glu": "E",
        "gly": "G",
        "his": "H",
        "ile": "I",
        "leu": "L",
        "lys": "K",
        "met": "M",
        "phe": "F",
        "pro": "P",
        "ser": "S",
        "thr": "T",
        "trp": "W",
        "tyr": "Y",
        "val": "V",
    }

    # Legacy alias for backward compatibility
    AA_MAP = THREE_TO_ONE

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        LangGraph node entry point.

        Synthesizes literature and computational evidence.
        """
        query = state.get("query", "")
        lit_summary = state.get("literature_summary", "No literature found.")
        struct_summary = state.get("structure_summary", "No structure analysis.")
        drug_summary = state.get("drug_summary", "")
        lit_count = state.get("literature_count", 0)
        pdb_ids = state.get("analyzed_pdb_ids", [])
        citations = state.get("literature_citations", [])
        drug_insights = state.get("drug_insights", [])
        resolution_warning = state.get("resolution_warning", "")

        # Extract mutations from literature
        mutations = self._extract_mutations_from_literature(citations)
        logger.info(f"Extracted {len(mutations)} mutations from literature")

        # Extract hinge residues from structure analysis
        hinge_residues = self._extract_hinge_residues(struct_summary)
        flexible_regions = self._extract_flexible_regions(struct_summary)

        # Cross-reference mutations with structural data
        insights = self._generate_insights(mutations, hinge_residues, flexible_regions)

        # Generate experiment suggestions
        suggester = ExperimentSuggester()
        experiment_state = {
            "mutations": mutations,
            "insights": insights,
            "drug_insights": drug_insights,
            "analyzed_pdb_ids": pdb_ids,
            "structure_summary": struct_summary,
        }
        suggestions = suggester.suggest(experiment_state)
        experiment_section = suggester.format_suggestions(suggestions)

        # Build synthesis report
        report = self._generate_report(
            query=query,
            lit_summary=lit_summary,
            struct_summary=struct_summary,
            drug_summary=drug_summary,
            lit_count=lit_count,
            pdb_ids=pdb_ids,
            mutations=mutations,
            insights=insights,
            drug_insights=drug_insights,
            experiment_suggestions=experiment_section,
            resolution_warning=resolution_warning,
        )

        return {
            "synthesis": "Complete",
            "final_report": report,
            "current_phase": "done",
        }

    def _extract_mutations_from_literature(self, citations: list) -> list[MutationInfo]:
        """Extract mutations mentioned in paper abstracts."""
        mutations = []

        for citation in citations:
            abstract = getattr(citation, "abstract", "") or ""
            title = getattr(citation, "title", "") or ""
            pmid = getattr(citation, "pmid", "unknown")
            text = f"{title} {abstract}"

            # Try each pattern
            for pattern in self.MUTATION_PATTERNS:
                for match in pattern.finditer(text):
                    groups = match.groups()
                    if len(groups) == 3:
                        orig, pos, mut = groups
                        # Convert three-letter codes if needed
                        orig_single = self.THREE_TO_ONE.get(orig.lower(), orig.upper())
                        mut_single = self.THREE_TO_ONE.get(mut.lower(), mut.upper())

                        # Get context
                        start = max(0, match.start() - 50)
                        end = min(len(text), match.end() + 50)
                        context = text[start:end].strip()

                        mutations.append(
                            MutationInfo(
                                original=orig_single,
                                position=int(pos),
                                mutant=mut_single,
                                source=f"PMID:{pmid}",
                                context=context,
                            )
                        )

        # Deduplicate
        seen = set()
        unique = []
        for m in mutations:
            key = (m.position, m.original, m.mutant)
            if key not in seen:
                seen.add(key)
                unique.append(m)

        return unique

    def _extract_hinge_residues(self, struct_summary: str) -> list[int]:
        """Extract hinge residue positions from structure summary."""
        hinge_residues = []

        # Multiple patterns to match different output formats
        patterns = [
            re.compile(r"[Hh]inge\s+[Rr]esidues?[:\s]+([0-9,\s]+)"),
            re.compile(r"\*\*[Hh]inge\s+[Rr]esidues?\*\*[^:]*:\s*(?:residues?\s+)?([0-9,\s\-]+)"),
            re.compile(r"hinge\s+(?:at\s+)?positions?\s*[:\s]+([0-9,\s]+)", re.IGNORECASE),
            re.compile(r"hinge[:\s]+(\d+(?:[,\s]+\d+)*)", re.IGNORECASE),
        ]

        for pattern in patterns:
            match = pattern.search(struct_summary)
            if match:
                numbers = re.findall(r"\d+", match.group(1))
                hinge_residues = [int(n) for n in numbers]
                if hinge_residues:
                    break

        return hinge_residues

    def _extract_flexible_regions(self, struct_summary: str) -> list[tuple[int, int]]:
        """Extract flexible region ranges from structure summary."""
        regions = []

        # Multiple patterns
        patterns = [
            re.compile(r"[Ff]lexible\s+[Rr]egions?[:\s]+(?:residues?\s+)?([0-9\-,\s]+)"),
            re.compile(r"\*\*[Ff]lexible\s+[Rr]egions?\*\*[^:]*:\s*(?:residues?\s+)?([0-9\-,\s]+)"),
            re.compile(r"flexible[:\s]+(\d+-\d+(?:[,\s]+\d+-\d+)*)", re.IGNORECASE),
        ]

        for pattern in patterns:
            match = pattern.search(struct_summary)
            if match:
                range_strs = re.findall(r"(\d+)-(\d+)", match.group(1))
                regions = [(int(a), int(b)) for a, b in range_strs]
                if regions:
                    break

        return regions

    def _generate_insights(
        self,
        mutations: list[MutationInfo],
        hinge_residues: list[int],
        flexible_regions: list[tuple[int, int]],
    ) -> list[MutationInsight]:
        """Cross-reference mutations with structural data."""
        insights = []

        for mut in mutations:
            pos = mut.position

            # Check if mutation is in a flexible region
            in_flexible = any(start <= pos <= end for start, end in flexible_regions)

            # Check if mutation is at a hinge residue
            is_hinge = pos in hinge_residues

            # Generate recommendation
            if is_hinge:
                rec = (
                    f"⚠️ {mut.original}{pos}{mut.mutant} is at a HINGE position. "
                    "Mutations here may significantly affect protein dynamics."
                )
            elif in_flexible:
                rec = (
                    f"🔄 {mut.original}{pos}{mut.mutant} is in a FLEXIBLE region. "
                    "This mutation may alter local conformational dynamics."
                )
            else:
                rec = (
                    f"✓ {mut.original}{pos}{mut.mutant} is in a stable region. "
                    "May improve stability without affecting function."
                )

            insights.append(
                MutationInsight(
                    mutation=mut,
                    in_flexible_region=in_flexible,
                    is_hinge_residue=is_hinge,
                    flexibility_score=None,  # Could be computed from NMA data
                    recommendation=rec,
                )
            )

        return insights

    def _generate_report(
        self,
        query: str,
        lit_summary: str,
        struct_summary: str,
        drug_summary: str,
        lit_count: int,
        pdb_ids: list[str],
        mutations: list[MutationInfo],
        insights: list[MutationInsight],
        drug_insights: list = None,
        experiment_suggestions: str = "",
        resolution_warning: str = "",
    ) -> str:
        """Generate the final synthesis report."""
        drug_insights = drug_insights or []

        parts = [
            "# Biotech Research Report\n",
            f"**Query:** {query}\n",
        ]

        # Add resolution warning if present
        if resolution_warning:
            parts.append(f"\n> **Note:** {resolution_warning}\n")

        parts.append("---\n")

        # Literature section
        parts.append("## Literature Evidence\n")
        parts.append(lit_summary)
        parts.append("\n---\n")

        # Structure section
        parts.append("## Computational Analysis\n")
        if pdb_ids:
            parts.append(f"**Analyzed structures:** {', '.join(pdb_ids)}\n")
        parts.append(struct_summary)
        parts.append("\n---\n")

        # Drug discovery section (if present)
        if drug_summary:
            parts.append(drug_summary)
            parts.append("\n---\n")

        # Mutations section
        if mutations:
            parts.append("## Mutations Found in Literature\n")
            parts.append(f"**Total mutations identified:** {len(mutations)}\n\n")

            for mut in mutations[:10]:  # Top 10
                parts.append(f"- **{mut.original}{mut.position}{mut.mutant}** ({mut.source})\n")

            if len(mutations) > 10:
                parts.append(f"\n*...and {len(mutations) - 10} more*\n")
            parts.append("\n---\n")

        # Insights section
        parts.append("## Synthesis & Insights\n")

        has_data = lit_count > 0 or pdb_ids or drug_insights

        if has_data:
            sources = []
            if lit_count > 0:
                sources.append("literature evidence")
            if pdb_ids:
                sources.append("structural analysis")
            if drug_insights:
                sources.append("drug discovery data")

            parts.append(f"This analysis combines **{', '.join(sources)}**.\n\n")

            if insights:
                parts.append("### Mutation-Structure Cross-Reference\n")
                for insight in insights[:5]:  # Top 5 insights
                    parts.append(f"{insight.recommendation}\n\n")

            parts.append("### Key Findings\n")
            if lit_count > 0:
                parts.append(
                    "- Literature provides context on known mutations and stability factors\n"
                )
            if pdb_ids:
                parts.append(
                    "- Structural analysis identifies flexible regions that may be targets\n"
                )
            if drug_insights:
                potent_drugs = [
                    d
                    for d in drug_insights
                    if hasattr(d, "potency_class") and "potent" in d.potency_class
                ]
                parts.append(
                    f"- Found {len(drug_insights)} compounds, {len(potent_drugs)} are potent inhibitors\n"
                )

        else:
            parts.append("Insufficient data for synthesis.\n")

        # Experiment suggestions
        if experiment_suggestions:
            parts.append("\n---\n")
            parts.append(experiment_suggestions)
        else:
            # Fallback simple recommendations
            parts.append("\n---\n")
            parts.append("## Recommendations for Further Research\n")

            rec_num = 1

            if mutations and pdb_ids:
                hinge_mutations = [i for i in insights if i.is_hinge_residue]
                stable_mutations = [i for i in insights if not i.in_flexible_region]

                if stable_mutations:
                    parts.append(
                        f"{rec_num}. **Stabilizing candidates:** {len(stable_mutations)} mutations in stable regions\n"
                    )
                    rec_num += 1
                if hinge_mutations:
                    parts.append(
                        f"{rec_num}. **Dynamics-altering:** {len(hinge_mutations)} mutations at hinge positions\n"
                    )
                    rec_num += 1

            if drug_insights:
                parts.append(
                    f"{rec_num}. Investigate top potent compounds for selectivity profiling\n"
                )
                rec_num += 1
                parts.append(
                    f"{rec_num}. Consider structure-activity relationship (SAR) analysis\n"
                )
                rec_num += 1

            if pdb_ids:
                parts.append(f"{rec_num}. Consider MD simulations to validate predicted effects\n")
                rec_num += 1

            parts.append(f"{rec_num}. Experimental validation recommended\n")

        return "\n".join(parts)
