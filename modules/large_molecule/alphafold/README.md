# AlphaFold2 — high-accuracy protein structure prediction

Submodule of the **large_molecule** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | AlphaFold2 v2.3.2, plus a one-time download of the genetic databases (UniRef90/30, MGnify, small BFD, PDB70, PDB mmCIF) into UC volumes |
| **Serving / compute** | Batch Databricks job; the fold step runs on an **A10 GPU endpoint** with JAX unified memory (spills to host RAM) for long sequences (>~1300 aa) |
| **Used by (UI)** | [Protein Structure Prediction](../../core/app/backend/documentation/protein_structure_prediction.md) — high-accuracy (batch) path |
| **Source · license** | DeepMind AlphaFold2 · Apache-2.0 (weights CC BY 4.0) |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh large_molecule <aws|azure|gcp>
# just this submodule:
./deploy.sh large_molecule <cloud> --only-submodule alphafold/alphafold_v2.3.2
```

## Notes

- The genetic-DB download is large and slow; it is skip-if-exists on re-deploy.
- Uses MSA + templates (unlike ESMFold), so it is much slower but higher accuracy.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/protein_structure_prediction.md)
