# SCimilarity — cell embeddings + 23M-cell similarity search

Submodule of the **single_cell** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | SCimilarity → UC models. Endpoints: **GeneOrder** (CPU), **GetEmbedding** (MULTIGPU_MEDIUM). SearchNearest is Vector-Search-backed: `scimilarity_cells` Delta + `scimilarity_cell_index` (128-dim, ~23M cells) |
| **Serving / compute** | Mixed CPU + GPU endpoints, plus a Vector Search index |
| **Used by (UI)** | [Cell Type Annotation](../../core/app/backend/documentation/cell_type_annotation.md), [Cell Similarity Search](../../core/app/backend/documentation/cell_similarity.md) |
| **Source · license** | `Genentech/scimilarity` (v0.4.0) · Apache-2.0 |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh single_cell <aws|azure|gcp>
# just this submodule:
./deploy.sh single_cell <cloud> --only-submodule scimilarity/scimilarity_v0.4.0_weights_v1.1
```

## Notes

- The 12 GB reference download and the Vector Search index are **preserved on destroy** (re-sync is multi-hour). Remove them manually only for a fully clean slate.
- Batch embedding requests in small groups (~5 cells) — a single request cannot exceed 16 MB.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/cell_type_annotation.md) · [detailed notes](scimilarity_v0.4.0_weights_v1.1/README.md)
