"""
Biotech Research Accelerator - Main Entry Point

CLI for running biotech research queries.
"""

import argparse
import asyncio
import logging
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .agents.nodes.structure_analyst import StructureAnalystAgent, analyze_protein_structure

console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_structure_analysis(pdb_id: str) -> None:
    """Run structure analysis on a PDB ID."""
    console.print(f"\n[bold blue]Analyzing structure: {pdb_id}[/bold blue]\n")

    result = await analyze_protein_structure(pdb_id)

    if result.error:
        console.print(f"[red]Error: {result.error}[/red]")
        return

    # Display results
    console.print(
        Panel(
            Markdown(result.summary),
            title=f"[bold green]Structure Analysis: {pdb_id}[/bold green]",
            border_style="green",
        )
    )

    # Show quick stats
    if result.nma_result:
        nma = result.nma_result
        console.print(f"\n[dim]Computed {nma.n_modes} normal modes[/dim]")
        console.print(f"[dim]Structure cached at: {result.structure.file_path}[/dim]")


async def run_query(query: str) -> None:
    """Run a general research query."""
    console.print(f"\n[bold blue]Processing query:[/bold blue] {query}\n")

    # For now, just do structure analysis if PDB ID detected
    agent = StructureAnalystAgent()
    pdb_ids = agent.extract_pdb_ids(query)

    if pdb_ids:
        console.print(f"[dim]Found PDB IDs: {', '.join(pdb_ids)}[/dim]\n")
        for pdb_id in pdb_ids:
            await run_structure_analysis(pdb_id)
    else:
        console.print("[yellow]No PDB IDs found in query.[/yellow]")
        console.print("Try: biotech 'Analyze flexibility of PDB 1LYZ'")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Biotech Research Accelerator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  biotech "Analyze flexibility of PDB 1LYZ"
  biotech --pdb 1LYZ
  biotech --pdb 1LYZ 3HHR 4HHB
        """,
    )

    parser.add_argument(
        "query",
        nargs="?",
        help="Research query to process",
    )

    parser.add_argument(
        "--pdb",
        nargs="+",
        help="PDB ID(s) to analyze directly",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Print banner
    console.print(
        Panel.fit(
            "[bold cyan]Biotech Research Accelerator[/bold cyan]\n"
            "[dim]Multi-agent AI for molecular biology research[/dim]",
            border_style="cyan",
        )
    )

    if args.pdb:
        # Direct PDB analysis
        for pdb_id in args.pdb:
            asyncio.run(run_structure_analysis(pdb_id.upper()))
    elif args.query:
        # Process query
        asyncio.run(run_query(args.query))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
