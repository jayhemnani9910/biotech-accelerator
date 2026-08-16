"""Parsing of the RCSB GraphQL metadata response.

`chain_ids` is a documented field of the fetch_structure MCP tool; it was
hardcoded to [] regardless of what the API returned.
"""

from biotech_accelerator.adapters.pdb_adapter import PDBAdapter

# Shape of the RCSB data API response, trimmed to what the adapter reads.
_RESPONSE = {
    "data": {
        "entry": {
            "rcsb_entry_info": {
                "resolution_combined": [1.65],
                "experimental_method": "X-ray",
            },
            "polymer_entities": [
                {
                    "rcsb_polymer_entity_container_identifiers": {"auth_asym_ids": ["A", "B"]},
                    "entity_poly": {"pdbx_seq_one_letter_code_can": "MTEYKLVVVG"},
                },
                {
                    "rcsb_polymer_entity_container_identifiers": {"auth_asym_ids": ["C"]},
                    "entity_poly": {"pdbx_seq_one_letter_code_can": "GAGGVGK"},
                },
            ],
            "struct": {"title": "KRAS G12C"},
        }
    }
}


def test_chain_ids_come_from_the_response():
    meta = PDBAdapter._parse_metadata(_RESPONSE)

    assert meta["chain_ids"] == ["A", "B", "C"]


def test_chain_ids_are_deduplicated_and_ordered():
    response = {
        "data": {
            "entry": {
                "rcsb_entry_info": {},
                "polymer_entities": [
                    {"rcsb_polymer_entity_container_identifiers": {"auth_asym_ids": ["A", "B"]}},
                    {"rcsb_polymer_entity_container_identifiers": {"auth_asym_ids": ["B", "A"]}},
                ],
            }
        }
    }

    assert PDBAdapter._parse_metadata(response)["chain_ids"] == ["A", "B"]


def test_residue_count_still_sums_the_sequences():
    assert PDBAdapter._parse_metadata(_RESPONSE)["num_residues"] == 17


def test_resolution_and_method_are_read():
    meta = PDBAdapter._parse_metadata(_RESPONSE)

    assert meta["resolution"] == 1.65
    assert meta["method"] == "X-ray"


def test_missing_entry_yields_empty_metadata():
    assert PDBAdapter._parse_metadata({"data": {"entry": None}}) == {}


def test_entity_without_chain_identifiers_is_tolerated():
    response = {
        "data": {
            "entry": {
                "rcsb_entry_info": {},
                "polymer_entities": [{"entity_poly": {"pdbx_seq_one_letter_code_can": "AAA"}}],
            }
        }
    }

    meta = PDBAdapter._parse_metadata(response)

    assert meta["chain_ids"] == []
    assert meta["num_residues"] == 3
