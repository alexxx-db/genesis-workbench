# small_molecule module

Drug-discovery essentials: generate candidate molecules, profile ADMET/toxicity, dock to targets, design
protein binders, and score developability. Also hosts the four developability predictors used by the
large-molecule enzyme-optimization loop.

## Submodules

| Submodule | Registers | Compute | UI workflow |
|---|---|---|---|
| [chemprop](chemprop/README.md) | ChemProp (BBBP/ClinTox/ADMET) | Serving endpoint | ADMET & Safety |
| [diffdock](diffdock/README.md) | DiffDock (+ESM2) | GPU endpoint | Molecular Docking |
| [genmol](genmol/README.md) | GenMol generator | Classic DBR 15.4 GPU endpoint | Guided Molecule Design |
| [proteina_complexa](proteina_complexa/README.md) | 3 variants (binder / ligand / AME) | GPU endpoints | Protein & Ligand Binder Design · Motif Scaffolding |
| [netsolp](netsolp/README.md) | NetSolP-1.0 (solubility) | CPU endpoint | developability axis |
| [pltnum](pltnum/README.md) | PLTNUM-ESM2 (half-life) | GPU_SMALL endpoint | developability axis |
| [deepstabp](deepstabp/README.md) | DeepSTABp (Tm) | GPU_SMALL endpoint | developability axis |
| [mhcflurry](mhcflurry/README.md) | MHCflurry 2.x (immunogenicity) | CPU endpoint | developability axis |
| [kermt](kermt/README.md) | KERMT (fine-tunable ADMET GNN) | A10 GPU endpoint | ADMET & Safety (fine-tune) |

## Deploy

```bash
# whole module (deploy core first):
./deploy.sh small_molecule <aws|azure|gcp>
# a single submodule:
./deploy.sh small_molecule <cloud> --only-submodule genmol/genmol_v1
```

## Notes

- The four developability predictors (netsolp, pltnum, deepstabp, mhcflurry) + proteina_complexa are the
  scoring/generation backbone of **Guided Enzyme Optimization** (large_molecule) — deploy them if you plan
  to run that workflow's Accurate path.
- KERMT fine-tunes on a bundled TDC ClinTox sample at install so its endpoint is live out of the box; it
  is shown side-by-side with ChemProp in the ADMET tab.
- GenMol and KERMT run on **classic** DBR GPU (not serverless) because of hard dependency pins.

Docs: [Engineering Guide](../../docs/ENGINEERING_GUIDE.md) · [in-app workflow docs](../core/app/backend/documentation/index.md)
