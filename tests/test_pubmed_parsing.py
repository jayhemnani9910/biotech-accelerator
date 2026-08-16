"""Parsing of PubMed efetch XML into Citations.

Two things bite here. Biomedical abstracts are usually *structured* — several
labelled AbstractText elements — and taking only the first one drops RESULTS,
which is exactly where mutations get reported. And titles and abstracts contain
inline markup (<i>, <sup>, <sub>), so .text stops at the first child element.
"""

import xml.etree.ElementTree as ET

from biotech_accelerator.adapters.pubmed_adapter import PubMedAdapter

STRUCTURED = """
<PubmedArticle><MedlineCitation><PMID>40123456</PMID><Article>
<ArticleTitle>Effects of <i>KRAS</i> G12C inhibition</ArticleTitle>
<Abstract>
<AbstractText Label="BACKGROUND">KRAS is frequently mutated.</AbstractText>
<AbstractText Label="METHODS">We tested 40 compounds.</AbstractText>
<AbstractText Label="RESULTS">The Y96D substitution conferred resistance.</AbstractText>
<AbstractText Label="CONCLUSIONS">Combination therapy is warranted.</AbstractText>
</Abstract>
<AuthorList>
  <Author><LastName>Smith</LastName><ForeName>Jane</ForeName></Author>
  <Author><LastName>Okafor</LastName><ForeName>Ada</ForeName></Author>
</AuthorList>
<Journal><Title>Nature</Title></Journal>
<PubDate><Year>2024</Year></PubDate>
</Article></MedlineCitation>
<PubmedData><ArticleIdList><ArticleId IdType="doi">10.1038/s41586-024-1</ArticleId></ArticleIdList></PubmedData>
</PubmedArticle>
"""

SIMPLE = """
<PubmedArticle><MedlineCitation><PMID>1</PMID><Article>
<ArticleTitle>A plain title</ArticleTitle>
<Abstract><AbstractText>One paragraph only.</AbstractText></Abstract>
<Journal><Title>Cell</Title></Journal>
</Article></MedlineCitation></PubmedArticle>
"""


def _parse(xml: str):
    return PubMedAdapter._parse_article(PubMedAdapter(), ET.fromstring(xml))


# --- structured abstracts --------------------------------------------------


def test_all_sections_of_a_structured_abstract_are_kept():
    abstract = _parse(STRUCTURED).abstract

    for fragment in ("frequently mutated", "40 compounds", "Y96D", "Combination therapy"):
        assert fragment in abstract, f"lost: {fragment}"


def test_structured_abstract_keeps_its_section_labels():
    abstract = _parse(STRUCTURED).abstract

    assert "BACKGROUND:" in abstract
    assert "RESULTS:" in abstract


def test_mutations_in_the_results_section_survive_to_extraction():
    """The whole point: mutation extraction reads Citation.abstract."""
    from biotech_accelerator.agents.nodes.synthesis import SynthesisAgent

    citation = _parse(STRUCTURED)
    muts = SynthesisAgent()._extract_mutations_from_literature([citation])

    assert any(m.original == "Y" and m.position == 96 and m.mutant == "D" for m in muts)


def test_unstructured_abstract_is_unchanged():
    assert _parse(SIMPLE).abstract == "One paragraph only."


def test_missing_abstract_is_none():
    xml = (
        "<PubmedArticle><MedlineCitation><PMID>1</PMID><Article>"
        "<ArticleTitle>T</ArticleTitle></Article></MedlineCitation></PubmedArticle>"
    )
    assert _parse(xml).abstract is None


# --- inline markup ---------------------------------------------------------


def test_title_keeps_text_after_inline_markup():
    """.text alone returned 'Effects of ' and dropped the rest."""
    assert _parse(STRUCTURED).title == "Effects of KRAS G12C inhibition"


def test_abstract_text_keeps_text_after_inline_markup():
    xml = """
    <PubmedArticle><MedlineCitation><PMID>1</PMID><Article>
    <ArticleTitle>T</ArticleTitle>
    <Abstract><AbstractText>The K<sub>d</sub> was 4 nM.</AbstractText></Abstract>
    </Article></MedlineCitation></PubmedArticle>
    """
    assert _parse(xml).abstract == "The Kd was 4 nM."


# --- the rest of the record ------------------------------------------------


def test_metadata_is_parsed():
    c = _parse(STRUCTURED)

    assert c.pmid == "40123456"
    assert c.authors == ["Jane Smith", "Ada Okafor"]
    assert c.journal == "Nature"
    assert c.year == 2024
    assert c.doi == "10.1038/s41586-024-1"
    assert c.url == "https://pubmed.ncbi.nlm.nih.gov/40123456/"


def test_a_record_without_an_article_element_is_skipped():
    xml = "<PubmedArticle><MedlineCitation><PMID>1</PMID></MedlineCitation></PubmedArticle>"
    assert _parse(xml) is None


def test_a_non_numeric_year_does_not_raise():
    xml = """
    <PubmedArticle><MedlineCitation><PMID>1</PMID><Article>
    <ArticleTitle>T</ArticleTitle><PubDate><Year>Spring</Year></PubDate>
    </Article></MedlineCitation></PubmedArticle>
    """
    assert _parse(xml).year is None


# --- hardening of the network-facing XML parse -----------------------------


def test_entity_expansion_in_a_response_is_rejected_not_expanded():
    """efetch responses are parsed straight off the network.

    stdlib ElementTree happily expands internal entities, so a hostile or
    compromised response can blow up memory before anything validates it.
    """
    import pytest

    billion_laughs = """<?xml version="1.0"?>
    <!DOCTYPE lolz [
      <!ENTITY lol "lol">
      <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
      <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
    ]>
    <PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID>
    <Article><ArticleTitle>&lol3;</ArticleTitle></Article>
    </MedlineCitation></PubmedArticle></PubmedArticleSet>"""

    with pytest.raises(Exception) as excinfo:
        PubMedAdapter._parse_xml(billion_laughs)

    assert "Entit" in type(excinfo.value).__name__ or "Forbidden" in type(excinfo.value).__name__
