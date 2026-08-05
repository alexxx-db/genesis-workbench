# Variant Annotation — ClinVar / ACMG annotation

Submodule of the **genomics** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | No serving model — an annotation **Databricks job** that writes per-run Delta tables + a Lakeview dashboard |
| **Serving / compute** | Spark cluster batch job |
| **Used by (UI)** | [Variant Annotation](../../core/app/backend/documentation/variant_annotation.md) — annotate variants with clinical significance |
| **Source · license** | ClinVar GRCh38 (NCBI, public domain) + ACMG SF v3.2 81-gene panel |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh genomics <aws|azure|gcp>
# just this submodule:
./deploy.sh genomics <cloud> --only-submodule variant_annotation/variant_annotation_v1
```

## Notes

- Writes **per-run** tables (`<base>__<run_name>_<mlflow_run_id_prefix>`) so Glow's VCF-INFO struct drift can't collide across runs and concurrent runs stay disjoint; cleanup is `DROP TABLE`.
- Filters by BRCA1/BRCA2, the ACMG SF v3.2 81-gene panel, or a custom region (BED).

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/variant_annotation.md)
