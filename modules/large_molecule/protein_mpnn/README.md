# ProteinMPNN — sequence design for a fixed backbone

Submodule of the **large_molecule** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | ProteinMPNN → UC model, served as a serving endpoint (V8 two-column schema: `pdb` + `fixed_positions`) |
| **Serving / compute** | GPU serving endpoint |
| **Used by (UI)** | [Protein Design](../../core/app/backend/documentation/protein_design.md), [Inverse Folding](../../core/app/backend/documentation/inverse_folding.md), [Motif Scaffolding](../../core/app/backend/documentation/motif_scaffolding.md) |
| **Source · license** | `dauparas/ProteinMPNN` · MIT |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh large_molecule <aws|azure|gcp>
# just this submodule:
./deploy.sh large_molecule <cloud> --only-submodule protein_mpnn/protein_mpnn_v0.1.0
```

## Notes

- Payloads use `dataframe_records=[{...}]`; the legacy `inputs=`/split-orient shape is rejected by the V8 schema.
- Pairs with RFdiffusion (design) and ESMFold (validation) in the design pipelines.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/inverse_folding.md)
