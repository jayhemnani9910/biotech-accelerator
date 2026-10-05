"""Regression tests for the agent nodes, graph parsing, CLI JSON and NMA fixes."""

import json
from types import SimpleNamespace

import numpy as np
import pytest

from biotech_accelerator import main as cli
from biotech_accelerator.adapters.base import AdapterHTTPError
from biotech_accelerator.agents.nodes.bio_literature import BioLiteratureAgent
from biotech_accelerator.agents.nodes.drug_binding import DrugBindingAgent
from biotech_accelerator.agents.nodes.experiment_suggester import ExperimentSuggester
from biotech_accelerator.agents.nodes.structure_analyst import (
    PDB_ID_PATTERN,
    StructureAnalysisResult,
    StructureAnalystAgent,
)
from biotech_accelerator.agents.nodes.synthesis import (
    MutationInfo,
    MutationInsight,
    ReportData,
    SynthesisAgent,
)
from biotech_accelerator.analysis.nma_wrapper import NMAAnalyzer
from biotech_accelerator.domain.compound_models import CompoundInfo
from biotech_accelerator.domain.protein_models import FlexibilityMetrics, NMAResult
from biotech_accelerator.graph.biotech_graph import parse_query_node, resolve_proteins_node
from biotech_accelerator.ports.compound import BioactivityData
from biotech_accelerator.ports.literature import Citation, LiteratureSearchResult

# --- BioLiteratureAgent -----------------------------------------------------


class _FakePubMed:
    def __init__(self, citations):
        self.citations = citations

    async def search(self, query, max_results=10):
        return LiteratureSearchResult(
            query=query, citations=self.citations, total_count=len(self.citations)
        )

    async def search_by_protein(self, name, topic=None, max_results=5):
        return LiteratureSearchResult(query=name, citations=[], total_count=0)

    async def close(self):
        pass


def _lit_agent(citations=()):
    return BioLiteratureAgent(pubmed_adapter=_FakePubMed(list(citations)))  # type: ignore[arg-type]


def test_mixed_case_abbreviations_are_detected():
    agent = _lit_agent()
    ev = agent._analyze_citation(Citation(title="x", abstract="IC50 was 5 nM; Tm rose 4 C."), "")
    assert ev.mentions_binding
    assert ev.mentions_stability


def test_short_keywords_do_not_match_inside_words():
    agent = _lit_agent()
    ev = agent._analyze_citation(Citation(title="kinase treatment outcomes"), "")
    assert not ev.mentions_binding
    assert not ev.mentions_stability


def test_literature_agent_has_no_unused_uniprot_adapter():
    assert not hasattr(_lit_agent(), "uniprot")


async def test_literature_count_matches_papers_found():
    citations = [Citation(pmid=str(i), title=f"paper {i}") for i in range(20)]
    result = await _lit_agent(citations)({"query": "q"})

    assert result["literature_count"] == 20
    assert "**Papers found:** 20 (top 15 analysed)" in result["literature_summary"]


# --- DrugBindingAgent -------------------------------------------------------


def _act(value, name, chembl_id=None, activity_type="IC50", unit="nM"):
    return BioactivityData(
        compound=CompoundInfo(name=name, chembl_id=chembl_id or name),
        target_name="t",
        activity_type=activity_type,
        activity_value=value,
        activity_unit=unit,
    )


class _FakeChEMBL:
    def __init__(self, by_target):
        self.by_target = by_target

    async def search_by_target(self, target, activity_type=None, max_results=15):
        rows = self.by_target[target]
        if isinstance(rows, Exception):
            raise rows
        return [r for r in rows if r.activity_type == activity_type]

    async def get_approved_drugs_for_target(self, target, max_results=10):
        return []

    async def close(self):
        pass


def test_target_map_ignores_substrings_of_ordinary_words():
    agent = DrugBindingAgent(chembl_adapter=_FakeChEMBL({}))  # type: ignore[arg-type]
    targets = agent._extract_targets("what drugs are available for this method on a walk", [])
    assert not {"ABL1", "MET", "ALK"} & set(targets)
    assert "ABL1" in agent._extract_targets("drugs for bcr-abl", [])


async def test_top_compounds_are_ranked_across_targets():
    chembl = _FakeChEMBL(
        {
            "EGFR": [_act(v, f"egfr-{v}") for v in (50, 60, 70, 80, 90)],
            "BRAF": [_act(v, f"braf-{v}") for v in (1, 2, 3, 4, 5)],
        }
    )
    agent = DrugBindingAgent(chembl_adapter=chembl)  # type: ignore[arg-type]
    result = await agent({"query": "egfr and braf drugs"})

    assert [c.name for c in result["target_compounds"][:2]] == ["braf-1", "braf-2"]


async def test_one_failing_target_keeps_the_others():
    chembl = _FakeChEMBL(
        {
            "EGFR": [_act(v, f"egfr-{v}") for v in (1, 2, 3, 4, 5)],
            "BRAF": AdapterHTTPError("ChEMBL", 503),
        }
    )
    agent = DrugBindingAgent(chembl_adapter=chembl)  # type: ignore[arg-type]
    result = await agent({"query": "egfr and braf drugs"})

    assert len(result["drug_insights"]) == 5
    assert "ChEMBL lookup failed for BRAF" in result["drug_summary"]


def test_approval_comes_from_chembl_not_name_suffix():
    agent = DrugBindingAgent(chembl_adapter=_FakeChEMBL({}))  # type: ignore[arg-type]
    rows = [_act(5, "investigatinib", "CHEMBL1"), _act(50, "realdrug", "CHEMBL2")]

    insights = agent._analyze_activities(rows, "EGFR", {"CHEMBL2"})

    approved = {i.compound.chembl_id: i.is_approved_drug for i in insights}
    assert approved == {"CHEMBL1": False, "CHEMBL2": True}


def test_ic50_and_ki_rows_for_one_compound_count_once():
    agent = DrugBindingAgent(chembl_adapter=_FakeChEMBL({}))  # type: ignore[arg-type]
    rows = [_act(50, "dup", "CHEMBL1"), _act(5, "dup", "CHEMBL1", activity_type="Ki")]

    insights = agent._analyze_activities(rows, "EGFR")

    assert len(insights) == 1
    assert insights[0].activity_type == "Ki"


# --- SynthesisAgent ---------------------------------------------------------


async def test_no_structure_gives_no_stable_region_verdicts():
    citation = Citation(pmid="1", title="t", abstract="The A42G mutation was studied.")
    result = await SynthesisAgent()(
        {"query": "q", "literature_count": 1, "literature_citations": [citation]}
    )
    report = result["final_report"]

    assert "stable region" not in report
    assert "No structural data" in report


def test_hinge_mutation_is_not_also_a_stabilizing_candidate():
    mut = MutationInfo(original="A", position=10, mutant="G", source="", context="")
    hinge = MutationInsight(
        mutation=mut,
        in_flexible_region=False,
        is_hinge_residue=True,
        flexibility_score=None,
        recommendation="",
    )
    recs = SynthesisAgent._fallback_recommendations(
        ReportData(mutations=[mut], insights=[hinge], pdb_ids=["1ABC"])
    )

    assert not any("Stabilizing" in r for r in recs)
    assert any("Dynamics-altering" in r for r in recs)


def test_single_letter_mutation_needs_amino_acid_letters_and_a_change():
    agent = SynthesisAgent()
    text = "Strains B42X and J5O, silent A42A, real V600E."
    mutations = agent._extract_mutations_from_literature([Citation(abstract=text)])

    assert [(m.original, m.position, m.mutant) for m in mutations] == [("V", 600, "E")]


# --- ExperimentSuggester ----------------------------------------------------


def _analysis(hinges=(), rigid=((3, 24),)):
    nma = NMAResult(
        pdb_id="1ABC",
        n_modes=10,
        eigenvalues=np.ones(10),
        eigenvectors=np.ones((30, 10)),
        fluctuations=np.ones(10),
        collectivity=np.ones(10),
        vibrational_entropy=-1.0,
        flexibility=FlexibilityMetrics(
            mean_fluctuation=0.1,
            max_fluctuation=2.0,
            flexible_regions=[],
            rigid_regions=[tuple(r) for r in rigid],
            hinge_residues=list(hinges),
        ),
        residue_numbers=list(range(1, 101)),
        chain_ids=["A"] * 100,
    )
    return StructureAnalysisResult(pdb_id="1ABC", nma_result=nma)


def test_rigid_core_suggestion_needs_only_rigid_regions():
    suggestions = ExperimentSuggester().suggest({"structure_analysis": [_analysis()]})
    assert any("rigid core" in s.title for s in suggestions)


# --- graph parsing ----------------------------------------------------------


async def test_actin_is_not_found_inside_interacting():
    result = await parse_query_node({"query": "interacting partners of lysozyme"})
    assert "actin" not in result["protein_names"]
    assert "lysozyme" in result["protein_names"]


async def test_drug_keywords_match_whole_words_only():
    result = await parse_query_node({"query": "mitochondrial skin kinase making"})
    assert result["has_drug_query"] is False


def test_years_are_not_pdb_ids():
    assert PDB_ID_PATTERN.findall("published 2020, see 1LYZ and 4hhb") == ["1LYZ", "4hhb"]
    assert StructureAnalystAgent.PDB_ID_PATTERN is PDB_ID_PATTERN


async def test_protein_names_resolved_even_with_pdb_ids(monkeypatch):
    class _FakeUniProt:
        async def search_sequences(self, name, max_results=1):
            return [SimpleNamespace(uniprot_id="P00698")]

        async def get_pdb_mapping(self, uniprot_id):
            return ["2LYZ"]

        async def close(self):
            pass

    import biotech_accelerator.adapters.uniprot_adapter as uniprot_module

    monkeypatch.setattr(uniprot_module, "UniProtAdapter", _FakeUniProt)
    result = await resolve_proteins_node(
        {"pdb_ids": ["1LYZ"], "protein_names": ["lysozyme"], "uniprot_ids": []}
    )

    assert result["pdb_ids"] == ["1LYZ", "2LYZ"]
    assert result["uniprot_ids"] == ["P00698"]


# --- CLI --json -------------------------------------------------------------


async def test_json_with_several_pdb_ids_prints_one_array(monkeypatch, capsys):
    async def fake_analyze(pdb_id):
        return StructureAnalysisResult(pdb_id=pdb_id, summary="s")

    monkeypatch.setattr(cli, "analyze_protein_structure", fake_analyze)

    assert await cli._structure_analyses(["1ABC", "2DEF"], emit_json=True) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert [r["pdb_id"] for r in parsed] == ["1ABC", "2DEF"]

    assert await cli._structure_analyses(["1ABC"], emit_json=True) == 0
    assert json.loads(capsys.readouterr().out)["pdb_id"] == "1ABC"


# --- NMAAnalyzer ------------------------------------------------------------


def _write_pdb(path, coords):
    lines = [
        f"ATOM  {i + 1:5d}  CA  ALA A{i + 1:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C"
        for i, (x, y, z) in enumerate(coords)
    ]
    path.write_text("\n".join(lines) + "\nEND\n")
    return path


def test_unparseable_structure_raises_value_error(monkeypatch, tmp_path):
    import prody

    monkeypatch.setattr(prody, "parsePDB", lambda *_a, **_k: None)
    with pytest.raises(ValueError, match="Could not parse"):
        NMAAnalyzer(n_modes=5).analyze(tmp_path / "empty.pdb")


def test_too_few_calpha_atoms_raises_value_error(tmp_path):
    pdb = _write_pdb(tmp_path / "tiny.pdb", [(0, 0, 0), (3.8, 0, 0)])
    with pytest.raises(ValueError, match="at least 3"):
        NMAAnalyzer(n_modes=5).analyze(pdb)


def test_vibrational_entropy_is_minus_half_kb_sum_log(tmp_path):
    rng = np.random.default_rng(0)
    pdb = _write_pdb(tmp_path / "blob.pdb", rng.random((20, 3)) * 10)

    result = NMAAnalyzer(n_modes=10).analyze(pdb)

    positive = result.eigenvalues[result.eigenvalues > 0]
    assert result.vibrational_entropy == pytest.approx(-0.5 * 0.001987 * np.sum(np.log(positive)))


def test_chain_break_is_not_a_hinge():
    # Chain A is flat at 1.0 apart from one real bump at residue 11; chain B is
    # flat at 5.0. The step between A20 and B101 is a chain break, not a hinge.
    chain_a = np.full(20, 1.0)
    chain_a[10] = 3.0
    fluct = np.concatenate([chain_a, np.full(20, 5.0)])
    resnums = np.concatenate([np.arange(1, 21), np.arange(101, 121)])
    chains = np.array(["A"] * 20 + ["B"] * 20)

    metrics = NMAAnalyzer(n_modes=10)._analyze_flexibility(fluct, resnums, chains)

    assert metrics.hinge_residues == [10, 12]
