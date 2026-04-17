"""
Biotech Research Accelerator — Working Example & Walkthrough

This script demonstrates the full project by running each layer individually,
then the complete LangGraph pipeline. Run with:

    python3 example_walkthrough.py

Requirements:
    pip install numpy scipy httpx pydantic pydantic-settings python-dotenv rich
    pip install langgraph langchain langchain-core prody biopython
"""

import asyncio
import time


async def main():
    print("=" * 70)
    print("  BIOTECH RESEARCH ACCELERATOR — WORKING EXAMPLE")
    print("=" * 70)

    # ─────────────────────────────────────────────────────────────────────
    # LAYER 1: Data Models (ports/ and domain/)
    # ─────────────────────────────────────────────────────────────────────
    print("\n┌─ LAYER 1: Data Models ─────────────────────────────────────────┐")

    from biotech_accelerator.domain.compound_models import CompoundInfo
    from biotech_accelerator.ports.literature import Citation
    from biotech_accelerator.ports.sequence import SequenceInfo

    # These are simple dataclasses that hold structured data
    seq = SequenceInfo(
        uniprot_id="P00698",
        name="Lysozyme C",
        sequence="KVFGRCE...",
        organism="Gallus gallus",
        gene_name="LYZ",
        pdb_ids=["1LYZ", "2LYZ"],
    )
    print(f"  SequenceInfo: {seq.name} ({seq.organism}), {len(seq.pdb_ids)} structures")

    compound = CompoundInfo(
        name="Aspirin",
        chembl_id="CHEMBL25",
        smiles="CC(=O)Oc1ccccc1C(=O)O",
        molecular_weight=180.16,
    )
    print(f"  CompoundInfo: {compound.name} (MW={compound.molecular_weight})")

    citation = Citation(
        pmid="12345",
        title="A study on lysozyme stability",
        authors=["Smith J", "Doe A"],
        journal="Nature",
        year=2024,
    )
    print(f"  Citation: {citation.title}")
    print("└───────────────────────────────────────────────────────────────┘")

    # ─────────────────────────────────────────────────────────────────────
    # LAYER 2: Adapters (external API clients)
    # ─────────────────────────────────────────────────────────────────────
    print("\n┌─ LAYER 2: Adapters (Live API Calls) ──────────────────────────┐")

    # --- PDB: Fetch protein structures ---
    from biotech_accelerator.adapters.pdb_adapter import PDBAdapter

    pdb = PDBAdapter()
    try:
        structure = await pdb.fetch_structure("1LYZ")
        print(
            f"  PDB 1LYZ: resolution={structure.resolution}Å, "
            f"{structure.num_residues} residues, method={structure.method}"
        )
    finally:
        await pdb.close()

    # --- UniProt: Protein sequences & annotations ---
    from biotech_accelerator.adapters.uniprot_adapter import UniProtAdapter

    uniprot = UniProtAdapter()
    try:
        seq = await uniprot.get_sequence("P00698")
        print(
            f"  UniProt P00698: {seq.name}, {seq.length} aa, "
            f"gene={seq.gene_name}, {len(seq.pdb_ids)} PDB structures"
        )
    finally:
        await uniprot.close()

    # --- PubMed: Scientific literature ---
    from biotech_accelerator.adapters.pubmed_adapter import PubMedAdapter

    pubmed = PubMedAdapter()
    try:
        result = await pubmed.search("lysozyme stability", max_results=3)
        print(
            f"  PubMed 'lysozyme stability': {result.total_count} total, "
            f"fetched {len(result.citations)}"
        )
        for c in result.citations[:2]:
            print(f"    [{c.year}] {c.title[:60]}...")
    finally:
        await pubmed.close()

    # --- ChEMBL: Drug/compound data ---
    from biotech_accelerator.adapters.chembl_adapter import ChEMBLAdapter

    chembl = ChEMBLAdapter()
    try:
        aspirin = await chembl.get_compound("CHEMBL25")
        print(
            f"  ChEMBL CHEMBL25: {aspirin.name}, MW={aspirin.molecular_weight}, LogP={aspirin.logp}"
        )
    finally:
        await chembl.close()

    print("└───────────────────────────────────────────────────────────────┘")

    # ─────────────────────────────────────────────────────────────────────
    # LAYER 3: Analysis (NMA — Normal Mode Analysis)
    # ─────────────────────────────────────────────────────────────────────
    print("\n┌─ LAYER 3: Computational Analysis (NMA) ───────────────────────┐")

    from biotech_accelerator.analysis.nma_wrapper import NMAAnalyzer

    analyzer = NMAAnalyzer()
    nma = await analyzer.analyze_async(structure.file_path)
    flex = nma.flexibility
    print(f"  NMA on 1LYZ: {nma.n_modes} normal modes computed")
    print(f"  Mean fluctuation: {flex.mean_fluctuation:.3f} Å²")
    print(f"  Flexible regions: {flex.flexible_regions[:3]}")
    print(f"  Rigid core: {flex.rigid_regions[:3]}")
    print(f"  Hinge residues: {[int(h) for h in flex.hinge_residues[:5]]}")
    print("└───────────────────────────────────────────────────────────────┘")

    # ─────────────────────────────────────────────────────────────────────
    # LAYER 4: Agents (LangGraph nodes)
    # ─────────────────────────────────────────────────────────────────────
    print("\n┌─ LAYER 4: AI Agents ──────────────────────────────────────────┐")

    # Each agent is a callable that takes a state dict and returns updates
    from biotech_accelerator.agents.nodes.bio_literature import BioLiteratureAgent
    from biotech_accelerator.agents.nodes.drug_binding import DrugBindingAgent
    from biotech_accelerator.agents.nodes.structure_analyst import StructureAnalystAgent

    # Structure agent
    agent = StructureAnalystAgent()
    try:
        result = await agent({"pdb_ids": ["1LYZ"]})
        print(
            f"  StructureAnalyst: analyzed {result['analyzed_pdb_ids']}, "
            f"summary={len(result['structure_summary'])} chars"
        )
    finally:
        await agent.close()

    # Literature agent
    agent = BioLiteratureAgent()
    try:
        result = await agent(
            {
                "query": "lysozyme mutations stability",
                "protein_names": ["lysozyme"],
                "target_proteins": [],
                "pdb_ids": ["1LYZ"],
            }
        )
        print(
            f"  BioLiterature: found {result['literature_count']} papers, "
            f"{len(result['literature_evidence'])} evidence items"
        )
    finally:
        await agent.close()

    # Drug binding agent
    agent = DrugBindingAgent()
    try:
        result = await agent(
            {
                "query": "EGFR inhibitors",
                "protein_names": ["EGFR"],
            }
        )
        print(
            f"  DrugBinding: {len(result.get('drug_insights', []))} compounds, "
            f"e.g. {result['drug_insights'][0].compound.name if result.get('drug_insights') else 'N/A'}"
        )
    finally:
        await agent.close()

    print("└───────────────────────────────────────────────────────────────┘")

    # ─────────────────────────────────────────────────────────────────────
    # LAYER 5: Full Pipeline (LangGraph orchestration)
    # ─────────────────────────────────────────────────────────────────────
    print("\n┌─ LAYER 5: Full Pipeline (LangGraph) ─────────────────────────┐")
    print("│                                                               │")
    print("│  Query → Parse → Resolve Proteins → Literature Search →       │")
    print("│  Structure Analysis → Drug Discovery → Synthesis → Report     │")
    print("│                                                               │")
    print("└───────────────────────────────────────────────────────────────┘")

    from biotech_accelerator.graph.biotech_graph import run_research

    query = "What mutations stabilize lysozyme? Analyze PDB 1LYZ structure."
    print(f'\n  Query: "{query}"')

    start = time.time()
    final = await run_research(query)
    elapsed = time.time() - start

    print(f"  Completed in {elapsed:.1f}s")
    print(f"  Phase: {final['current_phase']}")
    print(f"  PDB IDs: {final.get('pdb_ids', [])}")
    print(f"  Proteins: {final.get('protein_names', [])}")
    print(f"  UniProt: {final.get('uniprot_ids', [])}")
    print(f"  Papers: {final.get('literature_count', 0)}")
    print(f"  Structures: {final.get('analyzed_pdb_ids', [])}")
    print(f"  Drug query: {final.get('has_drug_query', False)}")
    print()

    # Print the final report
    print("=" * 70)
    print("  GENERATED RESEARCH REPORT")
    print("=" * 70)
    print(final.get("final_report", "No report generated"))
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
