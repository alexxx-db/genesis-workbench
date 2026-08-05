# DiffDock — protein-ligand molecular docking

Submodule of the **small_molecule** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | DiffDock v1.1.3 (+ bundled ESM2 embeddings) → UC model, served as a serving endpoint |
| **Serving / compute** | GPU serving endpoint (lazy model load to stay under the serving startup timeout) |
| **Used by (UI)** | [Molecular Docking](../../core/app/backend/documentation/molecular_docking.md); also docking-in-reward for Guided Molecule Design |
| **Source · license** | `gcorso/DiffDock` · MIT |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh small_molecule <aws|azure|gcp>
# just this submodule:
./deploy.sh small_molecule <cloud> --only-submodule diffdock/diffdock_v1
```

## Notes

- ESM2 weights, score model, and confidence model are packaged as MLflow artifacts to avoid re-downloading at serving time.
- Blind docking via diffusion: predicts 3D binding poses and ranks them with the confidence model.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/molecular_docking.md)
