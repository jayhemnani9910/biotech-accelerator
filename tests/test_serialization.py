"""The JSON contract shared by the CLI (--json) and every MCP tool.

Both entry points must describe the same object the same way, and the result
must survive json.dumps without a custom encoder.
"""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np

from biotech_accelerator.utils.serialization import to_jsonable


class Colour(Enum):
    RED = "red"


@dataclass
class Inner:
    tag: str
    weight: float


@dataclass
class Outer:
    name: str
    path: Path
    colour: Colour
    inner: Inner
    values: np.ndarray
    items: Optional[list] = None


def _sample() -> Outer:
    return Outer(
        name="x",
        path=Path("/tmp/x.pdb"),
        colour=Colour.RED,
        inner=Inner(tag="t", weight=1.5),
        values=np.array([1.0, 2.0, 3.0]),
        items=[Inner(tag="a", weight=0.5)],
    )


# --- the three types that were being mangled -------------------------------


def test_enum_becomes_its_value_not_its_internals():
    assert to_jsonable(Colour.RED) == "red"


def test_path_becomes_a_string():
    assert to_jsonable(Path("/tmp/x.pdb")) == "/tmp/x.pdb"


def test_ndarray_becomes_a_list_not_a_repr_string():
    out = to_jsonable(np.array([[1.0, 2.0], [3.0, 4.0]]))
    assert out == [[1.0, 2.0], [3.0, 4.0]]


def test_numpy_scalars_become_python_scalars():
    assert to_jsonable(np.int64(7)) == 7
    assert isinstance(to_jsonable(np.int64(7)), int)
    assert to_jsonable(np.float64(1.5)) == 1.5
    assert isinstance(to_jsonable(np.float64(1.5)), float)


# --- the whole-object contract ---------------------------------------------


def test_nested_dataclass_survives_json_dumps():
    out = to_jsonable(_sample())
    blob = json.dumps(out)  # must not need default=str

    round_tripped = json.loads(blob)
    assert round_tripped == {
        "name": "x",
        "path": "/tmp/x.pdb",
        "colour": "red",
        "inner": {"tag": "t", "weight": 1.5},
        "values": [1.0, 2.0, 3.0],
        "items": [{"tag": "a", "weight": 0.5}],
    }


def test_no_python_internals_leak_into_output():
    blob = json.dumps(to_jsonable(_sample()))
    for leaked in ("_value_", "_name_", "__objclass__", "_sort_order_", "PosixPath"):
        assert leaked not in blob, f"{leaked} leaked into the JSON payload"


def test_cli_and_mcp_agree_on_the_same_object():
    """The two entry points used to produce different JSON for one structure."""
    from biotech_accelerator.main import _to_jsonable as cli_serializer
    from biotech_accelerator.mcp_server import _serialize as mcp_serializer

    sample = _sample()
    assert cli_serializer(sample) == mcp_serializer(sample)
