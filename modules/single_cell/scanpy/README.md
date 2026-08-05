# Scanpy — CPU single-cell analysis pipeline

Submodule of the **single_cell** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | No serving model — a Scanpy analysis **Databricks job** |
| **Serving / compute** | CPU cluster batch job: QC → normalize → HVG → PCA → cluster → UMAP → markers, with optional diffusion pseudotime |
| **Used by (UI)** | [Single Cell Analysis](../../core/app/backend/documentation/single_cell_analysis.md) — Raw Processing (Scanpy path) |
| **Source · license** | `scverse/scanpy` · BSD-3 |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh single_cell <aws|azure|gcp>
# just this submodule:
./deploy.sh single_cell <cloud> --only-submodule scanpy/scanpy_v0.0.1
```

## Notes

- Results (UMAP, DE, enrichment, pseudotime) are explored in the interactive results viewer; runs are tracked in MLflow.
- Gene naming supports Ensembl-ID input (with species mapping) or a gene-symbol column — see the CHANGELOG "Gene mapping" note.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/single_cell_analysis.md)
