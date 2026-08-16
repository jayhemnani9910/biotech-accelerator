"""Tools driven through the real MCP protocol surface.

tests/test_mcp_server.py calls the tool functions directly, which skips the
layer a client actually uses: schema generation, argument coercion and result
serialisation. These go through MCPServer.call_tool instead, so a change in the
server library shows up here rather than in someone's editor.
"""

import json

import pytest

from biotech_accelerator import mcp_server
from biotech_accelerator.mcp_server import mcp

# Tools that need no network, so the protocol path can be exercised offline.
OFFLINE_TOOLS = {
    "extract_mutations": {"text": "The V600E substitution was characterised."},
    "cross_reference_mutations": {
        "mutations": [{"original": "V", "position": 47, "mutant": "E"}],
        "flexible_regions": [[45, 55]],
        "hinge_residues": [47],
    },
    "cache_stats": {},
    "clear_cache": {"namespace": "nonexistent-namespace"},
}

EXPECTED_TOOLS = {
    "search_literature",
    "search_literature_by_protein",
    "resolve_protein",
    "fetch_structure",
    "run_nma",
    "search_structures",
    "search_compounds_by_target",
    "get_compound",
    "get_approved_drugs_for_target",
    "extract_mutations",
    "cross_reference_mutations",
    "run_research",
    "cache_stats",
    "clear_cache",
}


def _text(result) -> str:
    """First text block of a CallToolResult."""
    return result.content[0].text


@pytest.fixture(autouse=True)
def _isolated_cache(monkeypatch, tmp_path):
    from biotech_accelerator.utils import cache as cache_module

    monkeypatch.setattr(cache_module, "_cache", cache_module.ResponseCache(cache_dir=tmp_path))


# --- discovery -------------------------------------------------------------


async def test_every_tool_is_advertised_over_the_protocol():
    names = {t.name for t in await mcp.list_tools()}

    assert EXPECTED_TOOLS.issubset(names)


async def test_every_tool_advertises_a_description():
    """The description is what a model reads to decide whether to call it."""
    for tool in await mcp.list_tools():
        assert tool.description, f"{tool.name} has no description"


async def test_every_tool_advertises_an_input_schema():
    for tool in await mcp.list_tools():
        assert tool.input_schema.get("type") == "object", f"{tool.name} has no object schema"


# --- invocation ------------------------------------------------------------


@pytest.mark.parametrize("name,args", sorted(OFFLINE_TOOLS.items()))
async def test_offline_tool_returns_a_successful_result(name, args):
    result = await mcp.call_tool(name, args)

    assert result.is_error is False, f"{name} errored: {_text(result)}"


@pytest.mark.parametrize("name,args", sorted(OFFLINE_TOOLS.items()))
async def test_offline_tool_returns_parseable_json(name, args):
    result = await mcp.call_tool(name, args)

    json.loads(_text(result))  # raises if the payload is not JSON


async def test_extract_mutations_over_the_protocol_finds_the_mutation():
    result = await mcp.call_tool("extract_mutations", OFFLINE_TOOLS["extract_mutations"])

    assert "V600E" in _text(result) or '"position": 600' in _text(result)


async def test_cross_reference_over_the_protocol_flags_the_hinge():
    result = await mcp.call_tool(
        "cross_reference_mutations", OFFLINE_TOOLS["cross_reference_mutations"]
    )

    assert "HINGE" in _text(result)


async def test_an_unknown_tool_is_rejected():
    with pytest.raises(Exception):
        await mcp.call_tool("no_such_tool", {})


# --- payload discipline ----------------------------------------------------


async def test_run_nma_stays_within_a_sane_payload_size(monkeypatch, tmp_path):
    """Guards the eigenvector omission across a server-library change."""
    import numpy as np

    from biotech_accelerator.agents.nodes.structure_analyst import StructureAnalysisResult
    from biotech_accelerator.domain.protein_models import (
        FlexibilityMetrics,
        NMAResult,
        PDBStructure,
    )

    n = 167
    nma = NMAResult(
        pdb_id="6OIM",
        n_modes=100,
        eigenvalues=np.ones(100),
        eigenvectors=np.ones((n * 3, 100)),
        fluctuations=np.ones(n),
        collectivity=np.ones(100),
        vibrational_entropy=-1.0,
        flexibility=FlexibilityMetrics(0.1, 2.0, [(1, 3)], [(5, 9)], [2]),
        residue_numbers=list(range(1, n + 1)),
        chain_ids=["A"] * n,
    )
    result = StructureAnalysisResult(
        pdb_id="6OIM",
        structure=PDBStructure(pdb_id="6OIM", file_path=tmp_path / "6OIM.pdb"),
        nma_result=nma,
    )

    class _Agent:
        async def analyze_structure(self, pdb_id):
            return result

    monkeypatch.setitem(mcp_server._adapters, "structure", _Agent())

    payload = await mcp.call_tool("run_nma", {"pdb_id": "6OIM"})
    text = _text(payload)

    assert len(text) < 50_000, f"payload is {len(text)} bytes"
    assert "eigenvectors_shape" in text


# --- server identity -------------------------------------------------------


def test_server_reports_the_package_version():
    """Clients show this in their server list; an empty version reads as broken."""
    from biotech_accelerator import __version__

    assert mcp.version == __version__
