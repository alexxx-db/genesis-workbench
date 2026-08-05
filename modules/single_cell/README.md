# single_cell module

Single-cell RNA-seq at scale: end-to-end processing (CPU or GPU), cell-type + disease annotation against
large reference atlases, similarity search, and gene-perturbation prediction.

## Submodules

| Submodule | Registers | Compute | UI workflow |
|---|---|---|---|
| [scanpy](scanpy/README.md) | *(pipeline — no model)* | CPU job | Single Cell Analysis (Scanpy) |
| [rapidssinglecell](rapidssinglecell/README.md) | *(pipeline — no model)* | GPU job | Single Cell Analysis (RAPIDS) |
| [scgpt](scgpt/README.md) | scGPT + perturbation | GPU endpoint | Gene Perturbation Prediction |
| [scimilarity](scimilarity/README.md) | SCimilarity (GeneOrder + GetEmbedding) + VS index (~23M cells) | CPU + MULTIGPU_MEDIUM + VS | Cell Type Annotation · Cell Similarity Search |
| [teddy](teddy/README.md) | Merck TEDDY-G 400M + 2M-cell reference + VS index | GPU_MEDIUM (A10) + VS | Cell Type + Disease Annotation |

## Deploy

```bash
# whole module (deploy core first):
./deploy.sh single_cell <aws|azure|gcp>
# a single submodule:
./deploy.sh single_cell <cloud> --only-submodule teddy/teddy_g_v1
```

## Notes

- SCimilarity and TEDDY build large reference tables + Vector Search indexes that are **preserved on
  destroy** (re-sync is multi-hour) — remove manually only for a clean slate.
- Cell-type annotation shows SCimilarity and TEDDY **side-by-side** on the same UMAP run.

Docs: [Engineering Guide](../../docs/ENGINEERING_GUIDE.md) · [in-app workflow docs](../core/app/backend/documentation/index.md)
