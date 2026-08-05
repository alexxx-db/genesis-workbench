# PLTNUM-ESM2 — protein half-life / relative stability

Submodule of the **small_molecule** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | PLTNUM-ESM2 (relative half-life ranker, ESM-2 650M backbone) → UC model, served as a serving endpoint |
| **Serving / compute** | **GPU_SMALL** serving endpoint |
| **Used by (UI)** | Half-life developability axis in [Guided Enzyme Optimization](../../core/app/backend/documentation/enzyme_optimization.md) |
| **Source · license** | `sagawa/PLTNUM-ESM2-NIH3T3` · MIT |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh small_molecule <aws|azure|gcp>
# just this submodule:
./deploy.sh small_molecule <cloud> --only-submodule pltnum/pltnum_v1
```

## Notes

- Output is a **relative** stability rank, not absolute hours — the enzyme-optimization loop anchors it against a user-supplied reference enzyme + margin.
- Weights auto-pull from HuggingFace at registration time.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/enzyme_optimization.md)
