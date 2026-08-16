"""Environment variables documented in the README must actually reach the code.

PUBMED_EMAIL, PUBMED_API_KEY and PDB_CACHE_DIR are promised in three places —
README, .env.example and .mcp.json — so each one needs a test that fails if the
wiring is ever removed again.
"""

from pathlib import Path

from biotech_accelerator.adapters.pdb_adapter import PDBAdapter
from biotech_accelerator.adapters.pubmed_adapter import PubMedAdapter

# --- PUBMED_EMAIL ----------------------------------------------------------


def test_pubmed_email_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("PUBMED_EMAIL", "real-user@lab.edu")

    assert PubMedAdapter().email == "real-user@lab.edu"


def test_explicit_pubmed_email_beats_the_environment(monkeypatch):
    monkeypatch.setenv("PUBMED_EMAIL", "env@lab.edu")

    assert PubMedAdapter(email="explicit@lab.edu").email == "explicit@lab.edu"


def test_pubmed_email_falls_back_to_a_default(monkeypatch):
    monkeypatch.delenv("PUBMED_EMAIL", raising=False)

    assert PubMedAdapter().email == "biotech-accelerator@example.com"


# --- PUBMED_API_KEY --------------------------------------------------------


def test_pubmed_api_key_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("PUBMED_API_KEY", "abc123")

    assert PubMedAdapter().api_key == "abc123"


def test_pubmed_api_key_reaches_the_request_parameters(monkeypatch):
    """The key is only useful if it is actually sent to NCBI."""
    monkeypatch.setenv("PUBMED_API_KEY", "abc123")

    params = PubMedAdapter()._build_params(db="pubmed")

    assert params["api_key"] == "abc123"


def test_pubmed_api_key_absent_when_unset(monkeypatch):
    monkeypatch.delenv("PUBMED_API_KEY", raising=False)

    assert "api_key" not in PubMedAdapter()._build_params(db="pubmed")


# --- PDB_CACHE_DIR ---------------------------------------------------------


def test_pdb_cache_dir_comes_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("PDB_CACHE_DIR", str(tmp_path / "structures"))

    assert PDBAdapter().get_cache_dir() == tmp_path / "structures"


def test_pdb_cache_dir_expands_a_tilde(monkeypatch):
    """The README documents the default with a ~ in it."""
    monkeypatch.setenv("PDB_CACHE_DIR", "~/pdb-cache-test")

    assert PDBAdapter().get_cache_dir() == Path.home() / "pdb-cache-test"


def test_explicit_pdb_cache_dir_beats_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("PDB_CACHE_DIR", str(tmp_path / "from-env"))

    adapter = PDBAdapter(cache_dir=tmp_path / "explicit")

    assert adapter.get_cache_dir() == tmp_path / "explicit"
