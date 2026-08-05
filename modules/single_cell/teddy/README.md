# TEDDY-G 400M — Merck single-cell foundation model

Submodule of the **single_cell** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | Merck TEDDY-G 400M (encoder-only, per-cell embeddings) → UC model + a ~2M-cell CELLxGENE reference Delta + `teddy_cell_index` Vector Search index |
| **Serving / compute** | **GPU_MEDIUM (A10)** serving endpoint (bf16 autocast); reference embed is a multinode `mapInPandas` GPU job |
| **Used by (UI)** | Joint cell-type + disease annotation on the UMAP tab (side-by-side with SCimilarity) — see [Cell Type Annotation](../../core/app/backend/documentation/cell_type_annotation.md) |
| **Source · license** | `Merck/TEDDY` · Apache-2.0 |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh single_cell <aws|azure|gcp>
# just this submodule:
./deploy.sh single_cell <cloud> --only-submodule teddy/teddy_g_v1
```

## Notes

- Use the **400M** variant (default) — the 70M encoder cannot distinguish some cell types in zero-shot retrieval; `teddy_model_size` should not be lowered.
- Reference embed + VS index build is multi-hour; both are preserved on destroy.
- A flattering Merck-account demo anchor ("your model, running governed on your Databricks data").

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/cell_type_annotation.md) · [detailed notes](teddy_g_v1/README.md)
