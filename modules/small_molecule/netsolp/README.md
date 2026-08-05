# NetSolP-1.0 — protein solubility prediction

Submodule of the **small_molecule** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | NetSolP-1.0 → UC model, served as a serving endpoint (ONNX Runtime) |
| **Serving / compute** | **CPU** serving endpoint |
| **Used by (UI)** | Solubility developability axis in [Guided Enzyme Optimization](../../core/app/backend/documentation/enzyme_optimization.md); [ADMET & Safety](../../core/app/backend/documentation/admet_safety.md) |
| **Source · license** | `tvinet/NetSolP-1.0` · BSD-3 |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh small_molecule <aws|azure|gcp>
# just this submodule:
./deploy.sh small_molecule <cloud> --only-submodule netsolp/netsolp_v1
```

## Notes

- Predicts solubility in *E. coli*. Weights (~85 MB ONNX) are git-bundled under `netsolp_v1/weights/` and survive destroy.
- Tiny dependency tree (`onnxruntime`, `fair-esm`); one of the cheapest endpoints to run.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/enzyme_optimization.md)
