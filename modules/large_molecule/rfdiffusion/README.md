# RFdiffusion — de novo protein backbone generation

Submodule of the **large_molecule** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | RFdiffusion → UC model, served as a serving endpoint |
| **Serving / compute** | **GPU_MEDIUM (A10)** serving endpoint |
| **Used by (UI)** | [Protein Design](../../core/app/backend/documentation/protein_design.md) — backbone generation / inpainting |
| **Source · license** | `RosettaCommons/RFdiffusion` · BSD-3 |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh large_molecule <aws|azure|gcp>
# just this submodule:
./deploy.sh large_molecule <cloud> --only-submodule rfdiffusion/rfdiffusion_v1.1.0
```

## Notes

- Generates a backbone; ProteinMPNN then assigns sequence, and ESMFold validates the fold.
- On A10 after human-scale designs exhausted T4 16 GB.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/protein_design.md)
