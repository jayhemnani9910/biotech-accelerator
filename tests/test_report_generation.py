"""Characterisation tests for the synthesis report.

Written against SynthesisAgent.__call__ rather than _generate_report directly,
so the report's internals can be restructured without rewriting the tests. These
pin the report's observable content: which sections appear, when, and in what
order.
"""

import numpy as np

from biotech_accelerator.agents.nodes.structure_analyst import StructureAnalysisResult
from biotech_accelerator.agents.nodes.synthesis import SynthesisAgent
from biotech_accelerator.domain.protein_models import (
    FlexibilityMetrics,
    NMAResult,
    PDBStructure,
)


class _Citation:
    def __init__(self, abstract="", title="", pmid="1"):
        self.abstract = abstract
        self.title = title
        self.pmid = pmid


class _Drug:
    def __init__(self, potency_class="highly potent (<10 nM)", name="drugX"):
        self.potency_class = potency_class
        self.is_approved_drug = True

        class _C:
            pass

        self.compound = _C()
        self.compound.name = name


def _analysis(hinges=(120,), flexible=((119, 124),), rigid=((3, 24),)):
    nma = NMAResult(
        pdb_id="6OIM",
        n_modes=10,
        eigenvalues=np.ones(10),
        eigenvectors=np.ones((30, 10)),
        fluctuations=np.ones(10),
        collectivity=np.ones(10),
        vibrational_entropy=-1.0,
        flexibility=FlexibilityMetrics(
            mean_fluctuation=0.1,
            max_fluctuation=2.0,
            flexible_regions=[tuple(r) for r in flexible],
            rigid_regions=[tuple(r) for r in rigid],
            hinge_residues=list(hinges),
        ),
        residue_numbers=list(range(1, 201)),
        chain_ids=["A"] * 200,
    )
    return StructureAnalysisResult(
        pdb_id="6OIM",
        structure=PDBStructure(pdb_id="6OIM", file_path="/tmp/x.pdb"),
        nma_result=nma,
        summary="## Structure Analysis: 6OIM",
    )


async def _report(**state) -> str:
    out = await SynthesisAgent()(state)
    return out["final_report"]


# --- always-present scaffolding --------------------------------------------


async def test_report_opens_with_the_title_and_query():
    report = await _report(query="what stabilises lysozyme")

    assert report.startswith("# Biotech Research Report")
    assert "**Query:** what stabilises lysozyme" in report


async def test_core_sections_appear_in_order():
    report = await _report(query="q", literature_summary="lit", structure_summary="struct")

    assert report.index("## Literature Evidence") < report.index("## Computational Analysis")
    assert report.index("## Computational Analysis") < report.index("## Synthesis & Insights")


async def test_empty_state_says_insufficient_data_rather_than_inventing_findings():
    report = await _report(query="q")

    assert "Insufficient data for synthesis." in report


# --- conditional sections --------------------------------------------------


async def test_resolution_warning_is_surfaced_when_present():
    report = await _report(query="q", resolution_warning="Could not resolve: FOO")

    assert "Could not resolve: FOO" in report


async def test_drug_section_is_omitted_when_there_is_no_drug_summary():
    report = await _report(query="q")

    assert "Drug Discovery Analysis" not in report


async def test_drug_summary_is_included_when_present():
    report = await _report(query="q", drug_summary="## Drug Discovery Analysis\ncontent")

    assert "## Drug Discovery Analysis" in report


async def test_analyzed_structures_are_listed():
    report = await _report(query="q", analyzed_pdb_ids=["6OIM", "1LYZ"])

    assert "**Analyzed structures:** 6OIM, 1LYZ" in report


# --- mutations -------------------------------------------------------------


async def test_mutations_section_lists_what_was_found():
    report = await _report(
        query="q", literature_citations=[_Citation(abstract="A120G and V600E were tested.")]
    )

    assert "## Mutations Found in Literature" in report
    assert "**Total mutations identified:** 2" in report
    assert "**A120G**" in report


async def test_mutations_section_is_absent_when_none_were_found():
    report = await _report(query="q", literature_citations=[_Citation(abstract="nothing here")])

    assert "## Mutations Found in Literature" not in report


async def test_long_mutation_lists_are_truncated_with_a_count():
    abstract = " ".join(f"A{i}G" for i in range(100, 115))  # 15 distinct mutations
    report = await _report(query="q", literature_citations=[_Citation(abstract=abstract)])

    assert "**Total mutations identified:** 15" in report
    assert "*...and 5 more*" in report


# --- synthesis body --------------------------------------------------------


async def test_sources_are_named_when_data_is_present():
    report = await _report(query="q", literature_count=3, analyzed_pdb_ids=["6OIM"])

    assert "literature evidence" in report
    assert "structural analysis" in report


async def test_cross_reference_section_appears_when_there_are_insights():
    report = await _report(
        query="q",
        literature_citations=[_Citation(abstract="A120G tested.")],
        structure_analysis=[_analysis(hinges=(120,))],
        analyzed_pdb_ids=["6OIM"],
    )

    assert "### Mutation-Structure Cross-Reference" in report
    assert "HINGE" in report


async def test_potent_drug_count_is_reported():
    report = await _report(query="q", literature_count=1, drug_insights=[_Drug(), _Drug()])

    assert "Found 2 compounds, 2 are potent inhibitors" in report


# --- experiment suggestions vs fallback ------------------------------------


async def test_experiment_suggestions_replace_the_fallback_recommendations():
    report = await _report(query="q", analyzed_pdb_ids=["6OIM"], structure_analysis=[_analysis()])

    assert "## Suggested Experiments" in report
    assert "## Recommendations for Further Research" not in report


async def test_fallback_recommendations_appear_when_no_experiments_were_suggested():
    report = await _report(query="q", literature_count=2)

    assert "## Recommendations for Further Research" in report
    assert "Experimental validation recommended" in report


async def test_fallback_recommendations_are_numbered_consecutively():
    # A weak, unapproved compound yields no experiment suggestions of its own,
    # which is the only way to reach the fallback with its drug branch active.
    weak = _Drug(potency_class="weak (>1 uM)", name="weakling")
    weak.is_approved_drug = False

    report = await _report(query="q", literature_count=1, drug_insights=[weak])

    body = report.split("## Recommendations for Further Research")[1]
    numbers = [
        line.split(".")[0].strip() for line in body.splitlines() if line.strip()[:1].isdigit()
    ]
    assert numbers == [str(i) for i in range(1, len(numbers) + 1)]
    assert len(numbers) >= 3
