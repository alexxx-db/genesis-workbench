# Genesis Workbench — Architecture

How the pieces fit together, for engineers who need to **maintain or extend** the platform. This is the
human-readable synthesis; the deeper design notes live in
[`CAPABILITY_REGISTRY_DESIGN.md`](../CAPABILITY_REGISTRY_DESIGN.md),
[`MCP_SERVER_APP_PLAN.md`](../MCP_SERVER_APP_PLAN.md), and
[`VORTEX_CONVERTIBLE_FIELDS.md`](../VORTEX_CONVERTIBLE_FIELDS.md). For the "how do I operate it" view, see
the [Engineering Guide](ENGINEERING_GUIDE.md).

---

## The one pipeline every model follows

```
Registration notebook (GPU job)
  → mlflow.pyfunc.log_model()          → Unity Catalog model (catalog.schema.model)
    → import_model_from_uc()           → GWB `models` table  (registry: display name → UC model)
      → deploy_model_endpoint()        → Model Serving endpoint (scale-to-zero)
                                          + row in `model_deployments` (endpoint registry)
        → capability published         → `node_catalog` table (ports, value shapes, dtypes)
          → consumed by UI · Vortex · MCP through one shared executor
```

Learn this once and every module reads the same. A model is registered exactly once; from then on it is
reachable identically from all three consumers.

---

## Layers

### 1. Infrastructure as code — Databricks Asset Bundles

Every submodule is a self-contained bundle (`databricks.yml` + `variables.yml` + `resources/*.yml`).
Cloud portability is achieved by keeping the base cluster spec cloud-neutral and overlaying
`aws/azure/gcp_attributes` per `targets:` block (`prod_aws` / `prod_azure` / `prod_gcp`). The `deploy.sh`
scripts wrap `databricks bundle validate/deploy/run` and add the steps bundles can't express (wheel
build, UC volume copy, grants, serial submodule loop).

### 2. Unity Catalog — governance & artifacts

- **Models** live at the three-level namespace `catalog.schema.model` (`mlflow.set_registry_uri("databricks-uc")`).
- **Volumes** are UC-managed (`libraries`, `model_weights`, `ai_canvas`, plus per-submodule caches).
- **Grants** are applied at deploy by `grant_app_permissions_job` to the app service principals:
  `CAN_QUERY` on endpoints, `CAN_MANAGE_RUN` on jobs, `READ/WRITE VOLUME`, model `EXECUTE`, and catalog/schema `USE`.

### 3. MLflow — registry + experiments

PyFunc models are logged with exact-pinned `pip_requirements`, a tiny `input_example`, and a signature,
then registered to UC. Two experiment paths: a system path under `/Shared/dbx_genesis_workbench_models/`
for registration artifacts, and a per-user path under `/Users/<email>/<folder>/` for workflow run
results (the folder is configurable on the app's Profile page). Workflow runs are tracked with tags
(`origin=genesis_workbench`, `feature=…`, `job_status=…`) so *Search Past Runs* can find them.

### 4. Model Serving — endpoints

Endpoints are created programmatically by `deploy_model_endpoint()` in the shared wheel, default
**scale-to-zero**. Workload class comes from the cloud env files (`CPU` / `GPU_SMALL` / `GPU_MEDIUM` /
`MULTIGPU_MEDIUM`). Some capabilities are **batch jobs** rather than endpoints (AlphaFold, the single-cell
pipelines, all of genomics, the enzyme-optimization orchestrator) — these dispatch a Databricks Job and
track status through MLflow.

### 5. The app — React + FastAPI on Databricks Apps

`core` deploys two Databricks Apps, each as its own service principal:

- **`genesis-workbench`** — the UI. FastAPI serves `/api/*` and the built React SPA at `/`
  (see [`modules/core/app/README.md`](../modules/core/app/README.md)).
- **`mcp-genesis-workbench`** — the MCP server, a thin adapter exposing capabilities as MCP tools.

### 6. The shared library (`genesis_workbench` wheel)

The heart of the platform, under `modules/core/library/genesis_workbench/src/genesis_workbench/`:

| Module | Responsibility |
|---|---|
| `models.py` | UC model registry helpers: `import_model_from_uc`, `deploy_model_endpoint`, `get_endpoint_name_for_uc_model`, `ModelCategory` |
| `capabilities.py` | Turns deployed models + prebuilt workflows into callable **capabilities** (joins `model_deployments ⋈ models`) |
| `node_catalog.py` | The typed node model — `NodeType`, `Port`, `PortType`, value **shapes** — published to the `node_catalog` table |
| `builtin_nodes.py` | The `CURATED_NODES` definitions published into `node_catalog` |
| `executor.py` | **The single place that runs a capability** — endpoint / databricks_job / endpoint_chain / transform. Used by UI, Vortex, and MCP |
| `adapters.py` | Input/output adapters between capability contracts and endpoint payload shapes |
| `workbench.py` | Settings-table access, job discovery, run helpers |
| `sequence_search.py`, `bionemo.py` | Feature-specific helpers |
| `privilege_management/` | Permission/grant helpers |

---

## The data model (Delta tables in the GWB schema)

Everything the app and executor need at runtime is in a handful of Delta tables in
`{core_catalog}.{core_schema}` — this is why the app has no external runtime dependency.

| Table | Written by | Read by | Purpose |
|---|---|---|---|
| `settings` | module deploy / `initialize_*` | app, executor | Module + app config (job ids, endpoint settings, feature flags) |
| `user_settings` | app Profile page | app | Per-user preferences (e.g. MLflow experiment folder) |
| `master_settings` | admin | app | Admin-only settings |
| `models` | `import_model_from_uc()` | app, capabilities | GWB model registry: display name → UC model + version + `ModelCategory` + active flag |
| `model_deployments` | `deploy_model_endpoint()` | app, capabilities, MCP | **Endpoint registry — source of truth for endpoint names** |
| `batch_models` | batch-workflow registration | app | Metadata for job-backed (non-endpoint) workflows |
| `node_catalog` | `publish_node_catalog()` | executor, Vortex, MCP | Capability contracts: ports, value **shapes** + dtypes for deterministic wiring |

> **Endpoint-name lookups go through `get_endpoint_name_for_uc_model(short_name)` (reads `model_deployments`)** —
> never reconstruct names from `DEV_USER_PREFIX` env vars. The table is the single source of truth; the
> env-var pattern was an architectural mistake that caused a class of 404 bugs (see CHANGELOG `teddy_annotation`).

---

## The three consumers, one executor

```
                         ┌─────────────────────────────┐
   UI (React+FastAPI) ──►│                             │
   Vortex canvas      ──►│   executor.execute_*(...)   │──► Model Serving endpoint
   MCP server         ──►│   (shared wheel)            │──► or Databricks Job
                         └─────────────────────────────┘
                                     ▲
                        node_catalog + model_deployments + models
```

- **UI** — a user clicks a workflow tab; the FastAPI router calls the executor.
- **Vortex** — the AI canvas composes a graph of `node_catalog` nodes; `run_ai_canvas_workflow` runs it
  through the executor. Deterministic wiring uses each port's published value *shape* to derive extraction
  paths (no LLM guessing) — bridging nodes are auto-inserted or the run is rejected at submit.
- **MCP** — `mcp-genesis-workbench` exposes `endpoint_<name>` (synchronous) and `workflow_<name>`
  (dispatch + poll) tools plus `list_capabilities` / `get_workflow_run_status`, all over the same executor.

Because all three share the executor and the same registry tables, **a capability you add once is
immediately reachable from the UI, Vortex, and MCP.**

---

## What `core` stands up

`./deploy.sh core <cloud>` deploys the foundation the modules build on:

- The **two apps** (UI + MCP) and the **`genesis_workbench` wheel**.
- The **Delta tables** above (via `initialize_core`) — **destructive to re-run on a populated install;
  use `update.sh` instead** (see the Engineering Guide → Maintain).
- **Volumes**: `libraries` (the wheel), `model_weights`, `ai_canvas`.
- **Jobs**: `deploy_model`, `grant_app_permissions`, `initialize_core`, `initialize_module`,
  `publish_node_catalog`, `start_all_endpoints`, `destroy_module`, `build_transformer_engine`,
  `run_ai_canvas_workflow`.
- A **secret scope** (catalog/schema/prefix) and an **admin Lakeview dashboard**.

Module deploys then register their models/workflows against this core and grant both app SPs access.

---

## Security posture (summary)

Good: UC governance, per-user token forwarding in the UI (`X-Forwarded-Access-Token`), app SPs with
scoped grants, secret scope for config. Gaps to close before customer data: the **MCP server has no
per-caller authorization**, bundles deploy under the **deploying user's identity** (`run_as: current_user`)
rather than a service principal, and some registry Docker tokens are plaintext DAB variables. Full
remediation plan and acceptance criteria: [`HARDENING_CHECKLIST.md`](../HARDENING_CHECKLIST.md).
