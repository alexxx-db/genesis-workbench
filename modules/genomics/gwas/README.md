# GWAS Analysis — genome-wide association studies via Glow

Submodule of the **genomics** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | No serving model — a Glow GWAS **Databricks job** |
| **Serving / compute** | Multi-node Spark cluster batch job |
| **Used by (UI)** | [GWAS Analysis](../../core/app/backend/documentation/gwas_analysis.md) — associate variants with phenotypes |
| **Source · license** | `projectglow/glow` · Apache-2.0 |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh genomics <aws|azure|gcp>
# just this submodule:
./deploy.sh genomics <cloud> --only-submodule gwas/gwas_v1
```

## Notes

- Ships a 1000 Genomes chr6 sample VCF as demo input.
- All-NULL p-value results are handled gracefully with a clear user message rather than a crash.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/gwas_analysis.md)
