"""Unit tests for NMA flexibility analysis — pure numeric logic, no I/O.

These pin the residue-numbering contract: everything NMAAnalyzer reports must be
expressed in the structure's own residue numbers, never in Ca-array indices.
"""

import numpy as np

from biotech_accelerator.analysis.nma_wrapper import NMAAnalyzer


def _analyzer() -> NMAAnalyzer:
    return NMAAnalyzer(n_modes=10)


def _flat(n: int, hot: range, low: float = 1.0, high: float = 10.0) -> np.ndarray:
    """Fluctuation profile that is `low` everywhere except `hot`, which is `high`.

    Kept sparse on purpose: a region only counts as flexible above 1.5x the mean,
    so the hot span has to stay a small fraction of the structure.
    """
    fluct = np.full(n, low)
    fluct[list(hot)] = high
    return fluct


# --- regions are reported in residue-number space --------------------------


def test_flexible_regions_use_residue_numbers_not_indices():
    """A structure numbered from 101 must report regions in the 101+ space."""
    fluct = _flat(20, range(5, 8))
    resnums = np.arange(101, 121)
    chains = np.array(["A"] * 20)

    metrics = _analyzer()._analyze_flexibility(fluct, resnums, chains)

    assert metrics.flexible_regions == [(106, 108)]


def test_hinge_residues_use_residue_numbers_not_indices():
    # A varied profile, so the 90th-percentile gradient cut selects something.
    rng = np.random.default_rng(7)
    fluct = rng.random(20) + 0.2
    resnums = np.arange(101, 121)
    chains = np.array(["A"] * 20)

    metrics = _analyzer()._analyze_flexibility(fluct, resnums, chains)

    assert metrics.hinge_residues, "expected at least one hinge"
    # Indices would be 0..19; residue numbers are 101..120. The two do not overlap.
    assert all(h in resnums.tolist() for h in metrics.hinge_residues)
    assert all(isinstance(h, int) for h in metrics.hinge_residues)


# --- gaps in the deposited structure must break a region -------------------


def test_region_splits_across_a_gap_in_residue_numbering():
    """Unresolved residues create a numbering gap; a region must not span it."""
    fluct = _flat(20, range(5, 11))
    # 100..107, then the structure jumps to 130..141 (residues 108-129 unresolved)
    resnums = np.concatenate([np.arange(100, 108), np.arange(130, 142)])
    chains = np.array(["A"] * 20)

    metrics = _analyzer()._analyze_flexibility(fluct, resnums, chains, min_region_size=3)

    assert metrics.flexible_regions == [(105, 107), (130, 132)]


def test_region_splits_across_a_chain_boundary():
    """Numbering can run on across a chain break; the region still must not."""
    fluct = _flat(20, range(5, 11))
    resnums = np.arange(10, 30)  # deliberately contiguous across the boundary
    chains = np.array(["A"] * 8 + ["B"] * 12)

    metrics = _analyzer()._analyze_flexibility(fluct, resnums, chains, min_region_size=3)

    assert metrics.flexible_regions == [(15, 17), (18, 20)]


# --- regions must stay inside the structure's real residue range -----------


def test_all_reported_positions_fall_inside_the_structures_residue_range():
    rng = np.random.default_rng(0)
    fluct = rng.random(60) + 0.2
    resnums = np.arange(201, 261)
    chains = np.array(["A"] * 60)

    metrics = _analyzer()._analyze_flexibility(fluct, resnums, chains)

    lo, hi = int(resnums[0]), int(resnums[-1])
    for start, end in metrics.flexible_regions + metrics.rigid_regions:
        assert lo <= start <= end <= hi, f"region ({start}, {end}) outside {lo}-{hi}"
    for hinge in metrics.hinge_residues:
        assert lo <= hinge <= hi, f"hinge {hinge} outside {lo}-{hi}"
