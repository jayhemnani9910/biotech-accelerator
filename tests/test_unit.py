"""Unit tests for pure-function logic — no network, no file I/O."""

from biotech_accelerator.agents.nodes.drug_binding import DrugBindingAgent
from biotech_accelerator.agents.nodes.structure_analyst import StructureAnalystAgent
from biotech_accelerator.agents.nodes.synthesis import SynthesisAgent
from biotech_accelerator.graph.biotech_graph import parse_query_node

# --- StructureAnalystAgent.extract_pdb_ids ---------------------------------


def _agent(tmp_path):
    from biotech_accelerator.adapters.pdb_adapter import PDBAdapter

    return StructureAnalystAgent(pdb_adapter=PDBAdapter(cache_dir=tmp_path))


def test_extract_pdb_ids_single(tmp_path):
    assert _agent(tmp_path).extract_pdb_ids("analyze PDB 1LYZ") == ["1LYZ"]


def test_extract_pdb_ids_multiple_and_deduped(tmp_path):
    ids = _agent(tmp_path).extract_pdb_ids("compare 1lyz and 4HHB, then 1LYZ again")
    assert ids == ["1LYZ", "4HHB"]


def test_extract_pdb_ids_none(tmp_path):
    assert _agent(tmp_path).extract_pdb_ids("no pdb id here") == []


def test_extract_pdb_ids_requires_leading_digit(tmp_path):
    # "ABCD" should not match; "1ABC" should
    assert _agent(tmp_path).extract_pdb_ids("ABCD 1ABC") == ["1ABC"]


# --- DrugBindingAgent._classify_potency ------------------------------------


def test_classify_potency_highly_potent_nm():
    agent = DrugBindingAgent()
    assert agent._classify_potency(5.0, "nM") == "highly potent (<10 nM)"


def test_classify_potency_potent_nm():
    agent = DrugBindingAgent()
    assert agent._classify_potency(50.0, "nM") == "potent (10-100 nM)"


def test_classify_potency_moderate_nm():
    agent = DrugBindingAgent()
    assert agent._classify_potency(500.0, "nM") == "moderate (100-1000 nM)"


def test_classify_potency_weak_nm():
    agent = DrugBindingAgent()
    assert agent._classify_potency(5000.0, "nM") == "weak (>1 µM)"


def test_classify_potency_um_normalizes_to_nm():
    agent = DrugBindingAgent()
    # 0.05 µM = 50 nM -> "potent"
    assert agent._classify_potency(0.05, "uM") == "potent (10-100 nM)"


def test_classify_potency_pm_normalizes_to_nm():
    agent = DrugBindingAgent()
    # 5000 pM = 5 nM -> "highly potent"
    assert agent._classify_potency(5000.0, "pM") == "highly potent (<10 nM)"


def test_classify_potency_accepts_greek_mu_as_micromolar():
    """ChEMBL emits both U+00B5 MICRO SIGN and U+03BC GREEK SMALL LETTER MU."""
    agent = DrugBindingAgent()
    assert agent._classify_potency(5.0, "µM") == "weak (>1 µM)"
    assert agent._classify_potency(5.0, "μM") == "weak (>1 µM)"


def test_classify_potency_unknown_unit_is_not_graded():
    """An unconvertible unit must not be silently graded on the nM scale."""
    agent = DrugBindingAgent()
    assert agent._classify_potency(5.0, "ug.mL-1") == "unknown potency (unit 'ug.mL-1')"
    assert agent._classify_potency(5.0, "") == "unknown potency (unit '')"


def test_classify_potency_micromolar_spelled_out():
    agent = DrugBindingAgent()
    assert agent._classify_potency(0.05, "micromolar") == "potent (10-100 nM)"


# --- DrugBindingAgent._analyze_activities ranking ---------------------------


def _activity(value, unit, name):
    from biotech_accelerator.domain.compound_models import CompoundInfo
    from biotech_accelerator.ports.compound import BioactivityData

    return BioactivityData(
        compound=CompoundInfo(name=name),
        target_name="EGFR",
        activity_type="IC50",
        activity_value=value,
        activity_unit=unit,
    )


def test_analyze_activities_ranks_across_mixed_units():
    """5 nM is 1000x more potent than 5 µM and must sort above it."""
    agent = DrugBindingAgent()
    activities = [_activity(5.0, "uM", "weak-one"), _activity(5.0, "nM", "strong-one")]

    insights = agent._analyze_activities(activities, "EGFR")

    assert [i.compound.name for i in insights] == ["strong-one", "weak-one"]


def test_analyze_activities_drops_unconvertible_units_from_ranking():
    """Rows we cannot put on a common scale must not be ranked as if we could."""
    agent = DrugBindingAgent()
    activities = [
        _activity(5.0, "ug.mL-1", "unrankable"),
        _activity(50.0, "nM", "rankable"),
    ]

    insights = agent._analyze_activities(activities, "EGFR")

    assert [i.compound.name for i in insights] == ["rankable"]


# --- DrugBindingAgent._extract_targets -------------------------------------


def test_extract_targets_from_known_map():
    agent = DrugBindingAgent()
    targets = agent._extract_targets("find EGFR inhibitors", [])
    assert "EGFR" in targets


def test_extract_targets_from_protein_names():
    agent = DrugBindingAgent()
    targets = agent._extract_targets("drug search", ["KRAS"])
    assert "KRAS" in targets


def test_extract_targets_inhibitor_pattern():
    agent = DrugBindingAgent()
    targets = agent._extract_targets("find jak2 inhibitor compounds", [])
    assert "JAK2" in targets


def test_extract_targets_empty_query():
    agent = DrugBindingAgent()
    assert agent._extract_targets("no targets here", []) == []


def test_extract_targets_ignores_the_word_target_itself():
    r"""The pattern "target\s+(\w+)" turned "target protein" into a ChEMBL query."""
    agent = DrugBindingAgent()
    assert "PROTEIN" not in agent._extract_targets("what does this target protein do", [])


def test_extract_targets_ignores_common_words_from_inhibitor_patterns():
    agent = DrugBindingAgent()
    assert "THE" not in agent._extract_targets("which compounds inhibit the receptor", [])


def test_extract_targets_ignores_generic_biology_words_in_protein_names():
    agent = DrugBindingAgent()
    assert agent._extract_targets("", ["DNA", "RNA", "CELL", "HUMAN"]) == []


def test_extract_targets_still_finds_a_real_symbol_next_to_noise():
    agent = DrugBindingAgent()
    targets = agent._extract_targets("find a KRAS inhibitor for this target protein", [])
    assert "KRAS" in targets
    assert "PROTEIN" not in targets


# --- SynthesisAgent.MUTATION_PATTERNS + _extract_mutations_from_literature -


class _FakeCitation:
    def __init__(self, title="", abstract="", pmid="test"):
        self.title = title
        self.abstract = abstract
        self.pmid = pmid


def test_extract_mutations_single_letter():
    agent = SynthesisAgent()
    citations = [_FakeCitation(abstract="The V600E mutation in BRAF drives melanoma.")]
    mutations = agent._extract_mutations_from_literature(citations)
    assert any(m.original == "V" and m.position == 600 and m.mutant == "E" for m in mutations)


def test_extract_mutations_three_letter_normalized():
    agent = SynthesisAgent()
    citations = [_FakeCitation(abstract="Ala42Gly substitution reduces activity.")]
    mutations = agent._extract_mutations_from_literature(citations)
    assert any(m.original == "A" and m.position == 42 and m.mutant == "G" for m in mutations)


def test_extract_mutations_deduplicated():
    agent = SynthesisAgent()
    citations = [
        _FakeCitation(abstract="V600E is common. V600E again."),
        _FakeCitation(abstract="Also V600E observed."),
    ]
    mutations = agent._extract_mutations_from_literature(citations)
    v600e = [m for m in mutations if m.position == 600 and m.mutant == "E"]
    assert len(v600e) == 1


def test_extract_mutations_none():
    agent = SynthesisAgent()
    citations = [_FakeCitation(abstract="No mutations mentioned.")]
    assert agent._extract_mutations_from_literature(citations) == []


# Structural data is no longer regex-parsed out of the rendered summary; the
# typed-state contract that replaced it is covered in tests/test_structural_state.py.


# --- parse_query_node (async) ---------------------------------------------


async def test_parse_query_node_pdb_extraction():
    result = await parse_query_node({"query": "Analyze PDB 1LYZ"})
    assert "1LYZ" in result["pdb_ids"]


async def test_parse_query_node_protein_mapping():
    result = await parse_query_node({"query": "What stabilizes lysozyme?"})
    assert "lysozyme" in result["protein_names"]
    assert "P00698" in result["uniprot_ids"]


async def test_parse_query_node_drug_keyword_detection():
    result = await parse_query_node({"query": "Find EGFR inhibitors"})
    assert result["has_drug_query"] is True


async def test_parse_query_node_no_drug_keyword():
    result = await parse_query_node({"query": "Analyze flexibility of 1LYZ"})
    assert result["has_drug_query"] is False


async def test_parse_query_node_empty_query():
    result = await parse_query_node({"query": ""})
    assert result["pdb_ids"] == []
    assert result["protein_names"] == []
    assert result["has_drug_query"] is False


# --- ChEMBLAdapter._select_best_target -------------------------------------


def test_select_best_target_prefers_single_protein_human():
    from biotech_accelerator.adapters.chembl_adapter import ChEMBLAdapter

    # Mirrors ChEMBL's actual score order for "EGFR": PPI complexes and a
    # mouse single-protein rank above canonical human EGFR (CHEMBL203).
    targets = [
        {
            "target_chembl_id": "CHEMBL4523747",
            "target_type": "PROTEIN-PROTEIN INTERACTION",
            "organism": "Homo sapiens",
        },
        {
            "target_chembl_id": "CHEMBL3608",
            "target_type": "SINGLE PROTEIN",
            "organism": "Mus musculus",
        },
        {
            "target_chembl_id": "CHEMBL203",
            "target_type": "SINGLE PROTEIN",
            "organism": "Homo sapiens",
        },
    ]
    best = ChEMBLAdapter._select_best_target(targets)
    assert best["target_chembl_id"] == "CHEMBL203"


def test_select_best_target_falls_back_to_first_when_no_single_protein():
    from biotech_accelerator.adapters.chembl_adapter import ChEMBLAdapter

    targets = [
        {"target_chembl_id": "A", "target_type": "PROTEIN FAMILY", "organism": "Homo sapiens"},
        {"target_chembl_id": "B", "target_type": "PROTEIN COMPLEX", "organism": "Homo sapiens"},
    ]
    # Stable sort preserves ChEMBL's own ranking within the same priority.
    assert ChEMBLAdapter._select_best_target(targets)["target_chembl_id"] == "A"


def test_select_best_target_empty_returns_none():
    from biotech_accelerator.adapters.chembl_adapter import ChEMBLAdapter

    assert ChEMBLAdapter._select_best_target([]) is None
