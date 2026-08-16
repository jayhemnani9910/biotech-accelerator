"""What the MCP tools are allowed to put on the wire.

An MCP response is read by a language model, so payload shape is part of the
contract: per-residue data is useful, the raw modal decomposition is not, and a
50,000-float matrix would crowd out everything else in the client's context.
"""

import json

import numpy as np

from biotech_accelerator.agents.nodes.structure_analyst import StructureAnalysisResult
from biotech_accelerator.domain.protein_models import (
    FlexibilityMetrics,
    NMAResult,
    PDBStructure,
)
from biotech_accelerator.mcp_server import _nma_response


def _result(n_residues: int = 167, n_modes: int = 100) -> StructureAnalysisResult:
    flexibility = FlexibilityMetrics(
        mean_fluctuation=0.13,
        max_fluctuation=2.07,
        flexible_regions=[(119, 124)],
        rigid_regions=[(3, 24)],
        hinge_residues=[120, 121],
    )
    nma = NMAResult(
        pdb_id="6OIM",
        n_modes=n_modes,
        eigenvalues=np.ones(n_modes),
        eigenvectors=np.ones((n_residues * 3, n_modes)),
        fluctuations=np.ones(n_residues),
        collectivity=np.ones(n_modes),
        vibrational_entropy=-1.5,
        flexibility=flexibility,
        residue_numbers=list(range(1, n_residues + 1)),
        chain_ids=["A"] * n_residues,
    )
    return StructureAnalysisResult(
        pdb_id="6OIM",
        structure=PDBStructure(pdb_id="6OIM", file_path="/tmp/6OIM.pdb"),
        nma_result=nma,
        summary="## Structure Analysis: 6OIM",
    )


def test_response_omits_the_raw_eigenvector_matrix():
    payload = _nma_response(_result())

    assert "eigenvectors" not in payload["nma_result"]


def test_response_reports_the_eigenvector_shape_it_withheld():
    """Withholding data silently is worse than not sending it."""
    payload = _nma_response(_result())

    assert payload["nma_result"]["eigenvectors_shape"] == [501, 100]


def test_response_keeps_per_residue_data_aligned_with_residue_numbers():
    nma = _nma_response(_result())["nma_result"]

    assert len(nma["fluctuations"]) == len(nma["residue_numbers"]) == 167


def test_response_keeps_the_small_per_mode_arrays():
    nma = _nma_response(_result())["nma_result"]

    assert len(nma["eigenvalues"]) == 100
    assert len(nma["collectivity"]) == 100


def test_response_stays_small_enough_for_a_client_context():
    blob = json.dumps(_nma_response(_result()))

    assert len(blob) < 50_000, f"payload is {len(blob)} bytes"


def test_response_survives_an_analysis_that_failed():
    failed = StructureAnalysisResult(pdb_id="9XXX", structure=None, error="not found")

    payload = _nma_response(failed)

    assert payload["error"] == "not found"
    assert payload["nma_result"] is None
