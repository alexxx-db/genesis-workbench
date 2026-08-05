# core module

The foundation every other module builds on. Deploying `core` stands up the UI, the MCP server, the
shared `genesis_workbench` wheel, the settings/registry Delta tables, volumes, jobs, and the admin
dashboard. **Deploy `core` first; destroy it last.**

## What's in here

| Path | What it is |
|---|---|
| [`app/`](app/README.md) | The `genesis-workbench` Databricks App — React SPA + FastAPI backend |
| `mcp_app/` | The `mcp-genesis-workbench` Databricks App — MCP server (thin adapter over the shared executor) |
| `library/genesis_workbench/` | The shared wheel: `models`, `capabilities`, `executor`, `node_catalog`, `adapters`, `workbench`, `privilege_management` (see [ARCHITECTURE](../../docs/ARCHITECTURE.md)) |
| `notebooks/` | Deploy-time + runtime notebooks: `deploy_model`, `grant_app_permissions`, `initialize_core`, `initialize_module`, `publish_node_catalog`, `start_all_endpoints`, `destroy_module`, `run_ai_canvas_workflow` |
| `resources/` | DAB resources: `app.yml`, `mcp_app.yml`, `jobs/`, `volumes/`, `secrets/`, `dashboards/`, `experiments/` |

## Deploy / update

```bash
# First install (from repo root) — creates the settings/registry tables:
./deploy.sh core <aws|azure|gcp>

# Redeploy the UI on a populated install — NEVER re-run deploy.sh core (it drops the tables):
cd modules/core
./update.sh <cloud>            # full: wheel rebuild + bundle deploy + grants + UC volume copy + MCP app
./update.sh <cloud> --ui-only  # fastest: rebuild frontend + redeploy UI app only
```

## The Delta tables core creates

`settings`, `user_settings`, `master_settings`, `models`, `model_deployments`, `batch_models`,
`node_catalog` — the runtime source of truth for the app, executor, Vortex, and MCP. See the
[data model](../../docs/ARCHITECTURE.md#the-data-model-delta-tables-in-the-gwb-schema).

## Notes

- Both apps run as their own service principals; `grant_app_permissions_job` grants **both** access to
  endpoints, jobs, volumes, and models on every module deploy.
- The MCP server has **no per-caller authZ** — control access via the app's accessor list, never share
  with "all users" ([HARDENING_CHECKLIST §2](../../HARDENING_CHECKLIST.md)).

Docs: [Engineering Guide](../../docs/ENGINEERING_GUIDE.md) · [Architecture](../../docs/ARCHITECTURE.md) · [App README](app/README.md)
