# KERMT — fine-tunable ADMET GNN (NVIDIA-BioNeMo)

Submodule of the **small_molecule** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | KERMT (Kinetic GROVER Multi-Task GNN) → UC model. On install it runs **register → fine-tune (bundled TDC ClinTox sample) → deploy** so the `kermt_admet` endpoint is live out of the box |
| **Serving / compute** | Classic **A10 GPU**; in-process PyFunc serving (plain RDKit featurization) |
| **Used by (UI)** | [ADMET & Safety](../../core/app/backend/documentation/admet_safety.md) (side-by-side with ChemProp); [KERMT fine-tune](../../core/app/backend/documentation/kermt_admet.md) to bring your own assay |
| **Source · license** | `NVIDIA-BioNeMo/KERMT` (NV-KERMT-70M-v2, GROVERbase) · Apache-2.0 |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh small_molecule <aws|azure|gcp>
# just this submodule (v2 is current):
./deploy.sh small_molecule <cloud> --only-submodule kermt/kermt_v2
```

## Notes

- GROVERbase weights are OneDrive-only — pre-stage `grover_base.pt` to `/Volumes/<catalog>/<schema>/kermt/pretrained/` once (register step is skip-if-exists).
- The 3 top-level `cuik_molmaker` imports are guarded so KERMT runs pip-only on the RDKit path (keeps the Model Serving env buildable).
- Returns the exact ChemProp ADMET contract so the ADMET tab reuses its query path.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/kermt_admet.md)
