# MHCflurry 2.x — MHC-I immunogenicity / peptide presentation

Submodule of the **small_molecule** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | MHCflurry 2.x → UC model, served as a serving endpoint (sliding 9-mer scan, default 6-allele HLA panel) |
| **Serving / compute** | **CPU** serving endpoint |
| **Used by (UI)** | Immunogenic-burden developability axis in [Guided Enzyme Optimization](../../core/app/backend/documentation/enzyme_optimization.md) |
| **Source · license** | `openvax/mhcflurry` · Apache-2.0 |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh small_molecule <aws|azure|gcp>
# just this submodule:
./deploy.sh small_molecule <cloud> --only-submodule mhcflurry/mhcflurry_v2
```

## Notes

- Default panel is the Sette-style 6-allele HLA set (~95% global population coverage), centralized in the app and orchestrator as a single source of truth.
- Aggregates per-peptide presentation into a per-residue "immunogenic burden" score.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/enzyme_optimization.md)
