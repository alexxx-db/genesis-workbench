# scGPT — single-cell foundation model + perturbation

Submodule of the **single_cell** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | scGPT + a perturbation variant → UC models, served as serving endpoints |
| **Serving / compute** | GPU serving endpoint |
| **Used by (UI)** | [Gene Perturbation Prediction](../../core/app/backend/documentation/perturbation_prediction.md) — zero-shot knockout/overexpression effects |
| **Source · license** | `bowang-lab/scGPT` · MIT |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh single_cell <aws|azure|gcp>
# just this submodule:
./deploy.sh single_cell <cloud> --only-submodule scgpt/scgpt_v0.2.4
```

## Notes

- Weights are pre-loaded in `load_context()` and forced to float32 (`model.float()`) to avoid dtype mismatches — a recurring scGPT gotcha (see Troubleshooting).
- Keep `input_example` small (~10 cells × 1500 genes) so it survives HVG filtering and logs fast.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/perturbation_prediction.md) · [detailed notes](scgpt_v0.2.4/README.md)
