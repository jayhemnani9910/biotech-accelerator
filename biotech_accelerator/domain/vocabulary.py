"""Tokens that look like gene symbols but are not.

Both the query parser and the drug-target extractor pull short uppercase tokens
out of free text, and both need the same stop list. It lives here, in the lowest
layer, so neither has to import the other.
"""

# Uppercase tokens a naive [A-Z]{2,6} match will pick up from ordinary prose.
EXCLUDED_TOKENS = frozenset(
    {
        # Techniques and molecule classes
        "PDB",
        "DNA",
        "RNA",
        "NMR",
        # Function words
        "AND",
        "THE",
        "FOR",
        "NOT",
        "WITH",
        "FROM",
        "THAT",
        "THIS",
        "HAVE",
        "BEEN",
        "WERE",
        "WHAT",
        "HOW",
        "WHY",
        "CAN",
        "ARE",
        "WAS",
        "HAS",
        "HAD",
        "WILL",
        # Research vocabulary
        "STUDY",
        "RESULTS",
        "METHODS",
        "DATA",
        "ANALYSIS",
        "RESEARCH",
        # Generic biology nouns
        "PROTEIN",
        "GENE",
        "CELL",
        "HUMAN",
        "MOUSE",
        "RAT",
        "TARGET",
        "RECEPTOR",
    }
)
