# Contributing to Genesis Workbench

How to make changes that fit the repo's conventions and pass review. Read the
[Engineering Guide](docs/ENGINEERING_GUIDE.md) and [Architecture](docs/ARCHITECTURE.md) first for the
mental model; this file is the checklist.

> The deepest step-by-step patterns live in the [`claude_skills/`](claude_skills/) files — the
> [Development skill](claude_skills/SKILL_GENESIS_WORKBENCH_DEVELOPMENT.md) for adding a model/workflow and
> the [Batch Workflow Pattern skill](claude_skills/SKILL_GENESIS_WORKBENCH_BATCH_WORKFLOW_PATTERN.md) for
> job-backed workflows. This file summarizes the rules those skills enforce.

## The three hard rules

A PR that breaks any of these should not merge.

### 1. Exact-pin every pip dependency
Everywhere a dependency is declared — notebook `%pip install`, DAB `environments.spec.dependencies`,
PyFunc `pip_requirements` / `conda_env`, orchestrator notebooks — use `pkg==X.Y.Z`. No `latest`, no `>=`,
no bare names. This includes the transitively load-bearing ones (`torch`, `transformers`, `numpy`,
`pandas`, `scikit-learn`, `mlflow`, `cloudpickle`, `biopython`). Unpinned installs silently broke past
deploys when PyPI resolution drifted between register-time and serving-time. Verify each new dep's license
at the upstream source and add a row to the README dependency table; license-disqualified deps
(academic-only, CC-BY-NC, non-pinnable `git+…`) are blockers.

### 2. On-demand compute for every workflow job, on every cloud
Don't set `availability` in the base cluster spec. Overlay it per target in `databricks.yml`
(`aws_attributes.availability: ON_DEMAND`, `azure_attributes.availability: ON_DEMAND_AZURE`,
`gcp_attributes.availability: ON_DEMAND_GCP`). Spot reclamation kills the minutes-to-hours GPU jobs GWB
runs. Mirror `modules/large_molecule/boltz/boltz_1/databricks.yml`; if a submodule defines multiple jobs,
each needs its own per-cloud block.

### 3. Ship docs in the same PR
Every new feature (UI workflow, model, batch pipeline) lands with three doc artifacts:
1. A per-feature page in [`modules/core/app/backend/documentation/`](modules/core/app/backend/documentation/README.md)
   (follow the template there).
2. A bullet under the matching module in the root [`README.md`](README.md).
3. A dated **decision** entry in [`CHANGELOG.md`](CHANGELOG.md) — explain *what changed and why*,
   anti-patterns avoided, and files to mirror; not a generic "added X" line.

If you can't write the feature doc without hand-waving, the inputs/outputs/errors aren't finished yet.

## Adding a model or workflow (summary)

- **New model:** create the submodule bundle, write `01_register_<name>.py` (PyFunc; load weights in
  `load_context()`; `self.model.float()`; tiny `input_example`), `02_import_model_gwb.py`
  (`import_model_from_uc` → `deploy_model_endpoint` with the right `ModelCategory` and `workload_type`),
  the job YAML (GPU register task / serverless import task), and wire it into the parent module
  `deploy.sh`/`destroy.sh`. Add a submodule `README.md` (see the existing cards).
- **New UI workflow:** map display name → endpoint in `backend/app/services/endpoints.py`, add an endpoint
  wrapper in `backend/app/services/`, add a FastAPI route under `backend/app/routers/` (Pydantic models;
  `StreamingResponse` + SSE for anything slow), add a React tab under `frontend/src/components/`, and
  register it on its page under `frontend/src/pages/`. Reuse `Dialog`/`Drawer`/`useOutsideDismiss` — never
  hand-roll popover dismissal.
- **Batch (job-backed) workflow:** follow the five-layer pattern (orchestrator job, registration,
  dispatcher, Search Past Runs, result dialog). Pre-create the MLflow run from the dispatcher; return
  `(job_id, job_run_id)`; tag runs with `origin`/`feature`/`job_status`.

Full detail: the [Development](claude_skills/SKILL_GENESIS_WORKBENCH_DEVELOPMENT.md) and
[Batch Workflow](claude_skills/SKILL_GENESIS_WORKBENCH_BATCH_WORKFLOW_PATTERN.md) skills.

## Local development (the app)

Two terminals — FastAPI backend on `:8000`, Vite frontend on `:5173` (proxies `/api`). Auth-gated routes
need the `X-Forwarded-Access-Token` header only Databricks Apps SSO injects, so they 401 locally;
`/api/health` is the no-auth smoke test. Full setup: [`modules/core/app/README.md`](modules/core/app/README.md).

Bump the wheel version in `modules/core/library/genesis_workbench/pyproject.toml` whenever you change the
wheel, or the deployed app will import the stale cached version.

## Before you open a PR — checklist

- [ ] All new pip deps exact-pinned; README dependency table updated; licenses verified.
- [ ] Every workflow job is on-demand on all three clouds (per-cloud overlay in `databricks.yml`).
- [ ] `databricks bundle validate` passes for the touched bundle(s) on `prod_aws` / `prod_azure` / `prod_gcp`.
- [ ] Feature doc page + root README bullet + CHANGELOG decision entry included.
- [ ] Submodule/module `README.md` added or updated if you added/changed a submodule.
- [ ] Wheel version bumped if the wheel changed.
- [ ] Endpoint names read from `model_deployments` (via `get_endpoint_name_for_uc_model`), not env vars.
- [ ] Serving payloads use `inputs=` / `dataframe_records`, never `dataframe_split=`.
- [ ] Verified end-to-end on a real workspace; note the verification in the CHANGELOG entry.

## CI (target state)

There is no CI pipeline in the repo today — quality control is manual "verified on ci-demo" runs recorded
in the CHANGELOG. The [hardening checklist](HARDENING_CHECKLIST.md) §4 scopes the CI to add: lint + wheel
unit tests + `bundle validate` across all cloud targets on every PR, a nightly smoke-deploy, and a
version-bump guard for the wheel. Until that lands, run `databricks bundle validate` locally and complete
the checklist above by hand.
