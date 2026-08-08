# MCP Server

## Introduction

Genesis Workbench ships a companion **Model Context Protocol (MCP)** server — `mcp-genesis-workbench` — a Databricks App that exposes every deployed model endpoint and prebuilt workflow as MCP tools. Any MCP client (the Databricks AI Playground, Claude, Cursor, or your own agents) can connect, discover the available tools, and call them. The server reuses the same capability core as the Vortex canvas, so an MCP tool call runs exactly the same code path as the UI.

## What It Achieves

- Makes the platform's models and workflows callable by LLM agents and MCP clients, not just the UI.
- Auto-generates one tool per capability from the live registry — no per-tool wiring to maintain.
- Keeps calls governed and attributable: the server runs as its own Databricks App service principal with explicit grants on the endpoints, jobs, volumes, and models it can use.

## How to Use

After deploying `core` (see the Installation Guide), the MCP app is reachable at:

```
https://<mcp-genesis-workbench-app-url>/mcp
```

Add that URL as a custom MCP server in your client:

- **Databricks AI Playground** — custom MCP servers named `mcp-…` are auto-discovered; select it and call its tools.
- **Claude / Cursor / other clients** — register the `/mcp` URL (OAuth) as a streamable-HTTP MCP server.

Typical flow: call **`list_capabilities`** to see what's available and the tool name to use, then:

- **`endpoint_<name>`** — invoke a model-serving endpoint. Runs synchronously and returns predictions.
- **`workflow_<name>`** — dispatch a prebuilt workflow (a Databricks Job or endpoint-chain). Job-backed workflows return a run id + URL; poll **`get_workflow_run_status`** for life-cycle, result, and a link. Chain-backed workflows run synchronously.

### Inputs

- Each tool's arguments are the capability's typed inputs (required) plus its params (optional) — the same inputs/params the Vortex node exposes.

### Outputs

- Endpoints/chains return their prediction/result payload directly.
- Jobs return `{run_id, run_url, …}`; `get_workflow_run_status(run_id)` returns the run's status, result, and link.

## Security & access control

Two layers, deny-by-default at both:

**Layer 1 — who can reach the app** (the accessor list, pinned declaratively in `resources/mcp_app.yml` so it survives redeploys). The **deployer** gets `CAN_MANAGE` and workspace **admins** always retain access (the bundle can't set the admins entry — Databricks manages it). To admit a group, add a `CAN_USE` entry to the `permissions:` block (the group must exist; do **not** use `admins`), then redeploy:

```yaml
- level: CAN_USE
  group_name: <your-entitled-group>
```

**Layer 2 — what each admitted caller may run** (per-caller authorization, `genesis_workbench.mcp_authz`). Tool calls still *execute* as the app service principal (which holds `CAN_QUERY` on endpoints and `CAN_MANAGE_RUN` on jobs), but before executing, every call is authorized against the **caller**:

1. **Identity** comes from the Databricks Apps proxy headers (`X-Forwarded-Email` / `X-Forwarded-Access-Token` — the same SSO-backed trust model as the UI backend's `auth.py`), captured per request by an ASGI middleware.
2. **Groups** are resolved via SCIM — with the caller's own forwarded token when present (which also proves the token is live), else by the app SP looking up the email — and cached (TTL `MCP_AUTHZ_CACHE_TTL`, default 300 s).
3. **Policy** is the same `app_permissions` table the UI enforces: the caller needs an active `module_access` grant for the capability's module (`large_molecule` / `small_molecule` / `single_cell` / `genomics`; module-less capabilities gate as `core`) at `MCP_REQUIRED_ACCESS_LEVEL` (default `view`). Members of `genesis-admin-group` (override: `GWB_ADMIN_GROUP`) or workspace `admins` are always allowed.
4. **Deny raises** a tool error stating the exact missing grant, and **every decision is audit-logged** as a structured `mcp_authz` JSON line in the app logs (denials at WARNING).

The `list_capabilities` tool annotates each capability with `authorized: true|false` for the calling identity, so an agent can plan without burning denied calls. `get_workflow_run_status` stays open to admitted callers.

**Mode knob** (`MCP_AUTHZ_MODE` in `mcp_app/app.yml`): `enforce` (default) denies; `permissive` logs the would-be denial but allows — use it to dry-run a rollout and mine the audit log for missing grants; `disabled` restores the legacy SP-only behavior.

**Granting access end-to-end:** admit the group at layer 1 (accessor list), then grant its modules at layer 2 — `AppPermissionsManager.grant_module_access(module_name="single_cell", groups=["<group>"], access_level="view")` or via the Master Settings UI. The `setup_permissions` task of `initialize_core` seeds `genesis-admin-group` with `full` on every registered module at deploy.

## How It's Implemented

### Architecture

- A **FastMCP** server serving **streamable HTTP** on port 8000, mounted at `/mcp`, hosted as the Databricks App `mcp-genesis-workbench`.
- On startup it initializes the `genesis_workbench` library and **registers one tool per capability** from `list_capabilities()`: `endpoint_<slug>` for serving endpoints and `workflow_<slug>` for runnable jobs/chains, plus the fixed `list_capabilities` and `get_workflow_run_status` tools. Transforms (canvas plumbing) are not exposed.
- Tool handlers call the **shared executor** (`execute_capability` / `run_status`) — the same core that backs the Vortex orchestrator — so endpoint queries and job dispatch behave identically to the UI. Calls run as the app service principal (OBO tokens lack model-serving scope).
- Deployment is wired into the `core` deploy: `update.sh` stages the wheel + app code into `mcp_app/`, deploys the `mcp_genesis_workbench_app` bundle resource, and the `grant_app_permissions_job` grants **both** app service principals (UI + MCP) CAN_QUERY on endpoints, CAN_MANAGE_RUN on jobs, plus volume/model/catalog access.

### Key Files

- `modules/core/mcp_app/backend/mcp_server.py` — the FastMCP server + tool registration + identity middleware
- `modules/core/library/genesis_workbench/src/genesis_workbench/mcp_authz.py` — per-caller authorization (identity, groups, policy, audit)
- `modules/core/mcp_app/app.yml`, `modules/core/mcp_app/requirements.txt` — the Databricks App definition (incl. `MCP_AUTHZ_MODE`)
- `modules/core/mcp_app/scripts/seed_prebuilt_workflows.py` — seeds the prebuilt-workflow capabilities
- `modules/core/library/genesis_workbench/src/genesis_workbench/{capabilities,executor}.py` — shared capability core
- `modules/core/update.sh` — stages + deploys the MCP app and grants its service principal
