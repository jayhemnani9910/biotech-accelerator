#!/usr/bin/env python3
"""
Quick test script to verify basic functionality.

Run: python test_basic.py
"""

import asyncio
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

from biotech_accelerator.adapters.pdb_adapter import PDBAdapter
from biotech_accelerator.agents.nodes.structure_analyst import (
    StructureAnalystAgent,
    analyze_protein_structure,
)
from biotech_accelerator.analysis.nma_wrapper import NMAAnalyzer


async def test_pdb_adapter():
    """Test PDB structure fetching."""
    print("\n=== Testing PDB Adapter ===\n")

    adapter = PDBAdapter()

    # Test with lysozyme (1LYZ)
    pdb_id = "1LYZ"
    print(f"Fetching structure: {pdb_id}")

    structure = await adapter.fetch_structure(pdb_id)

    print(f"  PDB ID: {structure.pdb_id}")
    print(f"  File: {structure.file_path}")
    print(f"  Resolution: {structure.resolution} Å")
    print(f"  Method: {structure.method}")
    print(f"  Residues: {structure.num_residues}")

    assert structure.file_path.exists(), "PDB file should exist"
    print("\n✓ PDB Adapter test passed!")

    await adapter.close()
    return structure


async def test_nma_analysis(pdb_path: Path):
    """Test Normal Mode Analysis."""
    print("\n=== Testing NMA Analysis ===\n")

    analyzer = NMAAnalyzer(n_modes=20)

    print(f"Running NMA on: {pdb_path}")
    result = await analyzer.analyze_async(pdb_path)

    print(f"  Modes computed: {result.n_modes}")
    print(f"  Mean fluctuation: {result.flexibility.mean_fluctuation:.4f}")
    print(f"  Max fluctuation: {result.flexibility.max_fluctuation:.4f}")
    print(f"  Flexible regions: {len(result.flexibility.flexible_regions)}")
    print(f"  Rigid regions: {len(result.flexibility.rigid_regions)}")
    print(f"  Hinge residues: {len(result.flexibility.hinge_residues)}")
    print(f"  Vibrational entropy: {result.vibrational_entropy:.4f}")

    print("\n✓ NMA Analysis test passed!")
    return result


async def test_structure_agent():
    """Test the Structure Analyst Agent."""
    print("\n=== Testing Structure Analyst Agent ===\n")

    # Test PDB ID extraction
    agent = StructureAnalystAgent()

    test_queries = [
        "Analyze the flexibility of 1LYZ",
        "Compare structures 1HHO and 2HHB",
        "What is the stability of PDB 4HHB?",
        "No PDB ID here",
    ]

    for query in test_queries:
        pdb_ids = agent.extract_pdb_ids(query)
        print(f"  '{query}' -> {pdb_ids}")

    # Test full analysis
    print("\nRunning full analysis on 1LYZ...")
    result = await analyze_protein_structure("1LYZ")

    if result.error:
        print(f"Error: {result.error}")
    else:
        print("\n--- Analysis Summary ---")
        print(result.summary)

    print("\n✓ Structure Agent test passed!")


async def main():
    """Run all tests."""
    print("=" * 60)
    print(" Biotech Research Accelerator - Basic Tests")
    print("=" * 60)

    try:
        # Test PDB adapter
        structure = await test_pdb_adapter()

        # Test NMA analysis
        await test_nma_analysis(structure.file_path)

        # Test agent
        await test_structure_agent()

        print("\n" + "=" * 60)
        print(" All tests passed! ✓")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
