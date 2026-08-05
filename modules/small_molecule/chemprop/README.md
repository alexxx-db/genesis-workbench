# ChemProp — molecular property / ADMET prediction

Submodule of the **small_molecule** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | ChemProp models (BBBP, ClinTox, 10-property ADMET) → UC models, served as serving endpoints |
| **Serving / compute** | Serving endpoint(s) |
| **Used by (UI)** | [ADMET & Safety](../../core/app/backend/documentation/admet_safety.md) |
| **Source · license** | `chemprop==2.2.3` · MIT |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh small_molecule <aws|azure|gcp>
# just this submodule:
./deploy.sh small_molecule <cloud> --only-submodule chemprop/chemprop_v2
```

## Notes

- Input is SMILES; output is a per-task property/probability dict.
- Shown side-by-side with the fine-tunable KERMT model in the ADMET tab.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/admet_safety.md)
