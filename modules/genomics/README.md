# genomics module

Variant analysis at population scale: GPU germline variant calling, VCF→Delta ingestion, GWAS, and
ClinVar/ACMG variant annotation. All submodules are **batch jobs** (no serving endpoints).

## Submodules

| Submodule | Registers | Compute | UI workflow |
|---|---|---|---|
| [parabricks](parabricks/README.md) | *(GPU variant calling — container)* | GPU job | Variant Calling |
| [vcf_ingestion](vcf_ingestion/README.md) | *(Glow VCF→Delta)* | Spark job | VCF Ingestion |
| [variant_annotation](variant_annotation/README.md) | *(ClinVar/ACMG + Lakeview dashboard)* | Spark job | Variant Annotation |
| [gwas](gwas/README.md) | *(Glow GWAS)* | Multi-node Spark job | GWAS Analysis |

## Deploy

```bash
# whole module (deploy core first):
./deploy.sh genomics <aws|azure|gcp>
# a single submodule:
./deploy.sh genomics <cloud> --only-submodule gwas/gwas_v1
```

## Notes

- **Parabricks is container-based** and requires a Docker image + credentials — store the token in a secret
  scope, not a plaintext DAB variable ([HARDENING_CHECKLIST §3](../../HARDENING_CHECKLIST.md)).
- Typical flow: Variant Calling (FASTQ→VCF) → VCF Ingestion (VCF→Delta) → Variant Annotation; the UI's
  "From VCF Ingestion" pill chains ingestion output into annotation.
- The reference genome (GRCh38), ClinVar, ACMG panel, and demo VCFs are downloaded into UC volumes/tables
  at deploy.

Docs: [Engineering Guide](../../docs/ENGINEERING_GUIDE.md) · [in-app workflow docs](../core/app/backend/documentation/index.md)
