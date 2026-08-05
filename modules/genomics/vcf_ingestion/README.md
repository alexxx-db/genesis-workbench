# VCF Ingestion — VCF → Delta via Glow

Submodule of the **genomics** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | No serving model — a Spark/Glow **Databricks job** that ingests VCFs into Delta tables |
| **Serving / compute** | Spark cluster batch job |
| **Used by (UI)** | [VCF Ingestion](../../core/app/backend/documentation/vcf_ingestion.md) — feeds Variant Annotation & GWAS |
| **Source · license** | `projectglow/glow` · Apache-2.0 |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh genomics <aws|azure|gcp>
# just this submodule:
./deploy.sh genomics <cloud> --only-submodule vcf_ingestion/vcf_ingestion_v1
```

## Notes

- Output table names are auto-generated (`vcf_ingested_<timestamp>`) and logged as an MLflow tag for downstream lookup.
- The "From VCF Ingestion" pill in the Variant Annotation tab picks up these tables automatically.

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/vcf_ingestion.md)
