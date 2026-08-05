# Proteina-Complexa — generative binder design & motif scaffolding

Submodule of the **small_molecule** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | Three variants → UC models: `proteina_complexa` (protein-protein binder), `proteina_complexa_ligand` (small-molecule binder), `proteina_complexa_ame` (motif scaffolding) |
| **Serving / compute** | GPU serving endpoints |
| **Used by (UI)** | [Protein Binder Design](../../core/app/backend/documentation/protein_binder_design.md), [Ligand Binder Design](../../core/app/backend/documentation/ligand_binder_design.md), [Motif Scaffolding](../../core/app/backend/documentation/motif_scaffolding.md); AME is the generator in Guided Enzyme Optimization |
| **Source · license** | `NVIDIA-Digital-Bio/Proteina-Complexa` · MIT (pinned to the `remove_openbabel` branch to stay GPL-clean) |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh small_molecule <aws|azure|gcp>
# just this submodule:
./deploy.sh small_molecule <cloud> --only-submodule proteina_complexa/proteina_complexa_v1
```

## Notes

- **Do not bump the upstream SHA** without checking for reintroduced `openbabel` imports (GPL-2.0) — see the CHANGELOG `proteina_no_openbabel` entry.
- Pin `transformers==5.5.0` and do **not** install `accelerate` (avoids the numpy `_core.multiarray` crash on DBR).

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/protein_binder_design.md) · [detailed notes](proteina_complexa_v1/README.md)
