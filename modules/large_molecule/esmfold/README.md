# ESMFold — fast single-sequence structure prediction

Submodule of the **large_molecule** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | ESMFold → UC model, served as a serving endpoint |
| **Serving / compute** | **GPU_MEDIUM (A10)** serving endpoint |
| **Used by (UI)** | [Protein Structure Prediction](../../core/app/backend/documentation/protein_structure_prediction.md); also the validation step in [Protein Design](../../core/app/backend/documentation/protein_design.md) and [Inverse Folding](../../core/app/backend/documentation/inverse_folding.md) |
| **Source · license** | `facebook/esmfold_v1` · MIT |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh large_molecule <aws|azure|gcp>
# just this submodule:
./deploy.sh large_molecule <cloud> --only-submodule esmfold/esmfold_v1
```

## Notes

- Fast because it needs no MSA — the go-to "wow" demo for structure prediction.
- On A10 because human-scale proteins exhausted T4 16 GB.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/protein_structure_prediction.md) · [detailed notes](esmfold_v1/README.md)
