"""Adapter cleanup on server shutdown.

The MCP server keeps one adapter instance per source for the life of the
process, each holding an httpx.AsyncClient. Nothing closed them: BaseAdapter
used to carry a __del__ that scheduled aclose() and dropped the task, which was
removed because it never reliably ran. MCPServer takes a lifespan, so shutdown
has a real hook to hang cleanup on.
"""

import pytest

from biotech_accelerator import mcp_server


class _Adapter:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class _AdapterThatFailsToClose:
    def __init__(self):
        self.closed = False

    async def close(self):
        raise RuntimeError("connection already gone")


@pytest.fixture(autouse=True)
def _clean_registry(monkeypatch):
    monkeypatch.setattr(mcp_server, "_adapters", {})


async def test_lifespan_closes_every_registered_adapter():
    a, b = _Adapter(), _Adapter()
    mcp_server._adapters.update({"pubmed": a, "chembl": b})

    async with mcp_server._lifespan(mcp_server.mcp):
        pass

    assert a.closed and b.closed


async def test_lifespan_empties_the_registry():
    mcp_server._adapters["pubmed"] = _Adapter()

    async with mcp_server._lifespan(mcp_server.mcp):
        pass

    assert mcp_server._adapters == {}


async def test_one_adapter_failing_to_close_does_not_strand_the_others():
    """Shutdown is best-effort; a broken connection must not skip the rest."""
    bad, good = _AdapterThatFailsToClose(), _Adapter()
    mcp_server._adapters.update({"bad": bad, "good": good})

    async with mcp_server._lifespan(mcp_server.mcp):
        pass

    assert good.closed


async def test_adapters_are_still_usable_inside_the_lifespan():
    a = _Adapter()
    mcp_server._adapters["pubmed"] = a

    async with mcp_server._lifespan(mcp_server.mcp):
        assert a.closed is False

    assert a.closed is True


def test_the_server_is_wired_to_the_lifespan():
    """A lifespan that is never registered cleans nothing up."""
    assert mcp_server.mcp.settings.lifespan is mcp_server._lifespan
