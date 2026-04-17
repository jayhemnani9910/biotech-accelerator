"""CLI for Biotech Research Accelerator.

Two modes:

* Full pipeline — `biotech "query"` runs the LangGraph pipeline
  (literature + structure + drugs + synthesis) and prints a markdown report.
* Direct structure analysis — `biotech --pdb 1LYZ 4HHB` skips straight to
  NMA for the given PDB IDs.

Both modes accept `--json` for machine-readable output (ideal when an MCP
client or coding agent is driving via Bash).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import asdict, is_dataclass
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .agents.nodes.structure_analyst import StructureAnalystAgent, analyze_protein_structure
from .graph.biotech_graph import run_research

console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _to_jsonable(obj: Any) -> Any:
    """Recursively convert dataclasses / Paths / enums to JSON-friendly values."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if hasattr(obj, "value"):  # Enum
        return obj.value
    if hasattr(obj, "__fspath__"):  # Path
        return str(obj)
    return obj


async def _structure_analysis(pdb_id: str, emit_json: bool) -> int:
    result = await analyze_protein_structure(pdb_id)

    if emit_json:
        print(json.dumps(_to_jsonable(result), default=str, indent=2))
        return 0 if result.error is None else 1

    if result.error:
        console.print(f"[red]Error: {result.error}[/red]")
        return 1

    console.print(
        Panel(
            Markdown(result.summary),
            title=f"[bold green]Structure Analysis: {pdb_id}[/bold green]",
            border_style="green",
        )
    )
    if result.nma_result:
        console.print(f"\n[dim]Computed {result.nma_result.n_modes} normal modes[/dim]")
        if result.structure:
            console.print(f"[dim]Structure cached at: {result.structure.file_path}[/dim]")
    return 0


async def _full_pipeline(query: str, emit_json: bool) -> int:
    state = await run_research(query)

    if emit_json:
        print(json.dumps(_to_jsonable(state), default=str, indent=2))
        return 0 if "error" not in state else 1

    if state.get("error"):
        console.print(f"[red]Error: {state['error']}[/red]")
        return 1

    report = state.get("final_report") or "No report generated."
    console.print(
        Panel(
            Markdown(report),
            title="[bold cyan]Research Report[/bold cyan]",
            border_style="cyan",
        )
    )
    return 0


async def _structure_fallback(query: str, emit_json: bool) -> int:
    """Legacy path: no query match beyond a PDB id — keep old behaviour."""
    agent = StructureAnalystAgent()
    try:
        pdb_ids = agent.extract_pdb_ids(query)
    finally:
        await agent.close()

    if not pdb_ids:
        if emit_json:
            print(json.dumps({"error": "no_pdb_ids_in_query", "query": query}))
            return 1
        console.print("[yellow]No PDB IDs found in query.[/yellow]")
        console.print("Try: biotech 'Analyze flexibility of PDB 1LYZ'")
        return 1

    exit_code = 0
    for pdb_id in pdb_ids:
        rc = await _structure_analysis(pdb_id, emit_json)
        exit_code = exit_code or rc
    return exit_code


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Biotech Research Accelerator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  biotech "What mutations stabilize lysozyme?"
  biotech "Analyze flexibility of PDB 1LYZ" --json
  biotech --pdb 1LYZ 3HHR 4HHB
  biotech --pdb 1LYZ --json
        """,
    )

    parser.add_argument("query", nargs="?", help="Research query to process")
    parser.add_argument("--pdb", nargs="+", help="PDB ID(s) to analyze directly (skips the graph)")
    parser.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        help="Emit machine-readable JSON on stdout (for agents / piping)",
    )
    parser.add_argument(
        "--structure-only",
        action="store_true",
        help="For a text query, only extract PDB IDs and run structure analysis",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # In JSON mode we suppress Rich banners so stdout stays parseable.
    if not args.emit_json:
        console.print(
            Panel.fit(
                "[bold cyan]Biotech Research Accelerator[/bold cyan]\n"
                "[dim]Multi-agent pipeline for molecular biology research[/dim]",
                border_style="cyan",
            )
        )

    if args.pdb:
        exit_code = 0
        for pdb_id in args.pdb:
            rc = asyncio.run(_structure_analysis(pdb_id.upper(), args.emit_json))
            exit_code = exit_code or rc
        sys.exit(exit_code)
    elif args.query:
        if args.structure_only:
            sys.exit(asyncio.run(_structure_fallback(args.query, args.emit_json)))
        sys.exit(asyncio.run(_full_pipeline(args.query, args.emit_json)))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
