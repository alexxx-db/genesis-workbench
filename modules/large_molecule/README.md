# large_molecule module

Protein structure prediction, design, and engineering. Fold proteins, design novel backbones and
sequences, search 150M+ sequences, and run the reward-weighted enzyme-optimization loop.

## Submodules

| Submodule | Registers | Compute | UI workflow |
|---|---|---|---|
| [esmfold](esmfold/README.md) | ESMFold | GPU_MEDIUM (A10) endpoint | Structure Prediction (fast) |
| [alphafold](alphafold/README.md) | AlphaFold2 + genetic DBs | Batch job + A10 fold endpoint | Structure Prediction (accurate) |
| [boltz](boltz/README.md) | Boltz-1 | GPU endpoint | Structure Prediction (multi-chain) |
| [esm2_embeddings](esm2_embeddings/README.md) | ESM-2 650M embeddings | GPU endpoint | Sequence Search (backbone) |
| [sequence_search](sequence_search/README.md) | UniRef corpus + Vector Search index | Batch + VS | Sequence Similarity Search |
| [protein_mpnn](protein_mpnn/README.md) | ProteinMPNN | GPU endpoint | Protein Design · Inverse Folding · Motif Scaffolding |
| [rfdiffusion](rfdiffusion/README.md) | RFdiffusion | GPU_MEDIUM (A10) endpoint | Protein Design |
| [enzyme_optimization](enzyme_optimization/README.md) | *(orchestrator — no model)* | CPU (Fast) / A10 GPU (Accurate) jobs | Guided Enzyme Optimization |

## Deploy

```bash
# whole module (deploy core first; deploy modules one at a time):
./deploy.sh large_molecule <aws|azure|gcp>
# a single submodule:
./deploy.sh large_molecule <cloud> --only-submodule esmfold/esmfold_v1
```

## Dependencies between submodules

- `sequence_search` needs `esm2_embeddings` (embedding backbone for the index).
- `enzyme_optimization` (Accurate path) calls Proteina-Complexa + the four developability predictors — all
  in the **small_molecule** module — so deploy that module too before running it.

Docs: [Engineering Guide](../../docs/ENGINEERING_GUIDE.md) · [in-app workflow docs](../core/app/backend/documentation/index.md)
