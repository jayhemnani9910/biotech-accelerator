---
description: Run the full biotech research pipeline on a query and reason over the structured evidence
argument-hint: "\"<research question>\""
allowed-tools: Bash(biotech *), Bash(/usr/bin/python3 -m biotech_accelerator.main *)
---

Run the biotech research pipeline on this question, then reason over the structured evidence:

Question: $ARGUMENTS

1. Execute the pipeline in JSON mode so you get all the raw evidence (citations, structure analysis, compounds, cross-references):

```bash
/usr/bin/python3 -m biotech_accelerator.main "$ARGUMENTS" --json 2>/dev/null
```

2. From the JSON output, identify:
   - Top 3–5 relevant papers (prefer recent, high-impact journals)
   - Extracted mutations and whether any map to flexible regions or hinge residues
   - Notable drug candidates if the query is drug-related
   - Resolution warnings or errors to flag

3. Produce a concise synthesis with:
   - A direct answer to the user's question grounded in the evidence
   - Cited PMIDs (as `[PMID:xxxxxx]`) for every claim
   - Specific experiment suggestions if the question implies engineering / validation
   - Honest gaps: what the pipeline could not determine

Do not restate the full JSON back to the user. Use it as context and reply with the synthesis.
