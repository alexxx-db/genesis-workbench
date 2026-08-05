# bionemo module (optional)

NVIDIA BioNeMo integration — container definitions and workflows that expose pre-trained BioNeMo models,
starting with **ESM-2 fine-tuning + inference** on a custom assay. Container-based, so it requires a
Docker build before deploy.

> **Disclaimer:** NVIDIA and NVIDIA BioNeMo are trademarks of NVIDIA Corporation. Usage must comply with
> the NVIDIA EULA and BioNeMo licensing. See the root [README](../../README.md#important-disclaimer).

## What's in here

| Path | What it is |
|---|---|
| `docker/` | `Dockerfile` + `build_docker.sh` for the BioNeMo image |
| `notebooks/` | `bionemo_esm_finetune.py`, `bionemo_esm_inference.py`, `initialize.py` |
| `resources/` | DAB job resources (`bionemo_finetune_esm.yml`, `bionemo_inference_esm.yml`) |

## Prerequisites

1. Build and push the BioNeMo container (see `docker/build_docker.sh`).
2. Create `modules/bionemo/module.env` with `bionemo_docker_userid`, `bionemo_docker_token`,
   `bionemo_docker_image` (store the token in a secret scope for production — see
   [HARDENING_CHECKLIST §3](../../HARDENING_CHECKLIST.md)).

## Deploy

```bash
# deploy core and any dependent modules first:
./deploy.sh bionemo <aws|azure|gcp>
```

## Notes

- Ships a sample fine-tune dataset (BLAT_ECOLX beta-lactamase fitness landscape) auto-provisioned by
  `initialize.py`.
- The **KERMT** ADMET fine-tune (also NVIDIA-BioNeMo) lives in the **small_molecule** module, not here.

Docs: [Engineering Guide](../../docs/ENGINEERING_GUIDE.md) · [in-app: ESM2 fine-tuning](../core/app/backend/documentation/bionemo_esm2.md)
