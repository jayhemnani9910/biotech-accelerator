"""One JSON conversion shared by the CLI (`--json`) and every MCP tool.

There used to be two of these — `main._to_jsonable` and `mcp_server._serialize` —
which disagreed about enums, Paths and numpy arrays, so the same structure came
out differently depending on which entry point you asked. Order matters below:
an Enum member has a `__dict__`, so a generic `vars()` branch placed first will
expand it into `_value_` / `_name_` / `__objclass__` instead of its value.
"""

from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import PurePath
from typing import Any

import numpy as np


def to_jsonable(obj: Any) -> Any:
    """Recursively convert an object into something `json.dumps` accepts.

    Handles dataclasses, enums, paths, numpy arrays and numpy scalars. Callers
    should not need `default=str`; if they do, a type is missing from here.
    """
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return to_jsonable(obj.value)
    if isinstance(obj, PurePath):
        return str(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.generic):  # np.int64, np.float64, np.bool_, ...
        return obj.item()
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    return obj
