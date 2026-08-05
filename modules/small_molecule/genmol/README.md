# GenMol — generative small-molecule design

Submodule of the **small_molecule** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | GenMol (SAFE masked-diffusion generator) → UC model, served as a serving endpoint |
| **Serving / compute** | Classic **DBR 15.4 LTS GPU** endpoint (pins `pandas`/`transformers` that fail to build on serverless py3.12) |
| **Used by (UI)** | [Guided Molecule Design](../../core/app/backend/documentation/guided_molecule_design.md) — generate → score → reseed loop |
| **Source · license** | `nvidia/NV-GenMol-89M-v2` · NVIDIA Open Model License |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh small_molecule <aws|azure|gcp>
# just this submodule:
./deploy.sh small_molecule <cloud> --only-submodule genmol/genmol_v1
```

## Notes

- Grows a seed scaffold / binding motif into K candidates per iteration under hard constraints (Min QED, Max ClinTox).
- Cluster availability is per-cloud on-demand (overlaid in `databricks.yml`).

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/guided_molecule_design.md)
