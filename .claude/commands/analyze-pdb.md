---
description: Run Normal Mode Analysis on one or more PDB IDs and summarize the dynamics
argument-hint: <pdb_id> [<pdb_id> ...]
allowed-tools: Bash(biotech --pdb *), Bash(/usr/bin/python3 -m biotech_accelerator.main --pdb *)
---

Analyze the protein dynamics for: $ARGUMENTS

1. Run ProDy Normal Mode Analysis via the biotech CLI in JSON mode:

```bash
/usr/bin/python3 -m biotech_accelerator.main --pdb $ARGUMENTS --json 2>/dev/null
```

2. For each structure in the JSON output, extract:
   - Mean and max fluctuation (Å²)
   - Flexible regions (top 3 residue ranges by mobility)
   - Rigid core regions
   - Hinge residue positions
   - Vibrational entropy

3. Summarize:
   - Which regions are candidates for stabilizing mutations (rigid core)
   - Which regions are candidates for dynamics-altering mutations (hinges / flexible loops)
   - Any structures that failed to analyze and why

Be concise. One paragraph plus a bulleted list per structure is plenty.
