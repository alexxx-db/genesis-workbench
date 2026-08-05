# DeepSTABp — protein melting temperature (Tm)

Submodule of the **small_molecule** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | DeepSTABp (Tm regression, ProtT5-XL backbone) → UC model, served as a serving endpoint |
| **Serving / compute** | **GPU_SMALL** serving endpoint |
| **Used by (UI)** | Thermostability developability axis in [Guided Enzyme Optimization](../../core/app/backend/documentation/enzyme_optimization.md) |
| **Source · license** | `CSBiology/deepStabP` · MIT |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh small_molecule <aws|azure|gcp>
# just this submodule:
./deploy.sh small_molecule <cloud> --only-submodule deepstabp/deepstabp_v1
```

## Notes

- Predicts melting temperature in °C; supports a `mt_mode` (`Cell`/`Lysate`) parameter.
- The ProtT5-XL backbone (~3 GB) and the MLP head are pulled at registration time.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/enzyme_optimization.md)
