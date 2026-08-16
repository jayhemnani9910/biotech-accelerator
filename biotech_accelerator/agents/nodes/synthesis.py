"""
Synthesis Agent

Synthesizes literature evidence with computational structural analysis.
Extracts mutations from papers and cross-references with flexibility data.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ._structural_context import StructuralContext, resolved_residues, structural_context
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
class ReportData:
    """Everything the final report is rendered from.

    Collected into one value object because passing eleven positional arguments
    made the signature the hardest thing about the function.
    """

    query: str = ""
    lit_summary: str = ""
    struct_summary: str = ""
    drug_summary: str = ""
    lit_count: int = 0
    pdb_ids: list[str] = field(default_factory=list)
    mutations: list["MutationInfo"] = field(default_factory=list)
    insights: list["MutationInsight"] = field(default_factory=list)
    drug_insights: list = field(default_factory=list)
    experiment_suggestions: str = ""
    resolution_warning: str = ""


@dataclass
class MutationInsight:
    """Insight from cross-referencing mutation with structure."""

    mutation: MutationInfo
    in_flexible_region: bool
    is_hinge_residue: bool
    flexibility_score: Optional[float]
    recommendation: str
    # False when the residue is absent from the analysed structure, in which case
    # the flags above carry no structural meaning.
    is_resolved: bool = True


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

        # Structural data comes from the typed NMA results, not the summary prose
        hinge_residues, flexible_regions, _ = self._structural_context(state)

        # Cross-reference mutations with structural data
        insights = self._generate_insights(
            mutations,
            hinge_residues,
            flexible_regions,
            resolved_residues=resolved_residues(state),
        )

        # Generate experiment suggestions
        suggester = ExperimentSuggester()
        experiment_state = {
            "mutations": mutations,
            "insights": insights,
            "drug_insights": drug_insights,
            "analyzed_pdb_ids": pdb_ids,
            "structure_analysis": state.get("structure_analysis"),
        }
        suggestions = suggester.suggest(experiment_state)
        experiment_section = suggester.format_suggestions(suggestions)

        # Build synthesis report
        report = self._generate_report(
            ReportData(
                query=query,
                lit_summary=lit_summary,
                struct_summary=struct_summary,
                drug_summary=drug_summary,
                lit_count=lit_count,
                pdb_ids=pdb_ids,
                mutations=mutations,
                insights=insights,
                drug_insights=drug_insights or [],
                experiment_suggestions=experiment_section,
                resolution_warning=resolution_warning,
            )
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

    @staticmethod
    def _structural_context(state: dict[str, Any]) -> StructuralContext:
        """Hinge residues and flexible/rigid regions from the analysed structures."""
        return structural_context(state)

    def _generate_insights(
        self,
        mutations: list[MutationInfo],
        hinge_residues: list[int],
        flexible_regions: list[tuple[int, int]],
        resolved_residues: Optional[set[int]] = None,
    ) -> list[MutationInsight]:
        """Cross-reference mutations with structural data.

        `resolved_residues` is the set of residue numbers actually present in the
        analysed structure. A mutation outside it gets no structural verdict —
        calling an unmodelled residue "stable" reads as a real negative result
        when it only means the residue was never looked at. Omit the argument
        when there is no roster to check against (the MCP tool passes explicit
        regions and has none).
        """
        insights = []

        for mut in mutations:
            pos = mut.position

            if resolved_residues is not None and pos not in resolved_residues:
                insights.append(
                    MutationInsight(
                        mutation=mut,
                        in_flexible_region=False,
                        is_hinge_residue=False,
                        flexibility_score=None,
                        recommendation=(
                            f"— {mut.original}{pos}{mut.mutant} is not resolved in the "
                            "analysed structure, so no structural interpretation is "
                            "available for it."
                        ),
                        is_resolved=False,
                    )
                )
                continue

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

    # --- report assembly ---------------------------------------------------
    #
    # Split into three stages so the branching lives apart from the markdown:
    # _evidence_sources / _key_findings / _fallback_recommendations decide what
    # is true, and _generate_report only renders. The inputs travel as one
    # ReportData rather than as eleven positional arguments.

    @staticmethod
    def _evidence_sources(data: "ReportData") -> list[str]:
        """Which kinds of evidence this report is actually built on."""
        sources = []
        if data.lit_count > 0:
            sources.append("literature evidence")
        if data.pdb_ids:
            sources.append("structural analysis")
        if data.drug_insights:
            sources.append("drug discovery data")
        return sources

    @staticmethod
    def _key_findings(data: "ReportData") -> list[str]:
        """One bullet per evidence stream that produced something."""
        findings = []
        if data.lit_count > 0:
            findings.append("Literature provides context on known mutations and stability factors")
        if data.pdb_ids:
            findings.append("Structural analysis identifies flexible regions that may be targets")
        if data.drug_insights:
            potent = [
                d
                for d in data.drug_insights
                if hasattr(d, "potency_class") and "potent" in d.potency_class
            ]
            findings.append(
                f"Found {len(data.drug_insights)} compounds, {len(potent)} are potent inhibitors"
            )
        return findings

    @staticmethod
    def _fallback_recommendations(data: "ReportData") -> list[str]:
        """Generic next steps, used only when no concrete experiment was suggested."""
        recommendations = []

        if data.mutations and data.pdb_ids:
            hinge = [i for i in data.insights if i.is_hinge_residue]
            stable = [i for i in data.insights if not i.in_flexible_region and i.is_resolved]
            if stable:
                recommendations.append(
                    f"**Stabilizing candidates:** {len(stable)} mutations in stable regions"
                )
            if hinge:
                recommendations.append(
                    f"**Dynamics-altering:** {len(hinge)} mutations at hinge positions"
                )

        if data.drug_insights:
            recommendations.append("Investigate top potent compounds for selectivity profiling")
            recommendations.append("Consider structure-activity relationship (SAR) analysis")

        if data.pdb_ids:
            recommendations.append("Consider MD simulations to validate predicted effects")

        recommendations.append("Experimental validation recommended")
        return recommendations

    def _generate_report(self, data: "ReportData") -> str:
        """Render the final synthesis report. Decisions live in the helpers above."""
        parts = [
            "# Biotech Research Report\n",
            f"**Query:** {data.query}\n",
        ]

        if data.resolution_warning:
            parts.append(f"\n**Note:** {data.resolution_warning}\n")

        parts.append("---\n")

        parts.append("## Literature Evidence\n")
        parts.append(data.lit_summary)
        parts.append("\n---\n")

        parts.append("## Computational Analysis\n")
        if data.pdb_ids:
            parts.append(f"**Analyzed structures:** {', '.join(data.pdb_ids)}\n")
        parts.append(data.struct_summary)
        parts.append("\n---\n")

        if data.drug_summary:
            parts.append(data.drug_summary)
            parts.append("\n---\n")

        if data.mutations:
            parts.append("## Mutations Found in Literature\n")
            parts.append(f"**Total mutations identified:** {len(data.mutations)}\n\n")
            for mut in data.mutations[:10]:
                parts.append(f"- **{mut.original}{mut.position}{mut.mutant}** ({mut.source})\n")
            if len(data.mutations) > 10:
                parts.append(f"\n*...and {len(data.mutations) - 10} more*\n")
            parts.append("\n---\n")

        parts.append("## Synthesis & Insights\n")

        sources = self._evidence_sources(data)
        if sources:
            parts.append(f"This analysis combines **{', '.join(sources)}**.\n\n")

            if data.insights:
                parts.append("### Mutation-Structure Cross-Reference\n")
                for insight in data.insights[:5]:
                    parts.append(f"{insight.recommendation}\n\n")

            parts.append("### Key Findings\n")
            for finding in self._key_findings(data):
                parts.append(f"- {finding}\n")
        else:
            parts.append("Insufficient data for synthesis.\n")

        parts.append("\n---\n")
        if data.experiment_suggestions:
            parts.append(data.experiment_suggestions)
        else:
            parts.append("## Recommendations for Further Research\n")
            for i, recommendation in enumerate(self._fallback_recommendations(data), 1):
                parts.append(f"{i}. {recommendation}\n")

        return "\n".join(parts)
