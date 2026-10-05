"""Regression tests for adapter and cache bugs found in the 2026-10 audit.

Uses httpx.MockTransport to simulate HTTP responses without network I/O.
"""

import gzip
import json
import time
import xml.etree.ElementTree as ET

import httpx
import pytest

from biotech_accelerator.adapters.base import AdapterTimeout, BaseAdapter
from biotech_accelerator.adapters.chembl_adapter import ChEMBLAdapter
from biotech_accelerator.adapters.pdb_adapter import PDBAdapter
from biotech_accelerator.adapters.pubmed_adapter import PubMedAdapter
from biotech_accelerator.adapters.uniprot_adapter import UniProtAdapter
from biotech_accelerator.ports.structure import StructureNotFoundError
from biotech_accelerator.utils.cache import ResponseCache


def _make_adapter(adapter_cls, handler, **kwargs):
    """Build an adapter whose httpx client is wired to a MockTransport handler."""
    adapter = adapter_cls(**kwargs)
    adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter._max_retries = 2
    adapter._backoff_base = 0.01
    return adapter


# --- BaseAdapter -----------------------------------------------------------


async def test_base_adapter_retries_read_error_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadError("connection reset", request=request)
        return httpx.Response(200, json={"ok": True})

    adapter = _make_adapter(BaseAdapter, handler)
    try:
        assert await adapter._get_json("https://example.com/x") == {"ok": True}
        assert calls["n"] == 2
    finally:
        await adapter.close()


async def test_base_adapter_wraps_protocol_error_after_retries():
    def handler(request):
        raise httpx.RemoteProtocolError("server disconnected", request=request)

    adapter = _make_adapter(BaseAdapter, handler)
    try:
        with pytest.raises(AdapterTimeout):
            await adapter._get_json("https://example.com/x")
    finally:
        await adapter.close()


async def test_base_adapter_reports_last_error_not_earlier_status():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        raise httpx.ReadTimeout("slow", request=request)

    adapter = _make_adapter(BaseAdapter, handler)
    try:
        with pytest.raises(AdapterTimeout):
            await adapter._get_json("https://example.com/x")
    finally:
        await adapter.close()


# --- ResponseCache ---------------------------------------------------------


def test_cache_ttl_zero_is_not_the_default(tmp_path):
    cache = ResponseCache(cache_dir=tmp_path)
    cache.set("ns", "k", "v", ttl=0)

    stored = json.loads(cache._get_cache_path("ns", "k").read_text())
    assert stored["expiration"] <= time.time()


def test_cache_non_object_json_is_a_miss(tmp_path):
    cache = ResponseCache(cache_dir=tmp_path)
    cache._get_cache_path("ns", "k").write_text("[1, 2, 3]")

    assert cache.get("ns", "k") is None
    assert cache.stats()["expired_count"] == 1


# --- ChEMBLAdapter ---------------------------------------------------------

_TARGET = {
    "target_chembl_id": "CHEMBL203",
    "pref_name": "Epidermal growth factor receptor erbB1",
    "target_type": "SINGLE PROTEIN",
    "organism": "Homo sapiens",
    "target_components": [{"accession": "P00533"}],
}


def _chembl_adapter(handler, tmp_path):
    adapter = _make_adapter(ChEMBLAdapter, handler)
    adapter._cache = ResponseCache(cache_dir=tmp_path)
    return adapter


async def test_chembl_search_by_target_uses_target_accession_casing_and_nm(tmp_path):
    seen = {}

    def handler(request):
        if request.url.path.endswith("/target/search.json"):
            return httpx.Response(200, json={"targets": [_TARGET]})
        seen.update(request.url.params)
        activity = {
            "molecule_chembl_id": "CHEMBL1",
            "standard_type": "Ki",
            "standard_value": "5",
            "standard_units": "nM",
        }
        return httpx.Response(200, json={"activities": [activity]})

    adapter = _chembl_adapter(handler, tmp_path)
    try:
        results = await adapter.search_by_target("EGFR", activity_type="ki")
    finally:
        await adapter.close()

    assert seen["standard_type"] == "Ki"
    assert seen["standard_units"] == "nM"
    assert results[0].target_uniprot == "P00533"


async def test_chembl_approved_drugs_keeps_phase_4_once(tmp_path):
    molecules = {
        "CHEMBL939": {
            "molecule_chembl_id": "CHEMBL939",
            "pref_name": "GEFITINIB",
            "max_phase": "4.0",
        },
        "CHEMBL9": {"molecule_chembl_id": "CHEMBL9", "pref_name": "TRIAL DRUG", "max_phase": 2},
    }
    molecule_calls = []

    def handler(request):
        path = request.url.path
        if path.endswith("/target/search.json"):
            return httpx.Response(200, json={"targets": [_TARGET]})
        if path.endswith("/mechanism.json"):
            mechs = [
                {"molecule_chembl_id": "CHEMBL939"},
                {"molecule_chembl_id": "CHEMBL939"},
                {"molecule_chembl_id": "CHEMBL9"},
            ]
            return httpx.Response(200, json={"mechanisms": mechs})
        chembl_id = path.rsplit("/", 1)[-1].removesuffix(".json")
        molecule_calls.append(chembl_id)
        return httpx.Response(200, json=molecules[chembl_id])

    adapter = _chembl_adapter(handler, tmp_path)
    try:
        drugs = await adapter.get_approved_drugs_for_target("EGFR")
    finally:
        await adapter.close()

    assert [d.chembl_id for d in drugs] == ["CHEMBL939"]
    assert molecule_calls.count("CHEMBL939") == 1


# --- PDBAdapter ------------------------------------------------------------


async def test_pdb_search_with_no_hits_returns_empty(tmp_path):
    def handler(request):
        return httpx.Response(204)

    adapter = _make_adapter(PDBAdapter, handler, cache_dir=tmp_path)
    try:
        assert await adapter.search_structures("no such protein") == []
    finally:
        await adapter.close()


async def test_pdb_download_retries_transient_errors(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, content=gzip.compress(b"ATOM\n"))

    adapter = _make_adapter(PDBAdapter, handler, cache_dir=tmp_path)
    try:
        path = await adapter.get_structure_file("1abc")
    finally:
        await adapter.close()

    assert path.read_bytes() == b"ATOM\n"


async def test_pdb_download_falls_back_to_plain_then_not_found(tmp_path):
    urls = []

    def handler(request):
        urls.append(str(request.url))
        return httpx.Response(404)

    adapter = _make_adapter(PDBAdapter, handler, cache_dir=tmp_path)
    try:
        with pytest.raises(StructureNotFoundError):
            await adapter.get_structure_file("9zzz")
    finally:
        await adapter.close()

    assert [u.rsplit("/", 1)[-1] for u in urls] == ["9ZZZ.pdb.gz", "9ZZZ.pdb"]


async def test_pdb_download_timeout_is_typed(tmp_path):
    def handler(request):
        raise httpx.ConnectTimeout("down", request=request)

    adapter = _make_adapter(PDBAdapter, handler, cache_dir=tmp_path)
    try:
        with pytest.raises(AdapterTimeout):
            await adapter.get_structure_file("1abc")
    finally:
        await adapter.close()


# --- PubMedAdapter ---------------------------------------------------------

_CITES_ONLY = """
<PubmedArticle><MedlineCitation><PMID>2</PMID><Article>
<ArticleTitle>No DOI of its own</ArticleTitle>
</Article></MedlineCitation>
<PubmedData>
<ArticleIdList><ArticleId IdType="pubmed">2</ArticleId></ArticleIdList>
<ReferenceList><Reference><ArticleIdList>
<ArticleId IdType="doi">10.1000/cited-paper</ArticleId>
</ArticleIdList></Reference></ReferenceList>
</PubmedData>
</PubmedArticle>
"""


def test_pubmed_doi_ignores_cited_papers():
    citation = PubMedAdapter._parse_article(PubMedAdapter(), ET.fromstring(_CITES_ONLY))
    assert citation is not None
    assert citation.doi is None


async def test_pubmed_malformed_efetch_returns_empty_result():
    def handler(request):
        if request.url.path.endswith("esearch.fcgi"):
            return httpx.Response(200, json={"esearchresult": {"idlist": ["1"], "count": "1"}})
        return httpx.Response(200, content=b"<PubmedArticleSet><broken>")

    adapter = _make_adapter(PubMedAdapter, handler)
    adapter._REQUEST_INTERVAL = 0
    try:
        result = await adapter.search("lysozyme")
    finally:
        await adapter.close()

    assert result.citations == []


# --- UniProtAdapter --------------------------------------------------------


def test_uniprot_unreviewed_entry_uses_submission_name():
    entry = {"proteinDescription": {"submissionNames": [{"fullName": {"value": "Kinase X"}}]}}
    assert UniProtAdapter._extract_protein_name(entry) == "Kinase X"


async def test_uniprot_organism_filter_is_quoted():
    seen = {}

    def handler(request):
        seen["query"] = request.url.params["query"]
        return httpx.Response(200, json={"results": []})

    adapter = _make_adapter(UniProtAdapter, handler)
    try:
        await adapter.search_sequences("lysozyme", organism="Homo sapiens")
    finally:
        await adapter.close()

    assert seen["query"] == 'lysozyme AND organism_name:"Homo sapiens"'
