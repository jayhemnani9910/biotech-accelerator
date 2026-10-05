/**
 * Demo data for Biotech Research Accelerator.
 *
 * Every scenario below is an illustrative, hand-written example laid out in the
 * report format produced by synthesis.py (_generate_report). None of it is
 * output captured from a run. Stages a scenario does not list are shown as
 * skipped in the pipeline.
 */

const DEMO_SCENARIOS = {
    lysozyme: {
        query: "What mutations stabilize T4 lysozyme? Analyze PDB 2LZM",
        steps: [
            {
                node: "parser",
                delay: 800,
                output: "T4 lysozyme, 2LZM",
                terminalOutput: [
                    { text: "Parsing query...", class: "info" },
                    { text: "Extracted protein: T4 lysozyme", class: "success" },
                    { text: "Extracted PDB ID: 2LZM", class: "success" },
                    { text: "Query type: stability analysis", class: "info" }
                ]
            },
            {
                node: "uniprot",
                delay: 1100,
                output: "P00720",
                terminalOutput: [
                    { text: "Querying UniProt...", class: "info" },
                    { text: "Resolved: P00720 (Endolysin, T4 lysozyme)", class: "success" },
                    { text: "Organism: Enterobacteria phage T4", class: "info" },
                    { text: "Length: 164 amino acids", class: "info" }
                ]
            },
            {
                node: "pubmed",
                delay: 1500,
                output: "3 papers",
                terminalOutput: [
                    { text: "Searching PubMed...", class: "info" },
                    { text: "Query: T4 lysozyme mutation stability", class: "info" },
                    { text: "Papers in this example: 3", class: "success" }
                ]
            },
            {
                node: "structure",
                delay: 1900,
                output: "2LZM, 1.7 A",
                terminalOutput: [
                    { text: "Downloading PDB 2LZM...", class: "info" },
                    { text: "Structure: 1.7 A resolution", class: "success" },
                    { text: "Running normal mode analysis (ANM/GNM)...", class: "info" },
                    { text: "Flexibility profile computed", class: "success" }
                ]
            },
            {
                node: "synthesis",
                delay: 1300,
                output: "4 mutations",
                terminalOutput: [
                    { text: "Cross-referencing mutations with flexible regions...", class: "info" },
                    { text: "Mutations from literature: G77A, A82P, S38D, N144D", class: "success" }
                ]
            },
            {
                node: "experiments",
                delay: 1000,
                output: "2 suggestions",
                terminalOutput: [
                    { text: "Generating experiment suggestions...", class: "info" },
                    { text: "2 experiments suggested", class: "success" }
                ]
            }
        ],
        report: `# Biotech Research Report

**Query:** What mutations stabilize T4 lysozyme? Analyze PDB 2LZM

---

## Literature Evidence

**Papers shown:** 3

### Key Papers:

**1. Matthews BW, Nicholson H, Becktel WJ (1987)**, Proc Natl Acad Sci USA 84:6663
- G77A and A82P stabilise T4 lysozyme by reducing the entropy of unfolding.

**2. Nicholson H, Becktel WJ, Matthews BW (1988)**, Nature 336:651
- S38D and N144D stabilise the protein through interactions with alpha-helix dipoles.

**3. Matsumura M, Signor G, Matthews BW (1989)**, Nature 342:291
- Engineered multiple disulfide bonds increase the stability of T4 lysozyme.

---

## Computational Analysis

**Analyzed structures:** 2LZM

### Structure Analysis: 2LZM

T4 lysozyme, X-ray structure at 1.7 A resolution. A run reports the flexibility
profile from normal mode analysis here: mean and maximum fluctuation, flexible
regions, rigid core regions and hinge residues. Those computed numbers are left
out of this hand-written example.

---

## Mutations Found in Literature

**Total mutations identified:** 4

- **G77A** (Matthews et al. 1987)
- **A82P** (Matthews et al. 1987)
- **S38D** (Nicholson et al. 1988)
- **N144D** (Nicholson et al. 1988)

---

## Synthesis & Insights

This analysis combines **literature evidence, structural analysis**.

### Mutation-Structure Cross-Reference

A run labels each mutation by where it sits in the computed flexibility profile
(hinge position, flexible region or stable region). That per-residue verdict
depends on the analysis and is not reproduced here.

### Key Findings

- Literature provides context on known mutations and stability factors
- Structural analysis identifies flexible regions that may be targets
- The cited work points at three routes to a more stable protein: lowering the
  entropy of unfolding, helix-dipole interactions, and engineered disulfide bonds

---

## Suggested Experiments

### 1. Rebuild the reported stabilising mutants
**Type:** Mutation
**Priority:** ***
**Difficulty:** Moderate

**Rationale:** G77A, A82P, S38D and N144D are reported stabilising substitutions, so they give a baseline for any new design.

**Methods:**
- Site-directed mutagenesis of the T4 lysozyme gene
- Express and purify wild type and each variant
- Thermal denaturation followed by circular dichroism

**Expected outcome:** Side-by-side stability comparison of wild type and each variant under one protocol.

---

### 2. Test an engineered disulfide bond
**Type:** Structure
**Priority:** **
**Difficulty:** Challenging

**Rationale:** Crosslinking two positions reported in the disulfide work tests whether the same route helps in your construct.

**Methods:**
- Pick cysteine pairs from the structure, keeping the active site clear
- Confirm bond formation under non-reducing conditions
- Compare stability with and without a reducing agent

**Expected outcome:** Evidence for or against disulfide engineering as a route for this protein.

---

*Illustrative example, hand-written in the report format this tool produces. Not output captured from a run.*`
    },

    egfr: {
        query: "Find inhibitors for EGFR kinase",
        steps: [
            {
                node: "parser",
                delay: 800,
                output: "EGFR, kinase",
                terminalOutput: [
                    { text: "Parsing query...", class: "info" },
                    { text: "Extracted target: EGFR", class: "success" },
                    { text: "Domain: kinase", class: "success" },
                    { text: "Query type: drug discovery", class: "info" }
                ]
            },
            {
                node: "uniprot",
                delay: 1100,
                output: "P00533",
                terminalOutput: [
                    { text: "Querying UniProt...", class: "info" },
                    { text: "Resolved: P00533 (EGFR)", class: "success" },
                    { text: "Full name: Epidermal growth factor receptor", class: "info" },
                    { text: "Organism: Homo sapiens", class: "info" }
                ]
            },
            {
                node: "pubmed",
                delay: 1500,
                output: "literature",
                terminalOutput: [
                    { text: "Searching PubMed...", class: "info" },
                    { text: "Query: EGFR kinase inhibitor resistance", class: "info" },
                    { text: "Literature summary assembled", class: "success" }
                ]
            },
            {
                node: "structure",
                delay: 1800,
                output: "kinase domain",
                terminalOutput: [
                    { text: "Searching PDB for EGFR...", class: "info" },
                    { text: "Kinase domain structures available with bound inhibitors", class: "success" },
                    { text: "Analysing the ATP site...", class: "info" }
                ]
            },
            {
                node: "chembl",
                delay: 1600,
                output: "compounds",
                terminalOutput: [
                    { text: "Querying ChEMBL...", class: "info" },
                    { text: "Approved EGFR inhibitors identified", class: "success" },
                    { text: "Gefitinib, erlotinib, osimertinib", class: "success" }
                ]
            },
            {
                node: "synthesis",
                delay: 1400,
                output: "3 inhibitors",
                terminalOutput: [
                    { text: "Combining literature, structure and compound data...", class: "info" },
                    { text: "Mutation-drug relationships summarised", class: "success" }
                ]
            },
            {
                node: "experiments",
                delay: 1000,
                output: "2 suggestions",
                terminalOutput: [
                    { text: "Generating experiment suggestions...", class: "info" },
                    { text: "2 experiments suggested", class: "success" }
                ]
            }
        ],
        report: `# Biotech Research Report

**Query:** Find inhibitors for EGFR kinase

---

## Literature Evidence

Well-established points about EGFR in non-small-cell lung cancer:

- Activating mutations in the EGFR kinase domain, chiefly **L858R** and **exon 19
  deletions**, sensitise tumours to the first-generation inhibitors **gefitinib**
  and **erlotinib**.
- The gatekeeper mutation **T790M** is a common mechanism of acquired resistance
  to those drugs.
- **Osimertinib** is a third-generation, covalent inhibitor active against
  T790M-positive disease.

*No paper list is reproduced in this example; a run prints the PubMed hits with
titles, authors, journals and relevance scores.*

---

## Computational Analysis

**Analyzed structures:** EGFR kinase domain

Structures of the kinase domain with bound inhibitors show the ATP site, the
hinge region and the gatekeeper position that T790M alters. A run reports the
flexibility profile from normal mode analysis here.

---

## Drug Discovery Analysis

**Targets analyzed:** EGFR

**Known drugs:** gefitinib, erlotinib, osimertinib

A run lists compounds returned by ChEMBL with their measured activity type,
value and potency class. Those measured values are left out of this hand-written
example rather than invented.

### Recommendations

1. Review approved drugs for repurposing opportunities
2. Cross-reference with structural data for binding site analysis
3. Consider structure-activity relationship (SAR) analysis

---

## Mutations Found in Literature

**Total mutations identified:** 3

- **L858R** (sensitising)
- **exon 19 deletion** (sensitising)
- **T790M** (resistance, gatekeeper)

---

## Synthesis & Insights

This analysis combines **literature evidence, structural analysis, drug discovery data**.

### Key Findings

- Literature provides context on known mutations and stability factors
- Structural analysis identifies flexible regions that may be targets
- Genotype decides the drug: sensitising mutations point to the earlier
  inhibitors, T790M points to osimertinib

---

## Suggested Experiments

### 1. Genotype before choosing a compound
**Type:** Assay
**Priority:** ***
**Difficulty:** Moderate

**Rationale:** The inhibitor that works depends on which EGFR mutation a model carries.

**Methods:**
- Sequence the EGFR kinase domain in each cell line used
- Run dose-response assays for each inhibitor against each genotype
- Include a wild-type line as a selectivity control

**Expected outcome:** A genotype-to-inhibitor map measured in your own hands.

---

### 2. Follow resistance as it emerges
**Type:** Binding
**Priority:** **
**Difficulty:** Challenging

**Rationale:** Resistance to EGFR inhibitors appears in the clinic, so a model that reproduces it is useful for testing next-generation compounds.

**Methods:**
- Culture a sensitive line under rising inhibitor concentration
- Sequence the kinase domain in resistant outgrowths
- Re-test the resistant lines against the other inhibitors

**Expected outcome:** Resistant derivatives with a known genotype for later screening.

---

*Illustrative example, hand-written in the report format this tool produces. Not output captured from a run.*`
    },

    braf: {
        query: "Analyze BRAF V600E mutation and find inhibitors",
        steps: [
            {
                node: "parser",
                delay: 800,
                output: "BRAF, V600E",
                terminalOutput: [
                    { text: "Parsing query...", class: "info" },
                    { text: "Extracted target: BRAF", class: "success" },
                    { text: "Mutation: V600E", class: "success" },
                    { text: "Query type: mutation + drug discovery", class: "info" }
                ]
            },
            {
                node: "uniprot",
                delay: 1100,
                output: "P15056",
                terminalOutput: [
                    { text: "Querying UniProt...", class: "info" },
                    { text: "Resolved: P15056 (BRAF)", class: "success" },
                    { text: "Full name: Serine/threonine-protein kinase B-raf", class: "info" },
                    { text: "Organism: Homo sapiens", class: "info" }
                ]
            },
            {
                node: "pubmed",
                delay: 1500,
                output: "literature",
                terminalOutput: [
                    { text: "Searching PubMed...", class: "info" },
                    { text: "Query: BRAF V600E inhibitor melanoma", class: "info" },
                    { text: "Literature summary assembled", class: "success" }
                ]
            },
            {
                node: "structure",
                delay: 1800,
                output: "kinase domain",
                terminalOutput: [
                    { text: "Searching PDB for BRAF...", class: "info" },
                    { text: "Kinase domain structures available with bound inhibitors", class: "success" },
                    { text: "Analysing the activation segment...", class: "info" }
                ]
            },
            {
                node: "chembl",
                delay: 1600,
                output: "compounds",
                terminalOutput: [
                    { text: "Querying ChEMBL...", class: "info" },
                    { text: "Approved BRAF inhibitors identified", class: "success" },
                    { text: "Vemurafenib, dabrafenib", class: "success" }
                ]
            },
            {
                node: "synthesis",
                delay: 1400,
                output: "V600E + drugs",
                terminalOutput: [
                    { text: "Combining literature, structure and compound data...", class: "info" },
                    { text: "Mutation-drug relationships summarised", class: "success" }
                ]
            },
            {
                node: "experiments",
                delay: 1000,
                output: "2 suggestions",
                terminalOutput: [
                    { text: "Generating experiment suggestions...", class: "info" },
                    { text: "2 experiments suggested", class: "success" }
                ]
            }
        ],
        report: `# Biotech Research Report

**Query:** Analyze BRAF V600E mutation and find inhibitors

---

## Literature Evidence

Well-established points about BRAF:

- **V600E** is the most common BRAF mutation in melanoma. The substitution leaves
  the kinase constitutively active and signalling through the MAPK pathway.
- V600E melanoma is treated with the targeted inhibitors **vemurafenib** and
  **dabrafenib**.
- BRAF inhibitors are combined with MEK inhibitors in the clinic, and resistance
  to single-agent treatment is well documented.

*No paper list is reproduced in this example; a run prints the PubMed hits with
titles, authors, journals and relevance scores.*

---

## Computational Analysis

**Analyzed structures:** BRAF kinase domain

Structures of the kinase domain with bound inhibitors show the ATP site and the
activation segment that carries position 600. A run reports the flexibility
profile from normal mode analysis here.

---

## Drug Discovery Analysis

**Targets analyzed:** BRAF

**Known drugs:** vemurafenib, dabrafenib

A run lists compounds returned by ChEMBL with their measured activity type,
value and potency class. Those measured values are left out of this hand-written
example rather than invented.

### Recommendations

1. Review approved drugs for repurposing opportunities
2. Cross-reference with structural data for binding site analysis
3. Consider structure-activity relationship (SAR) analysis

---

## Mutations Found in Literature

**Total mutations identified:** 1

- **V600E** (activating, activation segment)

---

## Synthesis & Insights

This analysis combines **literature evidence, structural analysis, drug discovery data**.

### Mutation-Structure Cross-Reference

Position 600 sits in the activation segment, the part of the kinase whose
conformation switches between active and autoinhibited states. A run reports
whether that residue falls in a flexible or hinge region of the analysed
structure.

### Key Findings

- Literature provides context on known mutations and stability factors
- Structural analysis identifies flexible regions that may be targets
- V600E is both the common mutation and the thing the approved inhibitors are
  selected against, so genotype and compound choice travel together

---

## Suggested Experiments

### 1. Compare inhibitors across BRAF genotypes
**Type:** Assay
**Priority:** ***
**Difficulty:** Moderate

**Rationale:** Approved BRAF inhibitors are used against V600E disease, so a genotype panel shows how far that carries in your models.

**Methods:**
- Assemble V600E-positive and BRAF wild-type lines
- Run dose-response assays for each inhibitor
- Read out MAPK pathway signalling alongside viability

**Expected outcome:** Measured difference in response between V600E and wild-type backgrounds.

---

### 2. Test BRAF plus MEK inhibition
**Type:** Assay
**Priority:** **
**Difficulty:** Moderate

**Rationale:** Combining a BRAF inhibitor with a MEK inhibitor is established clinical practice; a combination matrix shows the effect in your own models.

**Methods:**
- Run a dose matrix of a BRAF inhibitor against a MEK inhibitor
- Score for additivity or synergy
- Follow surviving cells for pathway reactivation

**Expected outcome:** A combination profile, and resistant populations for further study.

---

*Illustrative example, hand-written in the report format this tool produces. Not output captured from a run.*`
    }
};

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DEMO_SCENARIOS;
}
