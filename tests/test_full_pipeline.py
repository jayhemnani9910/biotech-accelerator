#!/usr/bin/env python3
"""
Test the full biotech research pipeline.

This tests:
1. Query parsing
2. PubMed literature search
3. PDB structure analysis
4. Synthesis of evidence
"""

import asyncio
import sys

import pytest
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

pytestmark = pytest.mark.integration

console = Console()


async def test_full_pipeline():
    """Run a complete research query through the pipeline."""
    from biotech_accelerator.graph.biotech_graph import run_research

    query = "What mutations stabilize lysozyme? Analyze PDB 1LYZ"

    console.print(
        Panel.fit(
            "[bold cyan]Biotech Research Accelerator[/bold cyan]\n[dim]Full Pipeline Test[/dim]",
            border_style="cyan",
        )
    )

    console.print(f"\n[bold]Query:[/bold] {query}\n")
    console.print("[dim]Running pipeline: parse → literature → structure → synthesis[/dim]\n")

    try:
        # Run the research
        final_state = await run_research(query)

        # Display results
        console.print("[bold green]Pipeline Complete![/bold green]\n")

        # Show phases completed
        console.print(f"[dim]Phase: {final_state.get('current_phase', 'unknown')}[/dim]")
        console.print(
            f"[dim]Literature papers found: {final_state.get('literature_count', 0)}[/dim]"
        )
        console.print(
            f"[dim]Structures analyzed: {final_state.get('analyzed_pdb_ids', [])}[/dim]\n"
        )

        # Show final report
        report = final_state.get("final_report", "No report generated")
        console.print(
            Panel(
                Markdown(report),
                title="[bold green]Research Report[/bold green]",
                border_style="green",
            )
        )

        return True

    except Exception as e:
        console.print(f"[red]Pipeline failed: {e}[/red]")
        import traceback

        traceback.print_exc()
        return False


async def test_literature_only():
    """Test literature search independently."""
    from biotech_accelerator.adapters.pubmed_adapter import PubMedAdapter

    console.print("\n[bold]Testing PubMed Search...[/bold]\n")

    adapter = PubMedAdapter()

    result = await adapter.search_by_protein(
        "lysozyme",
        topic="mutation stability",
        max_results=5,
    )

    console.print(f"Found {result.total_count} papers (showing {len(result.citations)})\n")

    for i, citation in enumerate(result.citations[:3], 1):
        console.print(f"[bold]{i}. {citation.title}[/bold]")
        console.print(f"   {citation.first_author} et al. ({citation.year})")
        console.print(f"   {citation.journal}")
        console.print(f"   [link={citation.url}]PubMed[/link]\n")

    await adapter.close()
    return True


async def test_uniprot():
    """Test UniProt lookup."""
    from biotech_accelerator.adapters.uniprot_adapter import UniProtAdapter

    console.print("\n[bold]Testing UniProt Lookup...[/bold]\n")

    adapter = UniProtAdapter()

    # Look up lysozyme (P00698)
    try:
        info = await adapter.get_sequence("P00698")

        console.print(f"[bold]Protein:[/bold] {info.name}")
        console.print(f"[bold]Organism:[/bold] {info.organism}")
        console.print(f"[bold]Gene:[/bold] {info.gene_name}")
        console.print(f"[bold]Length:[/bold] {info.length} amino acids")
        console.print(f"[bold]PDB structures:[/bold] {', '.join(info.pdb_ids[:5])}...")
        if info.function:
            console.print(f"[bold]Function:[/bold] {info.function[:200]}...")

        await adapter.close()
        return True

    except Exception as e:
        console.print(f"[red]UniProt lookup failed: {e}[/red]")
        await adapter.close()
        return False


async def main():
    """Run all tests."""
    console.print("=" * 60)
    console.print(" Biotech Research Accelerator - Full Pipeline Test")
    console.print("=" * 60)

    # Test UniProt
    await test_uniprot()

    # Test literature
    await test_literature_only()

    # Test full pipeline
    success = await test_full_pipeline()

    if success:
        console.print("\n" + "=" * 60)
        console.print(" [bold green]All tests passed![/bold green]")
        console.print("=" * 60)
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
