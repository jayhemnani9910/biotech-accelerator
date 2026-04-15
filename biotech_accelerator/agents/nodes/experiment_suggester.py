"""
Experiment Suggester

Generates actionable experiment suggestions based on
literature, structure, and drug discovery data.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExperimentSuggestion:
    """A suggested experiment."""

    title: str
    type: str  # "mutation", "binding", "structure", "assay"
    priority: int  # 1 = highest
    rationale: str
    methods: list[str]
    expected_outcome: str
    estimated_difficulty: str  # "easy", "moderate", "challenging"


class ExperimentSuggester:
    """
    Generates experiment suggestions from research data.

    Analyzes mutations, flexibility, and drug data to
    suggest actionable experiments.
    """

    # Amino acid properties for mutation suggestions
    AA_PROPERTIES = {
        # Hydrophobic
        "A": "hydrophobic",
        "V": "hydrophobic",
        "L": "hydrophobic",
        "I": "hydrophobic",
        "M": "hydrophobic",
        "F": "hydrophobic",
        "W": "hydrophobic",
        "P": "hydrophobic",
        # Polar
        "S": "polar",
        "T": "polar",
        "N": "polar",
        "Q": "polar",
        "C": "polar",
        "Y": "polar",
        # Charged
        "D": "negative",
        "E": "negative",
        "K": "positive",
        "R": "positive",
        "H": "positive",
        # Special
        "G": "flexible",
    }

    def suggest(self, state: dict[str, Any]) -> list[ExperimentSuggestion]:
        """Generate experiment suggestions from research state."""
        suggestions = []

        # Get data from state
        mutations = state.get("mutations", [])
        drug_insights = state.get("drug_insights", [])
        pdb_ids = state.get("analyzed_pdb_ids", [])
        struct_summary = state.get("structure_summary", "")

        # Extract flexible regions and hinge residues
        hinge_residues = self._extract_numbers(struct_summary, "hinge")
        flexible_regions = self._extract_regions(struct_summary, "flexible")
        rigid_regions = self._extract_regions(struct_summary, "rigid")

        # 1. Mutation-based suggestions
        if mutations or hinge_residues:
            suggestions.extend(self._suggest_mutations(mutations, hinge_residues, rigid_regions))

        # 2. Drug-based suggestions
        if drug_insights:
            suggestions.extend(self._suggest_drug_experiments(drug_insights))

        # 3. Structure-based suggestions
        if pdb_ids:
            suggestions.extend(self._suggest_structure_experiments(pdb_ids, flexible_regions))

        # Sort by priority
        suggestions.sort(key=lambda x: x.priority)

        return suggestions[:5]  # Top 5 suggestions

    def _suggest_mutations(
        self,
        known_mutations: list,
        hinge_residues: list[int],
        rigid_regions: list[tuple[int, int]],
    ) -> list[ExperimentSuggestion]:
        """Suggest mutation experiments."""
        suggestions = []

        # Suggest stabilizing mutations in rigid regions
        if rigid_regions:
            start, end = rigid_regions[0]
            suggestions.append(
                ExperimentSuggestion(
                    title=f"Engineer stabilizing mutations in rigid core (residues {start}-{end})",
                    type="mutation",
                    priority=1,
                    rationale=(
                        "Mutations in rigid regions are less likely to affect function "
                        "and more likely to improve stability."
                    ),
                    methods=[
                        "Design conservative mutations (e.g., V→I, L→V) in rigid core",
                        "Use Rosetta or FoldX for ΔΔG predictions",
                        "Express and purify mutants",
                        "Measure stability via DSF or CD thermal melt",
                    ],
                    expected_outcome="1-3°C increase in Tm for stabilizing mutations",
                    estimated_difficulty="moderate",
                )
            )

        # Suggest probing hinge residues
        if hinge_residues:
            positions = ", ".join(str(r) for r in hinge_residues[:3])
            suggestions.append(
                ExperimentSuggestion(
                    title=f"Probe hinge dynamics at positions {positions}",
                    type="mutation",
                    priority=2,
                    rationale=(
                        "Hinge residues control domain motion. Mutations here can "
                        "modulate flexibility and activity."
                    ),
                    methods=[
                        f"Design Gly→Pro mutations at positions {positions} to rigidify",
                        "Design Pro→Gly mutations to increase flexibility",
                        "Measure enzyme kinetics if applicable",
                        "Use NMR relaxation or hydrogen exchange to probe dynamics",
                    ],
                    expected_outcome="Changed conformational dynamics and possibly altered activity",
                    estimated_difficulty="moderate",
                )
            )

        return suggestions

    def _suggest_drug_experiments(
        self,
        drug_insights: list,
    ) -> list[ExperimentSuggestion]:
        """Suggest drug-related experiments."""
        suggestions = []

        # Find potent compounds
        potent = [
            d for d in drug_insights if hasattr(d, "potency_class") and "potent" in d.potency_class
        ]

        if potent:
            top_compound = (
                potent[0].compound.name if hasattr(potent[0], "compound") else "top compound"
            )
            suggestions.append(
                ExperimentSuggestion(
                    title=f"Profile selectivity of {top_compound}",
                    type="binding",
                    priority=1,
                    rationale=(
                        "Potent inhibitors need selectivity profiling to understand "
                        "off-target effects."
                    ),
                    methods=[
                        "Screen against kinase panel (or relevant target family)",
                        "Measure IC50 against top 10 related targets",
                        "Calculate selectivity index",
                        "Model binding mode with docking or crystallography",
                    ],
                    expected_outcome="Selectivity profile identifying potential off-targets",
                    estimated_difficulty="moderate",
                )
            )

        # Find known drugs for repurposing
        drugs = [d for d in drug_insights if hasattr(d, "is_approved_drug") and d.is_approved_drug]

        if drugs:
            drug_name = drugs[0].compound.name if hasattr(drugs[0], "compound") else "known drug"
            suggestions.append(
                ExperimentSuggestion(
                    title=f"Evaluate {drug_name} for repurposing",
                    type="assay",
                    priority=2,
                    rationale=(
                        "Approved drugs have known safety profiles, making them "
                        "attractive for repurposing."
                    ),
                    methods=[
                        "Confirm activity in cell-based assay",
                        "Test in disease-relevant model",
                        "Compare efficacy to standard-of-care",
                        "Assess drug-drug interaction potential",
                    ],
                    expected_outcome="Validated repurposing candidate for further development",
                    estimated_difficulty="moderate",
                )
            )

        return suggestions

    def _suggest_structure_experiments(
        self,
        pdb_ids: list[str],
        flexible_regions: list[tuple[int, int]],
    ) -> list[ExperimentSuggestion]:
        """Suggest structure-based experiments."""
        suggestions = []

        if flexible_regions:
            regions = ", ".join(f"{s}-{e}" for s, e in flexible_regions[:2])
            suggestions.append(
                ExperimentSuggestion(
                    title=f"Map binding sites in flexible regions ({regions})",
                    type="structure",
                    priority=2,
                    rationale=(
                        "Flexible regions often contain binding sites and may undergo "
                        "conformational changes upon ligand binding."
                    ),
                    methods=[
                        "Perform HDX-MS to identify protected regions upon ligand binding",
                        "Use crosslinking-MS to map interaction sites",
                        "Attempt co-crystallization with known ligands",
                        "Run molecular dynamics to observe conformational sampling",
                    ],
                    expected_outcome="Identified binding site(s) and conformational change mechanism",
                    estimated_difficulty="challenging",
                )
            )

        if pdb_ids:
            suggestions.append(
                ExperimentSuggestion(
                    title="Validate computational predictions with mutagenesis",
                    type="structure",
                    priority=3,
                    rationale=(
                        "NMA predictions of flexibility should be validated experimentally."
                    ),
                    methods=[
                        "Design 3-5 mutations spanning flexible and rigid regions",
                        "Express, purify, and crystallize mutants",
                        "Compare B-factors between wild-type and mutants",
                        "Measure thermostability as functional readout",
                    ],
                    expected_outcome="Validated flexibility predictions and structure-stability relationships",
                    estimated_difficulty="challenging",
                )
            )

        return suggestions

    def _extract_numbers(self, text: str, keyword: str) -> list[int]:
        """Extract numbers after a keyword."""
        pattern = rf"{keyword}[^:]*:\s*([0-9,\s]+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            numbers = re.findall(r"\d+", match.group(1))
            return [int(n) for n in numbers]
        return []

    def _extract_regions(self, text: str, keyword: str) -> list[tuple[int, int]]:
        """Extract residue ranges after a keyword."""
        patterns = [
            rf"{keyword}[^:]*:\s*residues?\s+(\d+)-(\d+)",
            rf"\*\*{keyword}[^*]*\*\*[^:]*:\s*(?:residues?\s+)?(\d+)-(\d+)",
            rf"{keyword}[:\s]+(\d+)-(\d+)",
        ]

        for pattern_str in patterns:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            matches = pattern.findall(text)
            if matches:
                return [(int(a), int(b)) for a, b in matches]

        return []

    def format_suggestions(self, suggestions: list[ExperimentSuggestion]) -> str:
        """Format suggestions as markdown."""
        if not suggestions:
            return "No specific experiments suggested based on available data."

        parts = ["## Suggested Experiments\n"]

        for i, sugg in enumerate(suggestions, 1):
            parts.append(f"### {i}. {sugg.title}")
            parts.append(f"**Type:** {sugg.type.capitalize()}")
            parts.append(f"**Priority:** {'⭐' * (4 - sugg.priority)}")
            parts.append(f"**Difficulty:** {sugg.estimated_difficulty.capitalize()}\n")
            parts.append(f"**Rationale:** {sugg.rationale}\n")
            parts.append("**Methods:**")
            for method in sugg.methods:
                parts.append(f"- {method}")
            parts.append(f"\n**Expected outcome:** {sugg.expected_outcome}\n")
            parts.append("---\n")

        return "\n".join(parts)
