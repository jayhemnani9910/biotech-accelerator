"""Error-path tests for BaseAdapter and per-adapter error mapping.

Uses httpx.MockTransport to simulate HTTP responses without network I/O.
"""

import json

import httpx
import pytest

from biotech_accelerator.adapters.base import (
    AdapterHTTPError,
    AdapterNotFound,
    AdapterParseError,
    AdapterTimeout,
    BaseAdapter,
)
from biotech_accelerator.adapters.chembl_adapter import (
    ChEMBLAdapter,
    CompoundNotFoundError,
)
from biotech_accelerator.adapters.uniprot_adapter import UniProtAdapter
from biotech_accelerator.ports.sequence import SequenceNotFoundError


def _make_adapter(adapter_cls, handler, **kwargs):
    """Build an adapter whose httpx client is wired to a MockTransport handler."""
    adapter = adapter_cls(**kwargs)
    adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    # Faster retries in tests.
    adapter._max_retries = 2
    adapter._backoff_base = 0.01
    return adapter


# --- BaseAdapter error semantics -------------------------------------------


async def test_base_adapter_404_raises_not_found():
    def handler(request):
        return httpx.Response(404, text="nope")

    adapter = _make_adapter(BaseAdapter, handler)
    try:
        with pytest.raises(AdapterNotFound):
            await adapter._get_json("https://example.com/missing")
    finally:
        await adapter.close()


async def test_base_adapter_500_retries_then_raises_http_error():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(500, text="boom")

    adapter = _make_adapter(BaseAdapter, handler)
    try:
        with pytest.raises(AdapterHTTPError) as exc_info:
            await adapter._get_json("https://example.com/flaky")
        assert exc_info.value.status_code == 500
        assert calls["n"] == 2  # retried once before giving up
    finally:
        await adapter.close()


async def test_base_adapter_400_raises_without_retry():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(400, text="bad")

    adapter = _make_adapter(BaseAdapter, handler)
    try:
        with pytest.raises(AdapterHTTPError):
            await adapter._get_json("https://example.com/bad")
        assert calls["n"] == 1  # no retry on non-retryable 4xx
    finally:
        await adapter.close()


async def test_base_adapter_timeout_raises_timeout():
    def handler(request):
        raise httpx.ConnectTimeout("slow", request=request)

    adapter = _make_adapter(BaseAdapter, handler)
    try:
        with pytest.raises(AdapterTimeout):
            await adapter._get_json("https://example.com/slow")
    finally:
        await adapter.close()


async def test_base_adapter_invalid_json_raises_parse_error():
    def handler(request):
        return httpx.Response(200, text="not-json{")

    adapter = _make_adapter(BaseAdapter, handler)
    try:
        with pytest.raises(AdapterParseError):
            await adapter._get_json("https://example.com/ok")
    finally:
        await adapter.close()


async def test_base_adapter_retries_on_429_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="slow down")
        return httpx.Response(200, json={"ok": True})

    adapter = _make_adapter(BaseAdapter, handler)
    try:
        data = await adapter._get_json("https://example.com/rate")
        assert data == {"ok": True}
        assert calls["n"] == 2
    finally:
        await adapter.close()


# --- UniProtAdapter maps AdapterNotFound → SequenceNotFoundError -----------


async def test_uniprot_get_sequence_404_raises_sequence_not_found():
    def handler(request):
        return httpx.Response(404)

    adapter = _make_adapter(UniProtAdapter, handler)
    try:
        with pytest.raises(SequenceNotFoundError):
            await adapter.get_sequence("Q99999")
    finally:
        await adapter.close()


async def test_uniprot_search_sequences_404_returns_empty():
    def handler(request):
        return httpx.Response(404)

    adapter = _make_adapter(UniProtAdapter, handler)
    try:
        result = await adapter.search_sequences("nothing")
        assert result == []
    finally:
        await adapter.close()


async def test_uniprot_get_pdb_mapping_swallows_not_found():
    def handler(request):
        return httpx.Response(404)

    adapter = _make_adapter(UniProtAdapter, handler)
    try:
        ids = await adapter.get_pdb_mapping("Q99999")
        assert ids == []
    finally:
        await adapter.close()


# --- ChEMBLAdapter maps AdapterNotFound → CompoundNotFoundError ------------


async def test_chembl_get_by_id_404_raises_compound_not_found():
    def handler(request):
        return httpx.Response(404)

    adapter = _make_adapter(ChEMBLAdapter, handler)
    try:
        with pytest.raises(CompoundNotFoundError):
            await adapter._get_by_chembl_id("CHEMBL000000")
    finally:
        await adapter.close()


async def test_chembl_search_by_target_404_returns_empty():
    def handler(request):
        return httpx.Response(404)

    adapter = _make_adapter(ChEMBLAdapter, handler)
    try:
        # _find_target will swallow the 404 and return None → empty list.
        results = await adapter.search_by_target("nonexistent-target")
        assert results == []
    finally:
        await adapter.close()


# --- ResponseCache error handling -----------------------------------------


def test_cache_round_trip(tmp_path):
    from biotech_accelerator.utils.cache import ResponseCache

    cache = ResponseCache(cache_dir=tmp_path)
    cache.set("ns", "key", {"answer": 42}, ttl=60)
    assert cache.get("ns", "key") == {"answer": 42}


def test_cache_missing_returns_none(tmp_path):
    from biotech_accelerator.utils.cache import ResponseCache

    cache = ResponseCache(cache_dir=tmp_path)
    assert cache.get("ns", "missing") is None


def test_cache_expired_returns_none_and_cleans_up(tmp_path):
    from biotech_accelerator.utils.cache import ResponseCache

    cache = ResponseCache(cache_dir=tmp_path)
    cache.set("ns", "k", "v", ttl=-1)  # already expired
    assert cache.get("ns", "k") is None
    # File should have been unlinked.
    assert list(tmp_path.glob("*.json")) == []


def test_cache_corrupted_file_returns_none(tmp_path):
    from biotech_accelerator.utils.cache import ResponseCache

    cache = ResponseCache(cache_dir=tmp_path)
    # Force a corrupted cache file at the expected path.
    path = cache._get_cache_path("ns", "k")
    path.write_text("{not-json")
    assert cache.get("ns", "k") is None


def test_cache_reads_legacy_format(tmp_path):
    from biotech_accelerator.utils.cache import ResponseCache

    cache = ResponseCache(cache_dir=tmp_path)
    path = cache._get_cache_path("ns", "legacy")
    path.write_text(json.dumps({"data": "hello", "expires_at": 2**32}))
    assert cache.get("ns", "legacy") == "hello"
