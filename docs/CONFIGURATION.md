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

```
workspace_url=https://adb-xxxx.azuredatabricks.net
core_catalog_name=genesis_workbench
core_schema_name=genesis
sql_warehouse_id=abcd1234efgh5678
```

---

## `modules/core/module.env` (required)

| Key | Description |
|---|---|
| `dev_user_prefix` | Prefix applied to resources during development (keeps parallel installs from colliding) |
| `app_name` | Name for the Databricks App (default `genesis-workbench`) |
| `secret_scope_name` | A unique secret scope name the app creates and uses |

```
dev_user_prefix=demo
app_name=genesis-workbench
secret_scope_name=genesis_workbench_secret_scope
```

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

See [`ARCHITECTURE.md`](ARCHITECTURE.md#the-data-model-delta-tables-in-the-gwb-schema) for the full data
model.
