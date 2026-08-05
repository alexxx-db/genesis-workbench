# Genesis Workbench — Productionization Hardening Checklist

A hardening checklist structured as SOW workstreams. Each item lists current state (from a code
review of this repo), target state, the work involved, a T-shirt effort estimate, and acceptance
criteria you can lift directly into deliverables. It covers the five core areas (deploy Service
Principal, MCP authorization, secrets, CI, AI Gateway inference tables) plus three adjacent areas a
life-sciences customer's security review will almost certainly raise.

**Scope note.** Genesis Workbench (GWB) is an open-source solution accelerator. This checklist converts
it from a demo-grade reference architecture into a customer-ownable, governed platform. It assumes
deployment into the customer's own Databricks workspace(s) with their Unity Catalog and identity
provider. Effort sizes are relative: **S** ≈ ≤2 days, **M** ≈ 3–5 days, **L** ≈ 1–2 weeks of one
engineer.

---

## Running the checks

The mechanically decidable acceptance criteria below are executed by
`scripts/hardening_check.py`. Run it against the source tree, or against a live
deployment to catch drift between what the bundles declare and what the workspace
actually has:

```bash
python scripts/hardening_check.py --source-only          # no credentials needed
python scripts/hardening_check.py --profile <cli-profile>  # + live workspace checks
python scripts/hardening_check.py --json                 # machine-readable, for CI
```

Covered today: **1.1** (run_as service principal — source and live), **1.2** (no
hardcoded workspace-specific defaults), **1.3** (job clusters ON_DEMAND and
cost-tagged), **2.2** (MCP app not shared broadly — source and live), **3.1** (no
plaintext credentials in job definitions). Exit code is 1 if any check fails.

A fresh demo-grade install is *expected* to fail several of these. That report is the
useful artifact: it is evidence of the gap rather than an assertion about it. Set
`REQUIRED_TAGS` in the script to the customer's tagging standard before relying on 1.3.

---

## Workstream 1 — Deploy identity & IaC (Service Principal)

### 1.1 Replace deployer identity with a dedicated deploy Service Principal
- **Current:** Bundles run as `run_as: user_name: ${var.current_user}` — resources are owned by, and
  jobs run as, whoever ran `deploy.sh`. Off-boarding that person or rotating them breaks ownership.
- **Target:** A dedicated **deploy SP** owns bundle deploys; jobs `run_as` a **runtime SP**. Human
  deployers only trigger the pipeline.
- **Work:** Create SP(s) + OAuth (M2M) credentials; set `run_as` in every module `databricks.yml`; grant
  the SP the catalog/schema/volume/cluster-policy entitlements; update `deploy.sh`/`update.sh` auth to
  use the SP profile.
- **Effort:** M
- **Acceptance:** Full clean deploy of `core` + one module succeeds under the SP with no human in the
  ownership chain; jobs show the runtime SP as `run_as`.

### 1.2 Parameterize remaining hardcoded/workspace-specific defaults
- **Current:** `permissions_config.py` has `DEFAULT_CATALOG = "genesis_workbench"` and `DEFAULT_SCHEMA`
  with `# TODO: parameterize from DAB`; a grant notebook carries a workspace-specific default
  `sql_warehouse_id`.
- **Target:** All catalog/schema/warehouse/prefix values flow from env files → DAB variables → app
  config; no hardcoded IDs in source.
- **Work:** Thread the values through `variables.yml` and app env bindings; remove literal defaults.
- **Effort:** S
- **Acceptance:** Grep for known literals returns none; deploy to a second workspace with only env-file
  changes.

### 1.3 Cluster policies & tagging enforcement
- **Current:** GPU node types come from env files; on-demand is set per target, but there's no policy
  guardrail, and the changelog documents DAB occasionally creating jobs as `SPOT_WITH_FALLBACK` despite
  YAML.
- **Target:** Cluster policies constrain node types/DBR/spot, and enforce cost-allocation tags on every
  job and endpoint.
- **Work:** Author policies; reference them in bundles; add a post-deploy assertion that all
  cluster-based jobs are `ON_DEMAND` and tagged.
- **Effort:** M
- **Acceptance:** Post-deploy check passes for 100% of jobs; policy blocks a non-conforming cluster.

---

## Workstream 2 — MCP server authorization

### 2.1 Per-caller authorization on the MCP server
- **Current:** The MCP app runs every capability as the app SP with **no per-user authZ** — anyone who
  can open the app can invoke anything the SP is entitled to. The only control is the app's accessor
  list (deny-by-default, pinned to the deployer).
- **Target:** MCP calls are authorized against the *calling* identity (OAuth token forwarded like the
  UI's `X-Forwarded-Access-Token`), with capability-level entitlement checks.
- **Work:** Forward and validate the caller token in `mcp_app`; map identity → allowed capabilities
  (group-based); enforce on `execute_capability`; deny + audit on failure. Decide the authorization
  model with the customer (per-group capability allow-lists).
- **Effort:** L
- **Acceptance:** A user without entitlement to endpoint X is denied when calling `endpoint_X` via MCP
  but the entitled user succeeds; every call is attributable to the human, not just the SP.

### 2.2 MCP access-control runbook & default posture
- **Current:** Entitlement is a manual `CAN_USE` edit in `resources/mcp_app.yml`; easy to misconfigure to
  "all users."
- **Target:** Documented, reviewed group-grant process; guardrail preventing "all users" sharing.
- **Work:** Write the runbook; add a deploy-time check that fails if the MCP app is shared broadly.
- **Effort:** S
- **Acceptance:** Runbook exists; broad-share check trips in a test.

---

## Workstream 3 — Secrets & credential management

### 3.1 Move container-registry tokens into secret scopes
- **Current:** `bionemo_docker_token` and `parabricks_docker_token` are passed as **plaintext DAB
  variables**, visible in job definitions via API (explicitly flagged "not yet fixed" in the changelog).
- **Target:** All registry credentials in a Databricks secret scope, referenced as
  `{{secrets/scope/key}}`; nothing sensitive in job/bundle definitions.
- **Work:** Provision scope entries; rewrite BioNeMo/Parabricks bundle refs; scrub any prior plaintext
  from deployed job configs.
- **Effort:** S–M
- **Acceptance:** API dump of job definitions contains no plaintext tokens; container builds still
  succeed.

### 3.2 Secret-scope audit & rotation policy
- **Current:** `core` creates a secret scope for catalog/schema/prefix; no documented rotation or
  backing-KMS choice.
- **Target:** Secrets backed by the customer's KMS where required; documented ownership + rotation
  cadence; least-privilege ACLs on the scope.
- **Work:** Inventory all secrets; define rotation; set scope ACLs to the runtime SP + admins only.
- **Effort:** S
- **Acceptance:** Secret inventory + rotation doc signed off; scope ACLs least-privilege.

### 3.3 App auth-mode review (PAT-style token usage)
- **Current:** The UI backend builds a `WorkspaceClient(token=..., auth_type="pat")` from the forwarded
  user token.
- **Target:** Confirm this matches the customer's approved Databricks Apps auth pattern; document token
  lifetime/scope.
- **Work:** Security review + doc; adjust if the customer mandates OBO/OAuth specifics.
- **Effort:** S
- **Acceptance:** Customer security sign-off on the app auth flow.

---

## Workstream 4 — CI/CD & automated testing

### 4.1 Continuous integration pipeline
- **Current:** No `.github/workflows` (or equivalent); quality control is manual "verified on ci-demo"
  notes in the changelog.
- **Target:** CI on every PR: lint, wheel unit tests, `databricks bundle validate` for all modules across
  all cloud targets, and Python type/build checks.
- **Work:** Author the pipeline (GitHub Actions / Azure DevOps to match the customer); wire
  `bundle validate --target prod_{aws,azure,gcp}`; gate merges.
- **Effort:** M
- **Acceptance:** PR that breaks a bundle or a unit test is blocked by CI.

### 4.2 Expand automated test coverage
- **Current:** Only ~5 wheel unit tests (capabilities/executor). No integration/smoke tests for
  registration, serving, or app routes.
- **Target:** Unit coverage on the shared library (capability/executor/models helpers); a
  **smoke-deploy** integration test that deploys `core` + one light module to an ephemeral workspace and
  asserts endpoint READY + one successful inference.
- **Work:** Add unit tests; build the ephemeral smoke-deploy harness (can reuse the MCP test harness
  pattern already in `mcp_app/scripts/test_mcp_server.py`).
- **Effort:** L
- **Acceptance:** Coverage threshold met on the wheel; nightly smoke-deploy passes end-to-end.

### 4.3 Release/versioning discipline
- **Current:** Wheel version bumps are manual and have caused stale-wheel import bugs (documented); no
  release tagging automation.
- **Target:** Automated version bump + changelog check + tagged releases; CI fails a PR that changes the
  wheel without a version bump.
- **Work:** Add the version-guard check and release tagging to CI.
- **Effort:** S
- **Acceptance:** Un-bumped wheel change fails CI; releases are tagged.

---

## Workstream 5 — Observability & model monitoring (AI Gateway inference tables)

### 5.1 Enable AI Gateway inference tables on serving endpoints
- **Current:** `models.py` has `AiGatewayConfig` / `AiGatewayInferenceTableConfig` imported but
  **commented out**; endpoints capture no request/response tables.
- **Target:** Every serving endpoint logs inference tables to UC (payload capture) for audit, drift, and
  usage analytics — enabled at deploy for new endpoints and back-filled on existing ones.
- **Work:** Uncomment/parameterize the AI Gateway config in `deploy_model_endpoint()`; back-fill existing
  endpoints via `put_ai_gateway`; decide table naming + retention with the customer.
- **Effort:** M
- **Acceptance:** Each endpoint has a populated inference table; a sample query shows captured requests.

### 5.2 Operational dashboards & alerting
- **Current:** Settings page shows endpoint status; no proactive monitoring, cost, or failure alerting.
- **Target:** Lakeview/SQL dashboards for endpoint usage, job success/failure, and GPU spend; alerts on
  job failures and cost thresholds.
- **Work:** Build dashboards over inference/system tables; configure alerts.
- **Effort:** M
- **Acceptance:** Dashboard live; a forced job failure triggers an alert.

---

## Workstream 6 — Cost governance (adjacent, high-priority for LS GPU spend)

### 6.1 GPU cost guardrails
- **Current:** Scale-to-zero is on, but "Start All Endpoints" keep-alive deliberately overrides it, and
  registration jobs run for hours on A10/multi-GPU. No budget/guardrail layer.
- **Target:** Budget policies + tag-based chargeback; keep-alive gated behind entitlement + auto-expiry;
  documented per-module cost profile.
- **Work:** Define budgets/alerts; restrict keep-alive; produce a cost-per-workflow reference from system
  billing tables.
- **Effort:** M
- **Acceptance:** Chargeback report by team/module; keep-alive requires entitlement and expires.

---

## Workstream 7 — Data governance, privacy & compliance (adjacent, LS-specific)

### 7.1 PHI/PII posture for genomics & single-cell data
- **Current:** Ships open/public reference data only; no assumptions about customer data classification.
  Genomics + single-cell inputs can be sensitive/regulated.
- **Target:** Documented data-classification model; UC-enforced access controls, row/column masking where
  needed; clarity that GWB is **research-use, not GxP/clinical**.
- **Work:** Data-flow/classification review; apply UC governance (tags, masking, catalog isolation);
  document the compliance boundary.
- **Effort:** M–L (depends on customer data)
- **Acceptance:** Data-classification doc + UC controls reviewed by customer governance.

### 7.2 Audit & lineage validation
- **Current:** UC + MLflow provide lineage inherently; audit-log review not packaged.
- **Target:** Verified end-to-end lineage (input volume → job → model → endpoint → result) and audit-log
  coverage for capability invocations.
- **Work:** Validate lineage graph; enable/route system audit logs; add capability-invocation audit (ties
  to 2.1).
- **Effort:** S–M
- **Acceptance:** A run is fully traceable from input to output in UC lineage + audit logs.

---

## Workstream 8 — Network & workspace isolation (adjacent)

### 8.1 Private networking / egress control
- **Current:** Deploy assumes standard workspace networking; several jobs pull model weights from public
  sources (HuggingFace, NGC, Zenodo, EBI) at registration time.
- **Target:** Documented egress allow-list (or pre-staged weights in UC volumes) so a locked-down/
  private-link workspace can deploy without ad-hoc internet access.
- **Work:** Enumerate all external fetches; provide a pre-stage script to land weights in UC volumes;
  document required egress endpoints.
- **Effort:** M
- **Acceptance:** Clean deploy in a restricted-egress workspace using pre-staged weights.

---

## Suggested phasing for the SOW

- **Phase 1 — Security baseline (must-have before any customer data):** 1.1, 2.1, 2.2, 3.1, 3.2, 7.1.
  *≈3–4 weeks.*
- **Phase 2 — Reliability & ownership:** 1.2, 1.3, 4.1, 4.2, 4.3, 8.1. *≈3–4 weeks.*
- **Phase 3 — Observability & cost:** 5.1, 5.2, 6.1, 7.2, 3.3. *≈2–3 weeks.*

Rough total: **8–11 weeks** for one senior Databricks/ML engineer, compressible with two. The Phase 1
items are the ones a life-sciences customer's security review will block on, so they anchor the minimum
viable productionization.
