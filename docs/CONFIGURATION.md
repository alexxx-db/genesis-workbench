# Genesis Workbench — Configuration Reference

Every configuration value GWB reads, in one place. Configuration is supplied through `.env` files that
`deploy.sh` concatenates into Databricks Asset Bundle variables at deploy time. For the deploy mechanics
that consume these, see [`Installation.md`](../Installation.md); for the big picture, see
[`ARCHITECTURE.md`](ARCHITECTURE.md).

> **Format rules:** one `key=value` per line, **no comments, no blank lines** — `deploy.sh` uses
> `paste -sd,` to fold each file into a single comma-separated string, and comments/blanks corrupt it.
> Values are not quoted.

## File types & precedence

| File | Location | Scope | Committed? |
|---|---|---|---|
| `application.env` | repo root | Application-wide (workspace, catalog, schema, warehouse) | **No — you create it** |
| `<cloud>.env` | repo root | Per-cloud compute (`aws.env` / `azure.env` / `gcp.env`) | Yes (defaults shipped) |
| `module.env` | `modules/<module>/` | Module-specific settings/secrets | **No — you create it** (where required) |
| `module_<cloud>.env` | `modules/<module>/` | Module + cloud specific overrides | Optional |

`deploy.sh` merges them in order **application + cloud + module + module_cloud**, so a later file can
override an earlier key.

---

## `application.env` (repo root — required)

| Key | Description |
|---|---|
| `workspace_url` | The Databricks workspace URL to deploy into |
| `core_catalog_name` | Unity Catalog catalog GWB uses (existing or created at deploy) |
| `core_schema_name` | Schema GWB uses — **must be exclusive to GWB** (created if absent) |
| `sql_warehouse_id` | ID of a SQL Warehouse for the app (a 2X-Small is sufficient) |
| `run_as_principal` | *(optional)* Identity that owns/runs deployed jobs. Defaults to the deploying user. Set to a runtime service principal for production — see note below. |
| `common_resource_tags` | *(optional)* Tags stamped on every job/cluster, incl. the cost-allocation pair `cost_center`/`project` (both default `genesis_workbench`; [`HARDENING_CHECKLIST.md`](../HARDENING_CHECKLIST.md) §1.3). To set your finance codes, override per module in that module's `module.env` as a one-line JSON mapping — e.g. `common_resource_tags={"application":"genesis_workbench","cost_center":"CC-1234","project":"gwb-research","module":"core","created_by":"deployer"}`. (Setting it here in `application.env` also works but applies one identical mapping to *every* module, flattening the per-module `module:` tag.) |

```
workspace_url=https://adb-xxxx.azuredatabricks.net
core_catalog_name=genesis_workbench
core_schema_name=genesis
sql_warehouse_id=abcd1234efgh5678
```

> **`run_as_principal` (production run-as identity).** Every bundle's `run_as` reads the
> `run_as_principal` DAB variable, which defaults to `{user_name: ${var.current_user}}` so
> demo/dev installs run as the deployer with no extra setup. For production, run jobs as a
> dedicated **runtime service principal** so ownership survives off-boarding
> ([`HARDENING_CHECKLIST.md`](../HARDENING_CHECKLIST.md) §1.1) by adding one line — a single-key
> JSON object, no spaces, since it is folded into `--var`:
>
> ```
> run_as_principal={"service_principal_name":"<sp-application-id>"}
> ```
>
> The deploy service principal must be able to act as that runtime SP, and the runtime SP needs the
> catalog/schema/volume/cluster entitlements the jobs use.

---

## `modules/core/module.env` (required)

| Key | Description |
|---|---|
| `dev_user_prefix` | Prefix applied to resources during development (keeps parallel installs from colliding) |
| `app_name` | Name for the Databricks App (default `genesis-workbench`) |
| `secret_scope_name` | A unique secret scope name the app creates and uses |
| `enable_inference_tables` | *(optional, default `true`)* AI Gateway payload capture on every endpoint the deploy-model job creates/updates — see note below. |

```
dev_user_prefix=demo
app_name=genesis-workbench
secret_scope_name=genesis_workbench_secret_scope
```

> **`enable_inference_tables` (AI Gateway inference tables,
> [`HARDENING_CHECKLIST.md`](../HARDENING_CHECKLIST.md) §5.1).** When `true` (the default), every
> serving endpoint deployed through the deploy-model job gets request/response payload capture into
> `<core_catalog>.<core_schema>.<endpoint_name>_serving_payload` — the audit/drift/usage trail, and
> the same table `delete_endpoint()` archives on teardown. Capture is applied best-effort *after*
> the endpoint is up, so a gateway/permissions problem never fails a long GPU deploy (it prints a
> warning instead). Set `enable_inference_tables=false` only while payload retention is under
> review. Endpoints deployed before this existed can be back-filled:
>
> ```
> python scripts/backfill_inference_tables.py --catalog <core_catalog> --schema <core_schema>          # dry-run
> python scripts/backfill_inference_tables.py --catalog <core_catalog> --schema <core_schema> --apply
> ```

---

## `modules/bionemo/module.env` (required only for the optional bionemo module)

| Key | Description |
|---|---|
| `bionemo_docker_userid` | User ID for the BioNeMo image repository |
| `bionemo_docker_token` | Token for the BioNeMo image repository |
| `bionemo_docker_image` | Image tag for the BioNeMo image |

> **Security:** these (and the Parabricks token) are passed as DAB variables and end up visible in job
> definitions. For production, move them to a secret scope and reference `{{secrets/scope/key}}` — see
> [`HARDENING_CHECKLIST.md`](../HARDENING_CHECKLIST.md) §3.

---

## Cloud compute files — `aws.env` / `azure.env` / `gcp.env` (shipped; edit only to change compute)

These map GWB's logical compute names to concrete instance types and Model Serving workload classes.
`gpu_*_setting` values are Model Serving workload types; `*_node_type` values are job-cluster node types.
Defaults are tuned per cloud (e.g. Azure has no `GPU_MEDIUM`, so `gpu_medium_setting=GPU_LARGE`).

| Key | AWS | Azure | GCP |
|---|---|---|---|
| `cpu_node_type` | `i3.4xlarge` | `Standard_F8` | `c3d-highmem-8-lssd` |
| `t4_node_type` | `g4dn.4xlarge` | `Standard_NV36ads_A10_v5` | `g2-standard-32` |
| `a10_node_type` | `g5.16xlarge` | `Standard_NV36ads_A10_v5` | `g2-standard-32` |
| `gpu_small_setting` | `GPU_SMALL` | `GPU_SMALL` | `GPU_MEDIUM` |
| `gpu_medium_setting` | `GPU_MEDIUM` | `GPU_LARGE` | `GPU_MEDIUM` |
| `gpu_large_setting` | `MULTIGPU_MEDIUM` | `GPU_LARGE` | `GPU_MEDIUM` |

All three clouds (`aws`, `azure`, `gcp`) are supported deploy targets (`prod_aws` / `prod_azure` /
`prod_gcp`).

---

## Module compute overrides — `module_<cloud>.env`

Some modules ship `module_aws.env.tmp` / `module_azure.env.tmp` templates (e.g. `single_cell`) that hold
**compute-only** overrides and no secrets. Remove the `.tmp` suffix to activate the standard settings, or
edit the values to change the compute used by that module.

---

## Runtime configuration (not in `.env` files)

Once deployed, additional configuration lives in Delta tables and app settings rather than env files:

- **`settings` table** — module + app config written at deploy/initialize (job ids, endpoint settings).
- **Profile page (per user)** — the MLflow experiment folder name (default `mlflow_experiments`) and
  similar preferences, stored in `user_settings`.
- **App resource bindings** (`app.yml`) — the LLM endpoint (`LLM_ENDPOINT_NAME`), SQL warehouse, secrets,
  and job permissions the app needs at runtime.
- **MCP per-caller authorization** (`mcp_app/app.yml` env, [`HARDENING_CHECKLIST.md`](../HARDENING_CHECKLIST.md) §2.1) —
  `MCP_AUTHZ_MODE` = `enforce` (default) | `permissive` (log-only dry-run) | `disabled`;
  `MCP_REQUIRED_ACCESS_LEVEL` = `view` (default) | `full`; `GWB_ADMIN_GROUP` (default
  `genesis-admin-group`); `MCP_AUTHZ_CACHE_TTL` seconds (default `300`). Entitlements themselves live in
  the `app_permissions` table (managed via `AppPermissionsManager` / Master Settings), the same store the
  UI enforces.

See [`ARCHITECTURE.md`](ARCHITECTURE.md#the-data-model-delta-tables-in-the-gwb-schema) for the full data
model.
