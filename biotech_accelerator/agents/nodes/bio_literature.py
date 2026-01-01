"""
Bio Literature Agent

Searches scientific literature for biotech research,
combining PubMed with protein-specific queries.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from ...adapters.pubmed_adapter import PubMedAdapter
from ...adapters.uniprot_adapter import UniProtAdapter
from ...ports.literature import Citation, LiteratureSearchResult

logger = logging.getLogger(__name__)


@dataclass
class LiteratureEvidence:
    """Evidence extracted from literature."""

    citation: Citation
    relevance_score: float
    key_findings: list[str]
    mentions_mutations: bool = False
    mentions_stability: bool = False
    mentions_binding: bool = False


class BioLiteratureAgent:
    """
    Agent that searches and analyzes scientific literature.

    Capabilities:
    - Search PubMed for protein-related papers
    - Extract relevant findings from abstracts
    - Identify mutation and stability mentions
    - Cross-reference with UniProt data
    """

    # Patterns for extracting information
    MUTATION_PATTERN = re.compile(
        r"\b([A-Z])(\d+)([A-Z])\b"  # e.g., A42G, R206W
    )
    STABILITY_KEYWORDS = [
        "stability",
        "stabiliz",
        "destabiliz",
        "thermostab",
        "melting",
        "Tm",
        "ΔΔG",
        "ddG",
        "folding",
        "unfolding",
    ]
    BINDING_KEYWORDS = [
        "binding",
        "affinity",
        "IC50",
        "Ki",
        "Kd",
        "inhibit",
        "agonist",
        "antagonist",
        "ligand",
        "substrate",
    ]

    def __init__(
        self,
        pubmed_adapter: Optional[PubMedAdapter] = None,
        uniprot_adapter: Optional[UniProtAdapter] = None,
    ):
        self.pubmed = pubmed_adapter or PubMedAdapter()
        self.uniprot = uniprot_adapter or UniProtAdapter()

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        LangGraph node entry point.

        Args:
            state: Current graph state with 'query' and optional protein context

        Returns:
            Updated state with literature evidence
        """
        query = state.get("query", "") or state.get("root_query", "")
        pdb_ids = state.get("pdb_ids", [])
        target_proteins = state.get("target_proteins", [])
        protein_names = state.get("protein_names", [])  # Also get simple string names

        # Build search queries
        search_results = []

        # Main query search
        logger.info(f"Searching PubMed for: {query}")
        main_result = await self.pubmed.search(query, max_results=10)
        search_results.extend(main_result.citations)

        # Protein-specific searches (ProteinContext objects)
        for protein in target_proteins:
            if hasattr(protein, "name") and protein.name:
                logger.info(f"Searching for protein context: {protein.name}")
                protein_result = await self.pubmed.search_by_protein(
                    protein.name,
                    topic="mutation OR stability",
                    max_results=5,
                )
                search_results.extend(protein_result.citations)

        # Fallback: search using simple protein name strings
        for protein_name in protein_names:
            if protein_name and len(protein_name) > 2:
                logger.info(f"Searching for protein name: {protein_name}")
                protein_result = await self.pubmed.search_by_protein(
                    protein_name,
                    topic="mutation OR stability",
                    max_results=5,
                )
                search_results.extend(protein_result.citations)

        # Deduplicate by PMID
        seen_pmids = set()
        unique_citations = []
        for citation in search_results:
            if citation.pmid and citation.pmid not in seen_pmids:
                seen_pmids.add(citation.pmid)
                unique_citations.append(citation)
            elif not citation.pmid:
                unique_citations.append(citation)

        # Analyze each citation
        evidence_list = []
        for citation in unique_citations[:15]:  # Limit to top 15
            evidence = self._analyze_citation(citation, query)
            evidence_list.append(evidence)

        # Sort by relevance
        evidence_list.sort(key=lambda e: e.relevance_score, reverse=True)

        # Generate literature summary
        summary = self._generate_summary(evidence_list, query)

        return {
            "literature_citations": unique_citations,
            "literature_evidence": evidence_list,
            "literature_summary": summary,
            "literature_count": len(unique_citations),
        }

    def _analyze_citation(self, citation: Citation, query: str) -> LiteratureEvidence:
        """Analyze a citation for relevance and key findings."""
        text = f"{citation.title} {citation.abstract or ''}"
        text_lower = text.lower()
        query_lower = query.lower()

        # Calculate relevance score
        relevance = 0.0

        # Query term matching
        query_terms = query_lower.split()
        for term in query_terms:
            if len(term) > 3 and term in text_lower:
                relevance += 0.1

        # Check for mutations
        mentions_mutations = bool(self.MUTATION_PATTERN.search(text))
        if mentions_mutations:
            relevance += 0.2

        # Check for stability keywords
        mentions_stability = any(kw in text_lower for kw in self.STABILITY_KEYWORDS)
        if mentions_stability:
            relevance += 0.15

        # Check for binding keywords
        mentions_binding = any(kw in text_lower for kw in self.BINDING_KEYWORDS)
        if mentions_binding:
            relevance += 0.15

        # Recency bonus
        if citation.year and citation.year >= 2020:
            relevance += 0.1

        # Cap at 1.0
        relevance = min(relevance, 1.0)

        # Extract key findings (simplified - just extract sentences with keywords)
        key_findings = []
        if citation.abstract:
            sentences = citation.abstract.split(". ")
            for sentence in sentences:
                sentence_lower = sentence.lower()
                if any(
                    kw in sentence_lower for kw in self.STABILITY_KEYWORDS + self.BINDING_KEYWORDS
                ):
                    key_findings.append(sentence.strip())
                    if len(key_findings) >= 3:
                        break

        return LiteratureEvidence(
            citation=citation,
            relevance_score=relevance,
            key_findings=key_findings,
            mentions_mutations=mentions_mutations,
            mentions_stability=mentions_stability,
            mentions_binding=mentions_binding,
        )

    def _generate_summary(
        self,
        evidence_list: list[LiteratureEvidence],
        query: str,
    ) -> str:
        """Generate a summary of literature findings."""
        if not evidence_list:
            return "No relevant literature found."

        # Count papers by topic
        mutation_papers = sum(1 for e in evidence_list if e.mentions_mutations)
        stability_papers = sum(1 for e in evidence_list if e.mentions_stability)
        binding_papers = sum(1 for e in evidence_list if e.mentions_binding)

        # Top papers
        top_papers = evidence_list[:5]

        parts = [
            "## Literature Review\n",
            f"**Query:** {query}\n",
            f"**Papers found:** {len(evidence_list)}\n",
            f"- Mentioning mutations: {mutation_papers}",
            f"- Mentioning stability: {stability_papers}",
            f"- Mentioning binding: {binding_papers}\n",
            "\n### Key Papers:\n",
        ]

        for i, ev in enumerate(top_papers, 1):
            c = ev.citation
            parts.append(f"**{i}. {c.title}**")
            parts.append(f"   - {c.first_author} et al. ({c.year}), {c.journal}")
            parts.append(f"   - Relevance: {ev.relevance_score:.2f}")
            if ev.key_findings:
                parts.append(f"   - Key finding: {ev.key_findings[0][:200]}...")
            parts.append("")

        return "\n".join(parts)

    async def close(self):
        """Close adapters."""
        await self.pubmed.close()
        await self.uniprot.close()


# Convenience function
async def search_biotech_literature(query: str, max_results: int = 10) -> LiteratureSearchResult:
    """Quick search for biotech literature."""
    agent = BioLiteratureAgent()
    result = await agent.pubmed.search(query, max_results=max_results)
    await agent.close()
    return result
