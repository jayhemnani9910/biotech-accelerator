"""
Biotech Research Graph

LangGraph workflow that orchestrates:
1. Query parsing
2. Protein resolution (UniProt lookup)
3. Literature search
4. Structure analysis
5. Synthesis of evidence
"""

import logging
import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ..agents.nodes.bio_literature import BioLiteratureAgent
from ..agents.nodes.drug_binding import DrugBindingAgent
from ..agents.nodes.structure_analyst import StructureAnalystAgent
from ..agents.nodes.synthesis import SynthesisAgent

logger = logging.getLogger(__name__)

# Pre-compiled patterns
_PDB_ID_PATTERN = re.compile(r"\b([0-9][A-Z0-9]{3})\b", re.IGNORECASE)
_GENE_PATTERN = re.compile(r"\b([A-Z]{2,6})\b")

_EXCLUDE_TERMS = {
    "PDB",
    "DNA",
    "RNA",
    "NMR",
    "AND",
    "THE",
    "FOR",
    "NOT",
    "WITH",
    "FROM",
    "THAT",
    "THIS",
    "HAVE",
    "BEEN",
    "WERE",
    "WHAT",
    "HOW",
    "WHY",
    "CAN",
    "ARE",
    "WAS",
    "HAS",
    "HAD",
    "WILL",
    "STUDY",
    "RESULTS",
    "METHODS",
    "DATA",
    "ANALYSIS",
    "RESEARCH",
    "PROTEIN",
    "GENE",
    "CELL",
    "HUMAN",
    "MOUSE",
    "RAT",
}

# Common protein name to UniProt ID mapping
PROTEIN_NAME_MAP = {
    "lysozyme": "P00698",
    "hemoglobin": "P69905",
    "insulin": "P01308",
    "egfr": "P00533",
    "tp53": "P04637",
    "p53": "P04637",
    "myoglobin": "P02144",
    "albumin": "P02768",
    "collagen": "P02452",
    "actin": "P60709",
    "tubulin": "P68366",
    "ferritin": "P02794",
    "catalase": "P04040",
    "kinase": None,  # Generic - need specific kinase
    "protease": None,  # Generic
}


class BiotechState(TypedDict, total=False):
    """State schema for biotech research graph."""

    # Input
    query: str
    root_query: str

    # Parsed entities
    pdb_ids: list[str]
    protein_names: list[str]
    uniprot_ids: list[str]

    # Literature results
    literature_citations: list
    literature_evidence: list
    literature_summary: str
    literature_count: int

    # Structure results
    structure_analysis: list
    structure_summary: str
    analyzed_pdb_ids: list[str]
    structure_error: str

    # Drug discovery results
    drug_summary: str
    drug_insights: list
    target_compounds: list
    has_drug_query: bool

    # Synthesis
    synthesis: str
    final_report: str

    # Control
    current_phase: str
    error: str
    resolution_warning: str


async def parse_query_node(state: BiotechState) -> dict[str, Any]:
    """Parse the query to extract proteins and research goals."""
    query = state.get("query", "")
    query_lower = query.lower()

    # Extract PDB IDs via regex (no need to instantiate full agent)
    pdb_ids = list(dict.fromkeys(m.upper() for m in _PDB_ID_PATTERN.findall(query)))

    # Extract protein names and map to UniProt IDs
    protein_names = []
    uniprot_ids = []

    # Check known protein names from dictionary
    for protein, uniprot in PROTEIN_NAME_MAP.items():
        if protein in query_lower:
            protein_names.append(protein)
            if uniprot:  # Only add if we have a mapping
                uniprot_ids.append(uniprot)

    # Also extract gene-like patterns (2-6 uppercase letters)
    for match in _GENE_PATTERN.findall(query):
        # Don't add if it's a PDB ID, excluded term, or already in protein_names
        if (
            match not in pdb_ids
            and match not in _EXCLUDE_TERMS
            and match.lower() not in [p.lower() for p in protein_names]
        ):
            protein_names.append(match)

    # Deduplicate while preserving order
    protein_names = list(dict.fromkeys(protein_names))
    uniprot_ids = list(dict.fromkeys(uniprot_ids))

    # Detect if this is a drug-related query
    drug_keywords = [
        "inhibitor",
        "drug",
        "compound",
        "bind",
        "agonist",
        "antagonist",
        "therapeutic",
        "treatment",
        "ic50",
        "ki",
        "affinity",
        "chembl",
        "potency",
        "potent",
        "selectivity",
        "selective",
        "adme",
        "bioavailability",
        "off-target",
        "molecule",
        "ligand",
        "blocker",
        "activator",
        "modulator",
        "substrate",
        "clinical",
        "trial",
        "pharmaceutical",
        "medicine",
        "target",
        "receptor",
    ]
    has_drug_query = any(kw in query_lower for kw in drug_keywords)

    logger.info(
        f"Parsed query - PDB IDs: {pdb_ids}, Proteins: {protein_names}, Drug query: {has_drug_query}"
    )

    return {
        "pdb_ids": pdb_ids,
        "protein_names": protein_names,
        "uniprot_ids": uniprot_ids,
        "has_drug_query": has_drug_query,
        "current_phase": "parsed",
    }


async def resolve_proteins_node(state: BiotechState) -> dict[str, Any]:
    """Resolve protein names to UniProt IDs and get mapped PDB structures."""
    protein_names = state.get("protein_names", [])
    pdb_ids = list(state.get("pdb_ids", []))  # Copy existing
    uniprot_ids = list(state.get("uniprot_ids", []))

    # If we already have PDB IDs from the query, skip resolution
    if pdb_ids and not protein_names:
        logger.info("PDB IDs already provided, skipping UniProt resolution")
        return {"current_phase": "proteins_resolved"}

    # If we have protein names but no PDB IDs, try to resolve via UniProt
    if protein_names and not pdb_ids:
        from ..adapters.uniprot_adapter import UniProtAdapter

        adapter = UniProtAdapter()

        try:
            for name in protein_names:
                logger.info(f"Resolving protein: {name}")
                results = await adapter.search_sequences(name, max_results=1)
                if results:
                    uniprot_id = results[0].uniprot_id
                    if uniprot_id not in uniprot_ids:
                        uniprot_ids.append(uniprot_id)

                    # Get PDB mappings
                    pdb_mappings = await adapter.get_pdb_mapping(uniprot_id)
                    logger.info(f"Found {len(pdb_mappings)} PDB structures for {name}")
                    pdb_ids.extend(pdb_mappings[:3])  # Limit to top 3 per protein

        except Exception as e:
            logger.error(f"UniProt resolution failed: {e}")
        finally:
            await adapter.close()

    # Deduplicate
    pdb_ids = list(dict.fromkeys(pdb_ids))
    uniprot_ids = list(dict.fromkeys(uniprot_ids))

    logger.info(f"Resolved - PDB IDs: {pdb_ids}, UniProt IDs: {uniprot_ids}")

    # Check if we failed to resolve any proteins
    if protein_names and not pdb_ids and not uniprot_ids:
        logger.warning(f"Could not resolve any proteins: {protein_names}")
        return {
            "pdb_ids": [],
            "uniprot_ids": [],
            "protein_names": protein_names,
            "resolution_warning": f"Could not resolve proteins to structures: {', '.join(protein_names)}",
            "current_phase": "proteins_resolved",
        }

    return {
        "pdb_ids": pdb_ids,
        "uniprot_ids": uniprot_ids,
        "protein_names": protein_names,
        "current_phase": "proteins_resolved",
    }


async def literature_node(state: BiotechState) -> dict[str, Any]:
    """Search scientific literature."""
    logger.info("Running literature search...")

    agent = BioLiteratureAgent()

    try:
        result = await agent(state)
        return {**result, "current_phase": "literature_done"}
    except Exception as e:
        logger.error(f"Literature search failed: {e}")
        return {
            "literature_summary": f"Literature search failed: {e}",
            "literature_count": 0,
            "current_phase": "literature_done",
        }
    finally:
        await agent.close()


async def structure_node(state: BiotechState) -> dict[str, Any]:
    """Analyze protein structures."""
    pdb_ids = state.get("pdb_ids", [])

    if not pdb_ids:
        logger.info("No PDB IDs to analyze")
        return {
            "structure_summary": "No protein structures to analyze.",
            "current_phase": "structure_done",
        }

    logger.info(f"Analyzing structures: {pdb_ids}")

    agent = StructureAnalystAgent()

    try:
        result = await agent(state)
        return {**result, "current_phase": "structure_done"}
    except Exception as e:
        logger.error(f"Structure analysis failed: {e}")
        return {
            "structure_error": str(e),
            "structure_summary": f"Structure analysis failed: {e}",
            "current_phase": "structure_done",
        }
    finally:
        await agent.close()


async def drug_node(state: BiotechState) -> dict[str, Any]:
    """Analyze drug-target interactions."""
    has_drug_query = state.get("has_drug_query", False)

    if not has_drug_query:
        logger.info("Not a drug query, skipping drug analysis")
        return {
            "drug_summary": "",
            "current_phase": "drugs_done",
        }

    logger.info("Running drug binding analysis...")

    agent = DrugBindingAgent()

    try:
        result = await agent(state)
        return result
    except Exception as e:
        logger.error(f"Drug analysis failed: {e}")
        return {
            "drug_summary": f"Drug analysis failed: {e}",
            "current_phase": "drugs_done",
        }
    finally:
        await agent.close()


async def synthesis_node(state: BiotechState) -> dict[str, Any]:
    """Synthesize literature and computational evidence using SynthesisAgent."""
    logger.info("Running synthesis...")

    agent = SynthesisAgent()

    try:
        result = await agent(state)
        return result
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        # Fallback to basic synthesis
        query = state.get("query", "")
        lit_count = state.get("literature_count", 0)
        pdb_ids = state.get("analyzed_pdb_ids", [])

        report = f"# Research Report\n\n**Query:** {query}\n\n"
        report += f"Papers found: {lit_count}\n"
        report += f"Structures analyzed: {pdb_ids}\n\n"
        report += f"*Synthesis error: {e}*\n"

        return {
            "synthesis": "Error",
            "final_report": report,
            "current_phase": "done",
        }


def build_biotech_graph() -> CompiledStateGraph:
    """
    Build the biotech research LangGraph.

    Flow:
    parse → resolve_proteins → literature → structure → drugs → synthesis → END
    """
    graph = StateGraph(BiotechState)

    # Add nodes
    graph.add_node("parse", parse_query_node)
    graph.add_node("resolve_proteins", resolve_proteins_node)
    graph.add_node("literature", literature_node)
    graph.add_node("structure", structure_node)
    graph.add_node("drugs", drug_node)
    graph.add_node("synthesis", synthesis_node)

    # Add edges
    graph.add_edge("parse", "resolve_proteins")
    graph.add_edge("resolve_proteins", "literature")
    graph.add_edge("literature", "structure")
    graph.add_edge("structure", "drugs")
    graph.add_edge("drugs", "synthesis")
    graph.add_edge("synthesis", END)

    # Set entry point
    graph.set_entry_point("parse")

    return graph.compile()


async def run_research(query: str) -> dict[str, Any]:
    """
    Run a biotech research query through the full pipeline.

    Args:
        query: Research question (e.g., "What mutations stabilize lysozyme?")

    Returns:
        Final state with report
    """
    # Input validation
    if not query or not query.strip():
        return {
            "error": "Query cannot be empty",
            "final_report": "# Error\n\nQuery cannot be empty. Please provide a research question.",
            "current_phase": "error",
        }

    if len(query) > 2000:
        return {
            "error": "Query too long",
            "final_report": "# Error\n\nQuery exceeds maximum length of 2000 characters.",
            "current_phase": "error",
        }

    # Sanitize control characters
    query = "".join(c for c in query if c.isprintable() or c.isspace())
    query = query.strip()

    graph = build_biotech_graph()

    initial_state = {
        "query": query,
        "root_query": query,
        "current_phase": "init",
    }

    # Run the graph
    final_state = await graph.ainvoke(initial_state)

    return final_state
