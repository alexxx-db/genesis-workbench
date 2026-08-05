# ESM-2 Embeddings — protein sequence embeddings

Submodule of the **large_molecule** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | ESM-2 650M embedding model → UC model, served as a serving endpoint (1280-dim mean-pooled embeddings) |
| **Serving / compute** | GPU serving endpoint; batch embedding runs via `ai_query()` against the endpoint |
| **Used by (UI)** | Backbone for [Sequence Similarity Search](../../core/app/backend/documentation/sequence_search.md) (feeds the Vector Search indexes) |
| **Source · license** | `facebook/esm2_t33_650M_UR50D` · MIT |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh large_molecule <aws|azure|gcp>
# just this submodule:
./deploy.sh large_molecule <cloud> --only-submodule esm2_embeddings/esm2_embeddings_v1
```

## Notes

- The embeddings populate the `gene_sequence_embedding_index` and `sequence_embedding_index` Vector Search indexes used by protein similarity search.
- Deploy this before (or with) `sequence_search`, which builds the corpus and index on top of it.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/sequence_search.md)
