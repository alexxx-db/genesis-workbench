# NVIDIA Parabricks — GPU germline variant calling

Submodule of the **genomics** module of Genesis Workbench.

| | |
|---|---|
| **Registers** | No serving model — a GPU variant-calling **Databricks job** (`fq2bam` alignment + `haplotypecaller`) |
| **Serving / compute** | GPU cluster batch job; container-based (requires a Parabricks Docker image + credentials) |
| **Used by (UI)** | [Variant Calling](../../core/app/backend/documentation/variant_calling.md) — FASTQ → VCF |
| **Source · license** | NVIDIA Parabricks (see repo disclaimer; NVIDIA EULA applies) |

## Deploy / redeploy

```bash
# whole module (from repo root):
./deploy.sh genomics <aws|azure|gcp>
# just this submodule:
./deploy.sh genomics <cloud> --only-submodule parabricks/parabricks_v1
```

## Notes

- Requires the reference genome (GRCh38) and a BWA index; the deploy downloads these via HTTPS to a UC volume.
- Store the Parabricks Docker token in a secret scope rather than a plaintext DAB variable (see `HARDENING_CHECKLIST.md` §3).

Docs: [Engineering Guide](../../../docs/ENGINEERING_GUIDE.md) · [in-app help](../../core/app/backend/documentation/variant_calling.md)
