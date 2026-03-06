# Biotech Research Accelerator

A multi-agent AI system that doesn't just READ about biology - it ANALYZES molecular data, cross-references literature with computational evidence, and suggests experiments.

## What Makes It Different

Current research agents (OpenAI Deep Research, Gemini, etc.) can **read** about biology.

This system can **read + analyze + recommend**:

```
User: "What mutations stabilize lysozyme? Analyze PDB 1LYZ"
         ↓
[PARSER] Extract proteins, PDB IDs, detect query type
         ↓
[UNIPROT] Resolve protein names → UniProt IDs → PDB structures
         ↓
[PUBMED] Search literature for mutations and stability data
         ↓
[STRUCTURE] Fetch PDB, run ANM/GNM analysis for flexibility
         ↓
[CHEMBL] Search for active compounds (if drug query detected)
         ↓
[SYNTHESIS] Cross-reference mutations with flexible regions
         ↓
[EXPERIMENTS] Generate actionable experiment suggestions
         ↓
Final Report with citations, structural insights, and next steps
```

## Features

### 1. Literature Analysis
- PubMed search with proper query construction
- Mutation extraction from abstracts (e.g., V600E, L858R)
- Relevance scoring and deduplication
- Rate limiting and retry logic

### 2. Structural Analysis
- PDB structure fetching from RCSB
- Normal Mode Analysis (ANM/GNM) via ProDy
- Flexibility profiling (flexible/rigid regions)
- Hinge residue identification

### 3. Drug Discovery
- ChEMBL integration for bioactivity data
- Target-based compound search
- Potency classification (<10nM, 10-100nM, etc.)
- Known drug identification

### 4. Intelligent Synthesis
- Cross-reference mutations with structure
- Map mutations to flexible/rigid regions
- Identify hinge-affecting mutations
- Generate experiment suggestions

## Installation

```bash
# Clone the repo
git clone https://github.com/your-username/biotech-accelerator.git
cd biotech-accelerator

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### Dependencies
- Python 3.10+
- ProDy (Normal Mode Analysis)
- httpx (async HTTP client)
- LangGraph (workflow orchestration)
- Rich (terminal formatting)

## Usage

### Python API

```python
import asyncio
from biotech_accelerator.graph.biotech_graph import run_research

async def main():
    # Stability research
    result = await run_research("What mutations stabilize lysozyme?")
    print(result["final_report"])

    # Drug discovery
    result = await run_research("Find inhibitors for EGFR kinase")
    print(result["final_report"])

asyncio.run(main())
```

### CLI

```bash
# Run test pipeline
python test_full_pipeline.py

# Run examples
python examples/run_examples.py
```

## Example Queries

| Query | What It Does |
|-------|--------------|
| "What mutations stabilize lysozyme?" | Literature + structure analysis |
| "Analyze PDB 1LYZ" | NMA flexibility analysis |
| "Find EGFR inhibitors" | ChEMBL drug search |
| "BRAF V600E mutation analysis" | Combined research |

## Architecture

```
biotech-accelerator/
├── biotech_accelerator/
│   ├── adapters/           # API integrations
│   │   ├── pdb_adapter.py      # RCSB PDB
│   │   ├── pubmed_adapter.py   # NCBI PubMed
│   │   ├── uniprot_adapter.py  # UniProt
│   │   └── chembl_adapter.py   # ChEMBL
│   │
│   ├── agents/nodes/       # LangGraph agents
│   │   ├── structure_analyst.py
│   │   ├── bio_literature.py
│   │   ├── drug_binding.py
│   │   ├── synthesis.py
│   │   └── experiment_suggester.py
│   │
│   ├── analysis/           # Computational wrappers
│   │   └── nma_wrapper.py      # ProDy ANM/GNM
│   │
│   ├── domain/             # Data models
│   │   ├── protein_models.py
│   │   └── compound_models.py
│   │
│   ├── graph/              # LangGraph workflow
│   │   └── biotech_graph.py
│   │
│   ├── ports/              # Abstract interfaces
│   │   ├── structure.py
│   │   ├── sequence.py
│   │   ├── literature.py
│   │   └── compound.py
│   │
│   └── utils/              # Utilities
│       └── cache.py            # Response caching
│
├── examples/               # Example scripts
├── test_full_pipeline.py   # Integration test
└── README.md
```

## Pipeline Flow

```
parse_query_node
       ↓
resolve_proteins_node (UniProt → PDB mapping)
       ↓
literature_node (PubMed search)
       ↓
structure_node (PDB + NMA analysis)
       ↓
drug_node (ChEMBL search, if drug query)
       ↓
synthesis_node (combine all evidence + experiments)
       ↓
     END
```

## Data Sources

| Source | Data Type | Status |
|--------|-----------|--------|
| PubMed | Research papers | ✅ Working |
| RCSB PDB | Protein structures | ✅ Working |
| UniProt | Sequences, annotations | ✅ Working |
| ChEMBL | Compound bioactivity | ✅ Working |
| ProDy | ANM/GNM analysis | ✅ Working |

## Performance Features

- **Caching**: API responses cached for 24h
- **Rate limiting**: PubMed requests throttled to avoid 429 errors
- **Retry logic**: Automatic retry with exponential backoff
- **Parallel search**: Multiple protein-specific searches

## Example Output

```
# Biotech Research Report

**Query:** What mutations stabilize lysozyme? Analyze PDB 1LYZ

## Literature Evidence
- 5 papers found
- 1 mutation identified: D67H

## Computational Analysis
**Analyzed structures:** 1LYZ

**Flexibility Profile:**
- Mean fluctuation: 0.145 Å²
- Flexible regions: 44-49, 66-72, 100-102
- Hinge residues: 45, 46, 47, 48, 49

## Synthesis & Insights
- D67H is in a flexible region
- May alter local dynamics

## Suggested Experiments

### 1. Engineer stabilizing mutations in rigid core
**Methods:**
- Design conservative mutations in rigid core
- Use Rosetta for ΔΔG predictions
- Measure stability via DSF thermal melt

### 2. Probe hinge dynamics at positions 45, 46, 47
**Methods:**
- Design Gly→Pro mutations to rigidify
- Use NMR relaxation to probe dynamics
```

## Contributing

This project combines several repositories:
- `revolu-idea`: Multi-agent orchestration
- `nobel-dataintelligence`: Molecular analysis

## License

MIT
