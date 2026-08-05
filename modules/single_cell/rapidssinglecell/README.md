# rapids-singlecell — GPU-accelerated single-cell pipeline

Submodule of the **single_cell** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | No serving model — a GPU-accelerated analysis **Databricks job** (CUDA equivalent of the Scanpy pipeline) |
| **Serving / compute** | GPU cluster batch job |
| **Used by (UI)** | [Single Cell Analysis](../../core/app/backend/documentation/single_cell_analysis.md) — Raw Processing (RAPIDS path) |
| **Source · license** | `scverse/rapids_singlecell` (RAPIDS) · MIT / Apache-2.0 |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh single_cell <aws|azure|gcp>
# just this submodule:
./deploy.sh single_cell <cloud> --only-submodule rapidssinglecell/rapidssinglecell_v0.0.1
```

## Notes

- Same pipeline shape as Scanpy but on GPU — use for large cell counts.
- Dependency pins are sensitive (`cuml`/`scikit-learn`/`numpy<2`); see the CHANGELOG before bumping.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/single_cell_analysis.md)
