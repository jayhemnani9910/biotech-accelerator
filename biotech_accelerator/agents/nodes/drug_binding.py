"""
Drug Binding Agent

Analyzes compound-protein interactions using ChEMBL data
and cross-references with structural analysis.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Optional

from ...adapters.chembl_adapter import ChEMBLAdapter
from ...domain.compound_models import CompoundInfo
from ...domain.vocabulary import EXCLUDED_TOKENS
from ...ports.compound import BioactivityData

logger = logging.getLogger(__name__)

# Concentration unit -> multiplier to reach nanomolar. Keys are NFKC-normalised
# and lowercased; "μm" here is U+03BC, which NFKC produces from both mu variants.
_UNIT_TO_NM = {
    "m": 1e9,
    "molar": 1e9,
    "mm": 1e6,
    "millimolar": 1e6,
    "um": 1e3,
    "μm": 1e3,
    "micromolar": 1e3,
    "nm": 1.0,
    "nanomolar": 1.0,
    "pm": 1e-3,
    "picomolar": 1e-3,
}


@dataclass
class DrugInsight:
    """Insight about a drug-target interaction."""

    compound: CompoundInfo
    target: str
    activity_type: str
    activity_value: float
    activity_unit: str
    potency_class: str  # "highly potent", "potent", "moderate", "weak"
    is_approved_drug: bool = False
    mechanism: Optional[str] = None


class DrugBindingAgent:
    """
    Agent that analyzes drug-protein binding.

    Capabilities:
    - Search for compounds active against a target
    - Analyze binding data from ChEMBL
    - Cross-reference with structural data
    - Identify approved drugs vs research compounds
    """

    # Known drug targets for quick lookup
    TARGET_MAP = {
        "egfr": ("EGFR", "Epidermal growth factor receptor"),
        "her2": ("ERBB2", "Receptor tyrosine-protein kinase erbB-2"),
        "braf": ("BRAF", "Serine/threonine-protein kinase B-raf"),
        "abl": ("ABL1", "Tyrosine-protein kinase ABL1"),
        "jak2": ("JAK2", "Tyrosine-protein kinase JAK2"),
        "vegfr": ("KDR", "Vascular endothelial growth factor receptor 2"),
        "alk": ("ALK", "ALK tyrosine kinase receptor"),
        "met": ("MET", "Hepatocyte growth factor receptor"),
        "flt3": ("FLT3", "Receptor-type tyrosine-protein kinase FLT3"),
        "kit": ("KIT", "Mast/stem cell growth factor receptor Kit"),
        "ace2": ("ACE2", "Angiotensin-converting enzyme 2"),
        "covid": ("SARS-CoV-2", "SARS-CoV-2 main protease"),
    }

    def __init__(self, chembl_adapter: Optional[ChEMBLAdapter] = None):
        self.chembl = chembl_adapter or ChEMBLAdapter()

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        LangGraph node entry point.

        Analyzes drug binding for targets in the query.
        """
        query = state.get("query", "") or state.get("root_query", "")
        protein_names = state.get("protein_names", [])

        # Extract target from query
        targets = self._extract_targets(query, protein_names)

        if not targets:
            logger.info("No drug targets identified in query")
            return {
                "drug_summary": "No drug targets identified for analysis.",
                "drug_insights": [],
                "current_phase": "drugs_done",
            }

        logger.info(f"Analyzing drugs for targets: {targets}")

        all_insights = []
        target_summaries = []

        for target in targets:
            # Get bioactivity data from ChEMBL
            activities = await self.chembl.search_by_target(
                target,
                activity_type="IC50",
                max_results=15,
            )

            # Also try Ki if IC50 has few results
            if len(activities) < 5:
                ki_activities = await self.chembl.search_by_target(
                    target,
                    activity_type="Ki",
                    max_results=10,
                )
                activities.extend(ki_activities)

            if not activities:
                target_summaries.append(f"No bioactivity data found for {target}")
                continue

            # Analyze activities
            insights = self._analyze_activities(activities, target)
            all_insights.extend(insights)

            # Generate summary for this target
            summary = self._generate_target_summary(target, insights)
            target_summaries.append(summary)

        # Build overall drug analysis summary
        drug_summary = self._generate_drug_summary(targets, all_insights, target_summaries)

        return {
            "drug_summary": drug_summary,
            "drug_insights": all_insights,
            "target_compounds": [i.compound for i in all_insights[:10]],
            "current_phase": "drugs_done",
        }

    def _extract_targets(
        self,
        query: str,
        protein_names: list[str],
    ) -> list[str]:
        """Extract drug targets from query.

        Every candidate is filtered through EXCLUDED_TOKENS. Without it the
        patterns below happily produce targets from ordinary prose — "target
        protein" yields PROTEIN, "inhibit the receptor" yields THE — and each
        one becomes a live ChEMBL search.
        """
        targets: list[str] = []

        def add(candidate: str) -> None:
            symbol = candidate.upper()
            if len(symbol) >= 2 and symbol not in EXCLUDED_TOKENS and symbol not in targets:
                targets.append(symbol)

        query_lower = query.lower()

        # Check for known targets
        for key, (symbol, _name) in self.TARGET_MAP.items():
            if key in query_lower:
                add(symbol)

        # Add protein names that look like targets
        for protein in protein_names:
            if re.match(r"^[A-Z]{2,6}\d?$", protein.upper()):
                add(protein)

        # Look for inhibitor/agonist/antagonist patterns
        patterns = [
            r"(\w+)\s+inhibitor",
            r"inhibit\s+(\w+)",
            r"(\w+)\s+antagonist",
            r"(\w+)\s+agonist",
            r"target\s+(\w+)",
        ]

        for pattern in patterns:
            for match in re.findall(pattern, query_lower):
                add(match)

        return targets

    def _analyze_activities(
        self,
        activities: list[BioactivityData],
        target: str,
    ) -> list[DrugInsight]:
        """Analyze bioactivity data and generate insights.

        Rows whose unit cannot be put on the nanomolar scale are dropped rather
        than ranked — comparing a raw value in µg/mL against one in nM produces
        a confident ordering with no meaning behind it.
        """
        ranked: list[tuple[float, DrugInsight]] = []

        for act in activities:
            nanomolar = self._to_nanomolar(act.activity_value, act.activity_unit)
            if nanomolar is None:
                logger.warning(
                    f"Dropping {act.compound.name or act.compound.chembl_id}: "
                    f"cannot convert {act.activity_value} {act.activity_unit!r} to nM"
                )
                continue

            ranked.append(
                (
                    nanomolar,
                    DrugInsight(
                        compound=act.compound,
                        target=target,
                        activity_type=act.activity_type,
                        activity_value=act.activity_value,
                        activity_unit=act.activity_unit,
                        potency_class=self._classify_potency(act.activity_value, act.activity_unit),
                        is_approved_drug=self._is_likely_drug(act.compound),
                    ),
                )
            )

        # Sort on the common nM scale, not on the raw value (lower = more potent).
        ranked.sort(key=lambda pair: pair[0])

        return [insight for _, insight in ranked]

    @staticmethod
    def _to_nanomolar(value: float, unit: str) -> Optional[float]:
        """Convert a concentration to nM, or None if the unit is unrecognised.

        NFKC folds U+00B5 MICRO SIGN and U+03BC GREEK SMALL LETTER MU to the same
        codepoint; ChEMBL emits both, and treating one of them as unrecognised
        silently grades micromolar values on the nanomolar scale.
        """
        normalized = unicodedata.normalize("NFKC", unit or "").strip().lower()
        factor = _UNIT_TO_NM.get(normalized)
        if factor is None:
            return None
        return value * factor

    def _classify_potency(self, value: float, unit: str) -> str:
        """Classify compound potency based on IC50/Ki value."""
        nanomolar = self._to_nanomolar(value, unit)
        if nanomolar is None:
            return f"unknown potency (unit {unit!r})"

        if nanomolar < 10:
            return "highly potent (<10 nM)"
        elif nanomolar < 100:
            return "potent (10-100 nM)"
        elif nanomolar < 1000:
            return "moderate (100-1000 nM)"
        else:
            return "weak (>1 µM)"

    def _is_likely_drug(self, compound: CompoundInfo) -> bool:
        """Check if compound is likely an approved drug."""
        if not compound.name:
            return False

        name = compound.name.lower()

        # Drug name patterns
        drug_suffixes = [
            "ib",
            "mab",
            "nib",
            "tinib",
            "zumab",
            "ximab",
            "cin",
            "mycin",
            "cillin",
            "pril",
            "sartan",
            "olol",
            "dipine",
            "afil",
            "prazole",
        ]

        for suffix in drug_suffixes:
            if name.endswith(suffix):
                return True

        return False

    def _generate_target_summary(
        self,
        target: str,
        insights: list[DrugInsight],
    ) -> str:
        """Generate summary for a single target."""
        if not insights:
            return f"No compounds found for {target}"

        parts = [f"### {target} Inhibitors\n"]

        # Count by potency class
        highly_potent = sum(1 for i in insights if "highly potent" in i.potency_class)
        potent = sum(1 for i in insights if i.potency_class == "potent (10-100 nM)")
        drugs = sum(1 for i in insights if i.is_approved_drug)

        parts.append(f"**Total compounds:** {len(insights)}")
        parts.append(f"- Highly potent (<10 nM): {highly_potent}")
        parts.append(f"- Potent (10-100 nM): {potent}")
        if drugs > 0:
            parts.append(f"- Likely approved drugs: {drugs}")
        parts.append("")

        # Top 5 compounds
        parts.append("**Top Compounds:**\n")
        for i, insight in enumerate(insights[:5], 1):
            name = insight.compound.name or insight.compound.chembl_id or "Unknown"
            drug_badge = " (Drug)" if insight.is_approved_drug else ""
            parts.append(
                f"{i}. **{name}**{drug_badge}\n"
                f"   - {insight.activity_type}: {insight.activity_value:.1f} {insight.activity_unit}\n"
                f"   - {insight.potency_class}"
            )
        parts.append("")

        return "\n".join(parts)

    def _generate_drug_summary(
        self,
        targets: list[str],
        insights: list[DrugInsight],
        target_summaries: list[str],
    ) -> str:
        """Generate overall drug analysis summary."""
        parts = [
            "## Drug Discovery Analysis\n",
            f"**Targets analyzed:** {', '.join(targets)}\n",
            f"**Total compounds found:** {len(insights)}\n",
        ]

        # Overall stats
        drugs = [i for i in insights if i.is_approved_drug]
        highly_potent = [i for i in insights if "highly potent" in i.potency_class]

        if drugs:
            parts.append(f"**Known drugs:** {len(drugs)}")
            drug_names = [d.compound.name for d in drugs[:5] if d.compound.name]
            if drug_names:
                parts.append(f"  - Examples: {', '.join(drug_names)}")

        if highly_potent:
            parts.append(f"**Highly potent compounds:** {len(highly_potent)}")

        parts.append("\n---\n")

        # Target-specific summaries
        for summary in target_summaries:
            parts.append(summary)
            parts.append("---\n")

        # Recommendations
        parts.append("### Recommendations\n")
        if drugs:
            parts.append("1. Review approved drugs for repurposing opportunities")
        if highly_potent:
            parts.append("2. Investigate highly potent compounds for selectivity")
        parts.append("3. Consider structure-activity relationship (SAR) analysis")
        parts.append("4. Cross-reference with structural data for binding site analysis")

        return "\n".join(parts)

    async def close(self):
        """Close adapters."""
        await self.chembl.close()
