"""A mutation at a residue the structure does not contain has no structural verdict.

"Stable region" is a claim about the structure. When the residue is not resolved
in the model at all — or belongs to a different protein entirely — the honest
answer is that we cannot say, not a reassuring negative.
"""

from biotech_accelerator.agents.nodes.synthesis import MutationInfo, SynthesisAgent


def _mutation(position: int) -> MutationInfo:
    return MutationInfo(original="A", position=position, mutant="V", source="PMID:1", context="")


def test_residue_outside_the_structure_is_not_called_stable():
    agent = SynthesisAgent()

    insights = agent._generate_insights(
        [_mutation(9999)],
        hinge_residues=[30],
        flexible_regions=[(119, 124)],
        resolved_residues={1, 2, 3, 30, 119, 120, 121, 122, 123, 124},
    )

    assert len(insights) == 1
    assert insights[0].is_resolved is False
    assert "stable region" not in insights[0].recommendation
    assert "not resolved" in insights[0].recommendation.lower()


def test_residue_inside_the_structure_still_gets_a_verdict():
    agent = SynthesisAgent()

    insights = agent._generate_insights(
        [_mutation(30)],
        hinge_residues=[30],
        flexible_regions=[],
        resolved_residues={1, 2, 3, 30},
    )

    assert insights[0].is_resolved is True
    assert "HINGE" in insights[0].recommendation


def test_unresolved_residue_is_not_flagged_as_flexible_or_hinge():
    agent = SynthesisAgent()

    insights = agent._generate_insights(
        [_mutation(500)], hinge_residues=[30], flexible_regions=[], resolved_residues={30}
    )

    assert insights[0].in_flexible_region is False
    assert insights[0].is_hinge_residue is False


def test_without_a_residue_list_behaviour_is_unchanged():
    """The MCP tool passes explicit regions and has no residue roster."""
    agent = SynthesisAgent()

    insights = agent._generate_insights([_mutation(120)], [30], [(119, 124)])

    assert insights[0].is_resolved is True
    assert "FLEXIBLE" in insights[0].recommendation
