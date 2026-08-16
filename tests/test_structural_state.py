"""Downstream nodes must read structural data from typed state, not from prose.

The NMA results arrive in state["structure_analysis"] as real objects. They used
to be re-derived by regex-scanning the rendered markdown summary, which silently
returned [] whenever a pattern missed — indistinguishable from "no hinges here".
"""

import numpy as np

from biotech_accelerator.agents.nodes.experiment_suggester import ExperimentSuggester
from biotech_accelerator.agents.nodes.structure_analyst import StructureAnalysisResult
from biotech_accelerator.agents.nodes.synthesis import SynthesisAgent
from biotech_accelerator.domain.protein_models import (
    FlexibilityMetrics,
    NMAResult,
    PDBStructure,
)


def _analysis(
    pdb_id="6OIM",
    hinges=(120, 121),
    flexible=((119, 124),),
    rigid=((3, 24),),
    failed=False,
):
    if failed:
        return StructureAnalysisResult(pdb_id=pdb_id, structure=None, error="boom")
    nma = NMAResult(
        pdb_id=pdb_id,
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
        # Roster must actually contain the hinge/region positions above, or the
        # unresolved-residue guard will (correctly) refuse to interpret them.
        residue_numbers=list(range(1, 201)),
        chain_ids=["A"] * 200,
    )
    return StructureAnalysisResult(
        pdb_id=pdb_id,
        structure=PDBStructure(pdb_id=pdb_id, file_path="/tmp/x.pdb"),
        nma_result=nma,
        summary="## Structure Analysis",
    )


# --- SynthesisAgent --------------------------------------------------------


def test_synthesis_reads_hinges_from_typed_state():
    agent = SynthesisAgent()
    state = {"structure_analysis": [_analysis(hinges=(120, 121))]}

    hinges, _, _ = agent._structural_context(state)

    assert hinges == [120, 121]


def test_typed_state_wins_over_a_contradicting_summary_string():
    """The summary is for humans; it must not be the source of truth."""
    agent = SynthesisAgent()
    state = {
        "structure_analysis": [_analysis(hinges=(120, 121))],
        "structure_summary": "**Hinge Residues** (potential motion points):\n7, 8, 9",
    }

    hinges, _, _ = agent._structural_context(state)

    assert hinges == [120, 121]


def test_prose_that_no_regex_would_match_still_yields_data():
    """This is the silent-empty failure the regexes had."""
    agent = SynthesisAgent()
    state = {
        "structure_analysis": [_analysis(hinges=(120, 121), flexible=((119, 124),))],
        "structure_summary": "Everything about this protein is quite wobbly, honestly.",
    }

    hinges, flexible, _ = agent._structural_context(state)

    assert hinges == [120, 121]
    assert flexible == [(119, 124)]


def test_missing_structure_analysis_yields_empty_context():
    agent = SynthesisAgent()

    assert agent._structural_context({}) == ([], [], [])


def test_failed_analyses_are_skipped_not_crashed_on():
    agent = SynthesisAgent()
    state = {"structure_analysis": [_analysis(failed=True), _analysis(hinges=(55,))]}

    hinges, _, _ = agent._structural_context(state)

    assert hinges == [55]


# --- ExperimentSuggester ---------------------------------------------------


def test_suggester_reads_rigid_regions_from_typed_state():
    suggester = ExperimentSuggester()
    state = {"structure_analysis": [_analysis(rigid=((3, 24),))], "analyzed_pdb_ids": ["6OIM"]}

    suggestions = suggester.suggest(state)

    titles = " ".join(s.title for s in suggestions)
    assert "residues 3-24" in titles


def test_suggester_reads_hinges_from_typed_state():
    suggester = ExperimentSuggester()
    state = {
        "structure_analysis": [_analysis(hinges=(120, 121, 122))],
        "analyzed_pdb_ids": ["6OIM"],
    }

    suggestions = suggester.suggest(state)

    titles = " ".join(s.title for s in suggestions)
    assert "120, 121, 122" in titles


# --- end-to-end through the synthesis node ---------------------------------


async def test_cross_reference_uses_real_residue_numbers_from_state():
    """A mutation at residue 120 must be flagged against a hinge at residue 120."""

    class _Citation:
        pmid = "1"
        title = ""
        abstract = "The A120G substitution was characterised."

    agent = SynthesisAgent()
    state = {
        "query": "A120G",
        "literature_citations": [_Citation()],
        "structure_analysis": [_analysis(hinges=(120,))],
        "analyzed_pdb_ids": ["6OIM"],
    }

    out = await agent(state)

    assert "HINGE" in out["final_report"]
