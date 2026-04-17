"""Smoke tests for the MCP server exposure layer.

Verifies tools are registered and the pure-function tools (no network)
work correctly. Adapter-backed tools are covered by the integration suite.
"""

from biotech_accelerator.mcp_server import (
    cross_reference_mutations,
    extract_mutations,
    mcp,
)


def test_mcp_server_registers_expected_tools():
    tools = mcp._tool_manager._tools
    expected = {
        "search_literature",
        "search_literature_by_protein",
        "resolve_protein",
        "fetch_structure",
        "run_nma",
        "search_compounds_by_target",
        "get_compound",
        "get_approved_drugs_for_target",
        "extract_mutations",
        "cross_reference_mutations",
        "run_research",
    }
    assert expected.issubset(set(tools.keys()))


def test_extract_mutations_tool_single_letter():
    muts = extract_mutations("The V600E mutation drives BRAF-related melanoma.")
    assert any(m["original"] == "V" and m["position"] == 600 and m["mutant"] == "E" for m in muts)


def test_extract_mutations_tool_three_letter():
    muts = extract_mutations("Ala42Gly reduces binding affinity.")
    assert any(m["original"] == "A" and m["position"] == 42 and m["mutant"] == "G" for m in muts)


def test_cross_reference_mutations_flags_hinge():
    mutations = [{"original": "V", "position": 47, "mutant": "E"}]
    insights = cross_reference_mutations(
        mutations, flexible_regions=[], hinge_residues=[45, 46, 47]
    )
    assert insights[0]["is_hinge_residue"] is True
    assert "HINGE" in insights[0]["recommendation"]


def test_cross_reference_mutations_flags_flexible_region():
    mutations = [{"original": "V", "position": 50, "mutant": "E"}]
    insights = cross_reference_mutations(mutations, flexible_regions=[[45, 55]], hinge_residues=[])
    assert insights[0]["in_flexible_region"] is True
    assert "FLEXIBLE" in insights[0]["recommendation"]


def test_cross_reference_mutations_flags_stable():
    mutations = [{"original": "V", "position": 100, "mutant": "E"}]
    insights = cross_reference_mutations(
        mutations, flexible_regions=[[45, 55]], hinge_residues=[47]
    )
    assert insights[0]["in_flexible_region"] is False
    assert insights[0]["is_hinge_residue"] is False
    assert "stable" in insights[0]["recommendation"].lower()
