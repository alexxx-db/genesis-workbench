# Boltz-1 — multi-chain co-folding

Submodule of the **large_molecule** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | Boltz-1 → UC model, served as a serving endpoint |
| **Serving / compute** | GPU serving endpoint (Medium workload) |
| **Used by (UI)** | [Protein Structure Prediction](../../core/app/backend/documentation/protein_structure_prediction.md) — multi-chain (protein-protein, protein-ligand via SMILES) |
| **Source · license** | `boltz-community/boltz-1` · MIT |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh large_molecule <aws|azure|gcp>
# just this submodule:
./deploy.sh large_molecule <cloud> --only-submodule boltz/boltz_1
```

## Notes

- Input format is a dict, e.g. `{"input": "protein_A:SEQUENCE", "msa": "no_msa", "use_msa_server": "True"}`.
- Dependency pins are exact and known-good (`torch`/`flash_attn`/`transformers`); see the register notebook before bumping.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/protein_structure_prediction.md)
