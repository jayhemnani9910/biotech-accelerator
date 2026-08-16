"""PubMed query construction.

The date bounds are independent parameters on the search_literature MCP tool, so
every combination has to produce a well-formed E-utilities term. A filter that
is silently dropped returns plausible-looking unfiltered results.
"""

from datetime import date

from biotech_accelerator.adapters.pubmed_adapter import PubMedAdapter


def _filter(date_from=None, date_to=None) -> str:
    return PubMedAdapter()._date_filter(date_from, date_to)


def test_no_dates_adds_no_filter():
    assert _filter() == ""


def test_both_bounds_produce_a_range():
    out = _filter(date(2020, 1, 1), date(2024, 1, 1))
    assert out == " AND 2020/01/01:2024/01/01[PDAT]"


def test_lower_bound_only_is_open_ended_upward():
    out = _filter(date_from=date(2020, 1, 1))
    assert out == " AND 2020/01/01:3000/01/01[PDAT]"


def test_upper_bound_only_is_open_ended_downward():
    """This used to emit ' : 2024/01/01[PDAT]' with no AND — silently ignored."""
    out = _filter(date_to=date(2024, 1, 1))
    assert out == " AND 1000/01/01:2024/01/01[PDAT]"


def test_every_combination_is_joined_with_and():
    combos = [
        (date(2020, 1, 1), None),
        (None, date(2024, 1, 1)),
        (date(2020, 1, 1), date(2024, 1, 1)),
    ]
    for lo, hi in combos:
        out = _filter(lo, hi)
        assert out.startswith(" AND "), f"{lo}/{hi} produced a dangling clause: {out!r}"
        assert out.endswith("[PDAT]")
