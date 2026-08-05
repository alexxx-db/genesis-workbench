# Guided Enzyme Optimization — reward-weighted design loop (orchestrator)

Submodule of the **large_molecule** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | No model of its own — an **orchestrator** with two Databricks jobs |
| **Serving / compute** | **Fast** job on a CPU cluster (endpoint-based AME + parent resampling); **Accurate** job on an **A10 GPU** cluster (in-process AME with Feynman-Kac steering). No serving endpoint. |
| **Used by (UI)** | [Guided Enzyme Optimization](../../core/app/backend/documentation/enzyme_optimization.md) |
| **Source · license** | GWB orchestrator around Proteina-Complexa-AME, ProteinMPNN, ESMFold, Boltz, NetSolP, PLTNUM, DeepSTABp, MHCflurry |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh large_molecule <aws|azure|gcp>
# just this submodule:
./deploy.sh large_molecule <cloud> --only-submodule enzyme_optimization/enzyme_optimization_v1
```

## Notes

- **Requires the endpoints it calls to be deployed first** — the four developability predictors and Proteina-Complexa live in the `small_molecule` module; deploy that module before running the Accurate path.
- Scores each candidate on motif RMSD, ESMFold pLDDT, optional Boltz substrate confidence, and four developability axes (solubility, anchor-relative half-life, Tm, immunogenic burden).
- Both jobs run **on-demand** on every cloud (spot reclamation kills multi-hour runs).

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/enzyme_optimization.md)
