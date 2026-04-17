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


# --- SynthesisAgent._extract_hinge_residues / _extract_flexible_regions ----


def test_extract_hinge_residues_basic():
    agent = SynthesisAgent()
    assert agent._extract_hinge_residues("Hinge residues: 45, 46, 47") == [45, 46, 47]


def test_extract_hinge_residues_missing():
    agent = SynthesisAgent()
    assert agent._extract_hinge_residues("no hinge info") == []


def test_extract_flexible_regions_basic():
    agent = SynthesisAgent()
    regions = agent._extract_flexible_regions("Flexible regions: 44-49, 66-72")
    assert (44, 49) in regions and (66, 72) in regions


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
