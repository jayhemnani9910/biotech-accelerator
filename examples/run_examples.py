#!/usr/bin/env python3
"""
Example queries for Biotech Research Accelerator.

Demonstrates the three main use cases:
1. Protein stability analysis
2. Drug discovery
3. Combined research
"""

import asyncio
import sys
from pathlib import Path

# Add package to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()


async def run_query(query: str, title: str):
    """Run a research query and display results."""
    from biotech_accelerator.graph.biotech_graph import run_research

    console.print(
        Panel.fit(
            f"[bold cyan]{title}[/bold cyan]\n[dim]{query}[/dim]",
            border_style="cyan",
        )
    )

    console.print("\n[dim]Running pipeline...[/dim]\n")

    result = await run_research(query)

    # Show summary stats
    console.print(f"[green]✓[/green] Literature: {result.get('literature_count', 0)} papers")
    console.print(
        f"[green]✓[/green] Structures: {len(result.get('analyzed_pdb_ids', []))} analyzed"
    )
    console.print(f"[green]✓[/green] Drug insights: {len(result.get('drug_insights', []))}")
    console.print()

    # Show report
    report = result.get("final_report", "No report generated")
    console.print(
        Panel(
            Markdown(report),
            title="[bold green]Research Report[/bold green]",
            border_style="green",
        )
    )

    return result


async def example_stability():
    """Example 1: Protein stability analysis."""
    return await run_query(
        "What mutations stabilize lysozyme? Analyze PDB 1LYZ",
        "Example 1: Protein Stability Analysis",
    )


async def example_drug_discovery():
    """Example 2: Drug discovery."""
    return await run_query("Find inhibitors for EGFR kinase", "Example 2: Drug Discovery")


async def example_combined():
    """Example 3: Combined research."""
    return await run_query(
        "Analyze BRAF V600E mutation and find inhibitors", "Example 3: Combined Research"
    )


async def main():
    """Run all examples."""
    console.print("=" * 70)
    console.print(" [bold]Biotech Research Accelerator - Examples[/bold]")
    console.print("=" * 70)
    console.print()

    # Menu
    console.print("Select an example to run:")
    console.print("  [1] Protein stability analysis (lysozyme)")
    console.print("  [2] Drug discovery (EGFR inhibitors)")
    console.print("  [3] Combined research (BRAF V600E)")
    console.print("  [4] Run all examples")
    console.print("  [q] Quit")
    console.print()

    choice = input("Enter choice (1-4, q): ").strip().lower()

    if choice == "1":
        await example_stability()
    elif choice == "2":
        await example_drug_discovery()
    elif choice == "3":
        await example_combined()
    elif choice == "4":
        await example_stability()
        console.print("\n" + "=" * 70 + "\n")
        await example_drug_discovery()
        console.print("\n" + "=" * 70 + "\n")
        await example_combined()
    elif choice == "q":
        console.print("Goodbye!")
    else:
        console.print("[red]Invalid choice[/red]")


if __name__ == "__main__":
    asyncio.run(main())
