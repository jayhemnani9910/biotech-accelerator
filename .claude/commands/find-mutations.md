---
description: Search PubMed for mutations reported for a given protein and map them to structure if available
argument-hint: "\"<protein name>\""
allowed-tools: Bash(biotech *), Bash(/usr/bin/python3 -m biotech_accelerator.main *)
---

Find reported mutations for: $ARGUMENTS

1. Use the full pipeline to search literature and resolve the protein to structures in one shot:

```bash
/usr/bin/python3 -m biotech_accelerator.main "What mutations have been reported for $ARGUMENTS?" --json 2>/dev/null
```

2. From the JSON output, extract every mutation found in `literature_citations` (look for entries in the report's mutation list and their source PMIDs).

3. If the pipeline resolved PDB structures, cross-reference each mutation's position with the reported flexible regions and hinge residues.

4. Report:
   - A table of mutations: original, position, mutant, source PMID, structural context (hinge / flexible / stable / no structure)
   - Which mutations are most likely to affect dynamics vs stability
   - Which proteins/structures could not be resolved

If no mutations are found, say so plainly — don't invent any.
