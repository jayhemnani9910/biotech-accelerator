"""Read NMA flexibility data out of graph state.

`structure_node` puts a list of StructureAnalysisResult into
state["structure_analysis"], each carrying an NMAResult with typed
FlexibilityMetrics. Downstream nodes read it from here rather than
regex-scanning the rendered markdown summary, which could not distinguish
"pattern did not match" from "this protein has no hinges".
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# (hinge_residues, flexible_regions, rigid_regions) — all in deposited residue numbers.
StructuralContext = tuple[list[int], list[tuple[int, int]], list[tuple[int, int]]]

EMPTY: StructuralContext = ([], [], [])


def resolved_residues(state: dict[str, Any]) -> Optional[set[int]]:
    """Residue numbers present in the analysed structure, or None if unknown.

    None and the empty set mean different things: None is "we have no roster to
    check against", the empty set would be "this structure resolved nothing".
    """
    analyses = state.get("structure_analysis") or []
    if not isinstance(analyses, list):
        return None

    for analysis in analyses:
        nma = getattr(analysis, "nma_result", None)
        if nma is not None and nma.residue_numbers:
            return {int(r) for r in nma.residue_numbers}
    return None


def structural_context(state: dict[str, Any]) -> StructuralContext:
    """Pull hinge residues and flexible/rigid regions from the analysed structures.

    Only the first successfully analysed structure is used. Residue numbers from
    two different proteins are not comparable, so merging them would produce
    cross-references between a mutation in one protein and a hinge in another.
    Any additional structures are logged and skipped.
    """
    analyses = state.get("structure_analysis") or []
    if not isinstance(analyses, list):
        return EMPTY

    usable = [a for a in analyses if getattr(a, "nma_result", None) is not None]
    if not usable:
        return EMPTY

    if len(usable) > 1:
        skipped = ", ".join(str(getattr(a, "pdb_id", "?")) for a in usable[1:])
        logger.info(
            f"Cross-referencing against {usable[0].pdb_id} only; "
            f"residue numbering is not comparable across structures (skipped: {skipped})"
        )

    flexibility = usable[0].nma_result.flexibility
    return (
        list(flexibility.hinge_residues),
        [tuple(r) for r in flexibility.flexible_regions],
        [tuple(r) for r in flexibility.rigid_regions],
    )
