# Genesis Workbench — Engineering Guide

**Audience:** a Databricks Data + AI engineer who has to *use, demo, maintain, or extend* Genesis
Workbench (GWB). This is the human front door — it orients you, then points you at the deeper docs
instead of duplicating them. If you only read one file before touching the repo, read this one.

> New to the biology terms (residue, pLDDT, SMILES, GWAS, scRNA-seq)? Keep
> [`GLOSSARY.md`](../GLOSSARY.md) open in a tab.

---

## 60-second mental model

GWB is a **Databricks-native blueprint** that puts ~25 open biological foundation models behind one
governed app. Every capability follows the same pipeline — learn it once and every module reads the same:

```
Registration notebook (GPU job)
  → mlflow.pyfunc.log_model()  →  Unity Catalog model (catalog.schema.model)
    → import_model_from_uc()   →  GWB `models` / `model_deployments` tables
      → deploy_model()         →  Model Serving endpoint (scale-to-zero)
        → React + FastAPI app  →  calls the endpoint via the Databricks SDK
```

Three consumers share **one** capability executor (`genesis_workbench` wheel): the **UI**, the
**Vortex** visual workflow canvas, and the **MCP server**. A model you register once is reachable from
all three.

**Everything is Databricks primitives:** Asset Bundles (IaC), Unity Catalog (models, volumes, grants),
MLflow (registry + experiments), Model Serving (endpoints), and Databricks Apps (the UI + MCP server).

For the full picture — layers, the Delta data model, and how the shared executor serves all three
consumers — read [`ARCHITECTURE.md`](ARCHITECTURE.md). Every **module** and **submodule** also has its own
README (`modules/<module>/README.md` and `modules/<module>/<submodule>/README.md`) with what it registers,
its compute/endpoint, and the exact `--only-submodule` deploy command.

---

## Repo map

```
genesis-workbench/
├── deploy.sh / destroy.sh / cleanup.sh   # root orchestrators: ./deploy.sh <module> <cloud>
├── application.env                        # you create this: workspace_url, catalog, schema, warehouse
├── aws.env / azure.env / gcp.env          # per-cloud GPU node types + serving workload sizes
├── README.md                              # product overview + full model/dataset inventory
├── Installation.md                        # authoritative deploy/destroy mechanics + prerequisites
├── CHANGELOG.md                           # decision log — read this for known issues & "why" context
├── GLOSSARY.md                            # life-sciences terms cheat sheet
├── HARDENING_CHECKLIST.md                 # productionization / security SOW scope
├── claude_skills/                         # deep how-to guides (AI-authored, human-readable)
├── docs/                                  # diagrams, images, this guide, doc index
└── modules/
    ├── core/                              # UI app + MCP server + shared wheel + settings tables
    │   ├── app/                           # React (frontend/) + FastAPI (backend/) — see app/README.md
    │   ├── mcp_app/                        # MCP server (thin adapter over the shared executor)
    │   ├── library/genesis_workbench/     # the shared wheel: models, capabilities, executor
    │   ├── notebooks/                      # deploy_model, grant_app_permissions, start_all_endpoints…
    │   └── resources/                      # DAB resources: apps, jobs, volumes, experiments
    ├── large_molecule/   (8 submodules)    # esmfold, alphafold, boltz, esm2_embeddings,
    │                                       #   protein_mpnn, rfdiffusion, sequence_search, enzyme_optimization
    ├── single_cell/      (5 submodules)    # scanpy, rapidssinglecell, scgpt, scimilarity, teddy
    ├── small_molecule/   (9 submodules)    # genmol, kermt, diffdock, chemprop, proteina_complexa,
    │                                       #   netsolp, pltnum, deepstabp, mhcflurry
    ├── genomics/         (4 submodules)    # parabricks, vcf_ingestion, variant_annotation, gwas
    └── bionemo/                            # optional; ESM-2 fine-tune/inference (container-based)
```

Each **submodule** is a self-contained Databricks Asset Bundle: `databricks.yml`, `variables.yml`,
`deploy.sh`, `destroy.sh`, `resources/*.yml`, and `notebooks/`. Deploy one in isolation with
`--only-submodule <path>`.

---

## USE — deploy and run it

**Full, authoritative steps:** [`Installation.md`](../Installation.md). Guided/interactive path:
[`claude_skills/SKILL_GENESIS_WORKBENCH_DEPLOY_WIZARD.md`](../claude_skills/SKILL_GENESIS_WORKBENCH_DEPLOY_WIZARD.md).
Quick reference below.

### Prerequisites (do these first)

- **Workspace admin** on a Databricks workspace with **GPU quota** (T4 + A10; on Azure some models need
  multi-GPU — check `azure.env`). GPU quota is the #1 thing that blocks a deploy — confirm it early.
- Databricks CLI authenticated to the target workspace as the **DEFAULT** profile.
- Python 3.11 (use a venv/conda dedicated to this app).
- A **UC catalog** (existing or new) and a **dedicated schema** used *only* by GWB.
- A **2X-Small SQL Warehouse** (grab its ID).
- `application.env` at the repo root + `module.env` in `modules/core/` (see Installation.md for fields).

### Deploy

```bash
# 1. core FIRST — stands up the UI app, the MCP server, the wheel, and the settings tables
./deploy.sh core <aws|azure|gcp>

# 2. then each module, ONE AT A TIME (wait for each module's first jobs to reach RUNNING first)
./deploy.sh large_molecule <cloud>
./deploy.sh single_cell    <cloud>
./deploy.sh small_molecule <cloud>
./deploy.sh genomics       <cloud>
./deploy.sh bionemo        <cloud>   # optional — requires a BioNeMo container build
```

Deploying serially serializes GPU cluster-create and surfaces quota problems one module at a time.
Registration jobs download weights, log PyFunc models, and provision endpoints — this can take **many
hours**. That's expected.

### Verify

- **Jobs:** all cluster-based jobs should be `ON_DEMAND` and reach `RUNNING`/`SUCCEEDED`. (Known DAB
  quirk: some jobs come up `SPOT_WITH_FALLBACK` on first deploy — see
  [Troubleshooting → ON_DEMAND not enforced](../claude_skills/SKILL_GENESIS_WORKBENCH_TROUBLESHOOTING.md).)
- **Endpoints:** `databricks serving-endpoints list` → look for `gwb_*` endpoints reaching `READY`.
- **App:** `databricks apps get genesis-workbench` → open its URL. `/api/health` is the fastest smoke test.
- **MCP:** `databricks apps get mcp-genesis-workbench` → server is at `<url>/mcp`.

### Access & entitlement

The app runs as its own service principal. Grants (endpoint `CAN_QUERY`, job `CAN_MANAGE_RUN`, volume
R/W, model `EXECUTE`) are applied at deploy by `grant_app_permissions_job`. To let a group use the app,
add a `CAN_USE` entry for that group to the app's `permissions:` block and redeploy — **do not** share
with "all users" (the MCP server has no per-caller authZ; see
[`HARDENING_CHECKLIST.md`](../HARDENING_CHECKLIST.md) §2).

---

## DEMO — run a clean customer session

Full playbook (agenda, framing, per-account anchors): the [Workshop one-pager](WORKSHOP_ONEPAGER.md).
Operational essentials below.

**T-minus days (never live):**
- Deploy **only the modules you'll show** — a full install is a lot of GPU spend and long deploys.
- Confirm GPU quota with the account team.
- Pre-run anything slow or costly (AlphaFold on long sequences, Accurate-mode enzyme optimization ~$22
  GPU) and save the results to show; don't run these live.

**T-minus minutes:**
- **Pre-warm endpoints** so scale-to-zero cold starts (5–20 min for big models) don't stall you: Settings
  → Endpoint Management → **Start All Endpoints** (pick a duration covering the session).

**Live, lead with fast + visual:**
- ESMFold real-time structure prediction (Large Molecule → Structure Prediction).
- SCimilarity / TEDDY cell-type annotation with UMAP (Single Cell).
- For a technical audience: show **Vortex** (describe a goal → generated runnable pipeline) and the
  **MCP server** ("every model is a tool your agents can call").

**Anchor on the customer's modality:** biologics/genetics → large_molecule + genomics; single-cell (esp.
Merck/TEDDY) → single_cell; small-molecule discovery → small_molecule ADMET/docking/GenMol.

**Teardown:** `./destroy.sh <module> <cloud>` (core **last**). Vector Search indexes and large reference
tables are intentionally **preserved** on destroy (re-sync is multi-hour) — clean those separately if the
workspace is ephemeral. See
[`SKILL_GENESIS_WORKBENCH_DESTROY_WIZARD.md`](../claude_skills/SKILL_GENESIS_WORKBENCH_DESTROY_WIZARD.md).

---

## MAINTAIN — keep it healthy

### Redeploy the UI without wiping settings

**Never run `./deploy.sh core` on a populated install** — its `initialize_core_job` drops and recreates
the settings/models/model_deployments tables and you lose all registrations. Use `update.sh` instead:

```bash
cd modules/core
./update.sh <cloud>              # full redeploy: wheel rebuild + bundle deploy + grants + UC volume copy
./update.sh <cloud> --ui-only    # fastest: rebuild frontend + redeploy app; skips grants/secrets/volume copy
```

`update.sh` (non-`--ui-only`) also redeploys the MCP app; `--ui-only` skips it.

### Common failures — go straight to the index

[`SKILL_GENESIS_WORKBENCH_TROUBLESHOOTING.md`](../claude_skills/SKILL_GENESIS_WORKBENCH_TROUBLESHOOTING.md)
is the categorized runbook (registration dtype errors, serving payload-shape errors, SCimilarity request
sizing, AlphaFold download failures, ON_DEMAND enforcement, Mol* styling, `.deployed` lock). Always cross-check
[`CHANGELOG.md`](../CHANGELOG.md) — it records the *root cause and the decision*, not just the fix.

Where to look when something breaks:
- **Registration job failed** → job run output; the traceback usually lands in `load_context()`/`predict()`
  (dtype mismatch, wrong input shape, missing artifact).
- **Endpoint failing/won't start** → Serving → `<endpoint>` → Logs (container build + invocation logs).
- **App error** → Databricks App logs for `genesis-workbench`.
- **Endpoint name lookups** → the `model_deployments` table is the single source of truth
  (`get_endpoint_name_for_uc_model(short_name)`), not env-var construction.

### Cost control

- Endpoints default to **scale-to-zero**; leave them there except during a demo window.
- **Start All Endpoints** keep-alive intentionally *fights* scale-to-zero — only use it for demos and let
  it expire.
- Heavy registration/optimization jobs run **on-demand** (spot reclamation kills multi-hour runs); this is
  a deliberate cost/reliability trade — see the on-demand hard rule under **EXTEND**.
- For chargeback/budgets and inference-table observability (off by default), see
  [`HARDENING_CHECKLIST.md`](../HARDENING_CHECKLIST.md) §5–6.

### Upgrading a model / bumping the wheel

- Bump `modules/core/library/genesis_workbench/pyproject.toml` **version** whenever you change the wheel —
  otherwise pip's resolver skips reinstall and the app imports the stale wheel (a documented past outage).
- Re-registering a model with a new `workload_type` is more reliable than an in-place endpoint config edit
  (in-place edits can time out on container creation).

---

## EXTEND — add a model or workflow

Full step-by-step with copy-paste patterns:
[`SKILL_GENESIS_WORKBENCH_DEVELOPMENT.md`](../claude_skills/SKILL_GENESIS_WORKBENCH_DEVELOPMENT.md). For a
long-running batch workflow (form → job → MLflow → search past runs → result dialog), follow
[`SKILL_GENESIS_WORKBENCH_BATCH_WORKFLOW_PATTERN.md`](../claude_skills/SKILL_GENESIS_WORKBENCH_BATCH_WORKFLOW_PATTERN.md).

### Three hard rules (a PR that breaks these should not merge)

1. **Exact-pin every pip dependency** (`pkg==X.Y.Z`) everywhere — notebook `%pip`, DAB
   `environments.spec.dependencies`, PyFunc `pip_requirements`/`conda_env`. Unpinned installs silently
   broke past deploys when PyPI resolution drifted between register-time and serving-time.
2. **On-demand compute for every workflow job, on every cloud.** Don't set `availability` in the base
   cluster spec; overlay `aws/azure/gcp_attributes.availability` per target in `databricks.yml`. Spot
   reclamation kills multi-hour GPU runs.
3. **Ship docs in the same PR:** a per-feature page in
   [`modules/core/app/backend/documentation/`](../modules/core/app/backend/documentation/) (template:
   its [`README.md`](../modules/core/app/backend/documentation/README.md)), a bullet in the root
   [`README.md`](../README.md), and a decision entry in [`CHANGELOG.md`](../CHANGELOG.md).

### Add a model (5 steps)

1. **Create the submodule** `modules/<module>/<name>/<name>_v1/` with `databricks.yml`, `variables.yml`,
   `deploy.sh`, `destroy.sh`, `resources/{volumes.yml,register_<name>.yml}`, `notebooks/`.
2. **`01_register_<name>.py`** — download weights (skip-if-exists), define an `mlflow.pyfunc.PythonModel`
   (load weights **once** in `load_context()`, call `self.model.float()`, keep `input_example` tiny),
   `log_model(..., registered_model_name=f"{catalog}.{schema}.{model_name}")`.
3. **`02_import_model_gwb.py`** — `import_model_from_uc(...)` then `deploy_model(...)` with the right
   `ModelCategory` and `workload_type` (`CPU` / `GPU_SMALL` / `GPU_MEDIUM` / `MULTIGPU_MEDIUM`).
4. **Job YAML** — register task on a GPU job cluster, import/deploy task on serverless
   (`environments`); download-only tasks belong on CPU nodes.
5. **Wire into** the parent `modules/<module>/deploy.sh` and `destroy.sh` module loop.

### Add a UI workflow (5 steps)

1. Map the display name → endpoint in `backend/app/services/endpoints.py` (`_MODEL_ENDPOINT_MAP`,
   case-sensitive).
2. Add an endpoint wrapper (e.g. in `utils/protein_design.py`) — use `inputs=[…]` / `dataframe_records`,
   never `dataframe_split=`.
3. Add a FastAPI route in the right router under `backend/app/routers/` (Pydantic request/response;
   `HTTPException` on failure; `StreamingResponse` + SSE for anything >~5 s).
4. Add a React tab component under `frontend/src/components/` (TanStack Query mutation; stable query keys;
   reuse `Dialog`/`Drawer`/`useOutsideDismiss` — never hand-roll popover dismissal).
5. Register the tab on its page under `frontend/src/pages/`.

### Local dev loop (app)

Two terminals (backend on :8000, Vite frontend on :5173 proxying `/api`). Auth-gated routes need the
`X-Forwarded-Access-Token` header that only Databricks Apps SSO injects, so they 401 locally;
`/api/health` is the no-auth smoke test. Full instructions in
[`modules/core/app/README.md`](../modules/core/app/README.md).

### Capabilities, Vortex & MCP

New endpoints/workflows become **capabilities** in the shared registry (published to the `node_catalog`
table) and are automatically reachable from Vortex and MCP through the shared executor. Design details:
[`CAPABILITY_REGISTRY_DESIGN.md`](../CAPABILITY_REGISTRY_DESIGN.md),
[`MCP_SERVER_APP_PLAN.md`](../MCP_SERVER_APP_PLAN.md),
[`VORTEX_CONVERTIBLE_FIELDS.md`](../VORTEX_CONVERTIBLE_FIELDS.md).

---

## Where to go next

| I want to… | Read |
|---|---|
| Understand how it fits together (pipeline · data model · executor · consumers) | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) |
| Understand the product & see the full model/dataset inventory | [`README.md`](../README.md) |
| Deploy / destroy step by step | [`Installation.md`](../Installation.md) · [`docs/Module.md`](Module.md) |
| Be walked through a guided deploy | [`SKILL_..._DEPLOY_WIZARD.md`](../claude_skills/SKILL_GENESIS_WORKBENCH_DEPLOY_WIZARD.md) |
| Fix a specific error | [`SKILL_..._TROUBLESHOOTING.md`](../claude_skills/SKILL_GENESIS_WORKBENCH_TROUBLESHOOTING.md) · [`CHANGELOG.md`](../CHANGELOG.md) |
| Add a model / workflow / tab | [`SKILL_..._DEVELOPMENT.md`](../claude_skills/SKILL_GENESIS_WORKBENCH_DEVELOPMENT.md) |
| Add a batch (job-backed) workflow | [`SKILL_..._BATCH_WORKFLOW_PATTERN.md`](../claude_skills/SKILL_GENESIS_WORKBENCH_BATCH_WORKFLOW_PATTERN.md) |
| Understand each UI tab / workflow | [`.../documentation/index.md`](../modules/core/app/backend/documentation/index.md) |
| Work on the React + FastAPI app | [`modules/core/app/README.md`](../modules/core/app/README.md) |
| Productionize / harden for a customer | [`HARDENING_CHECKLIST.md`](../HARDENING_CHECKLIST.md) |
| Look up a biology term | [`GLOSSARY.md`](../GLOSSARY.md) |
