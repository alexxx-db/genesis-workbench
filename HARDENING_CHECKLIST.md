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
- **Current:** Every bundle's `run_as` now reads a `run_as_principal` DAB variable (all 29
  `databricks.yml`) instead of a hardcoded `user_name`. Its default is
  `{user_name: ${var.current_user}}` so demo/dev deploys are unchanged, but production can point it at a
  runtime service principal with a single `application.env` line (see [`CONFIGURATION.md`](docs/CONFIGURATION.md)).
  The source half of this check (`hardening_check.py` 1.1) now **passes**; the live half (jobs actually
  running as an SP) still depends on the operational steps below.
- **Target:** A dedicated **deploy SP** owns bundle deploys; jobs `run_as` a **runtime SP**. Human
  deployers only trigger the pipeline.
- **Work (remaining, operational):** Create SP(s) + OAuth (M2M) credentials; set
  `run_as_principal={"service_principal_name":"<sp>"}` in `application.env`; grant the SP the
  catalog/schema/volume/cluster-policy entitlements; update `deploy.sh`/`update.sh` auth to use the SP
  profile.
- **Effort:** M (in-repo parameterization done; SP provisioning + entitlements remain)
- **Acceptance:** Full clean deploy of `core` + one module succeeds under the SP with no human in the
  ownership chain; jobs show the runtime SP as `run_as`.

### 1.2 Parameterize remaining hardcoded/workspace-specific defaults
- **Current (resolved in source):** `permissions_config.py` now derives `DEFAULT_CATALOG` /
  `DEFAULT_SCHEMA` from the environment (`CORE_CATALOG_NAME` / `PERMISSIONS_SCHEMA` /
  `CORE_SCHEMA_NAME`) instead of the former `"genesis_workbench"` / `"permissions"` literals; the
  setup notebook already parameterizes catalog/schema via DAB task widgets. `hardening_check.py` 1.2
  now **passes** (no known workspace-specific literals in source).
- **Target:** All catalog/schema/warehouse/prefix values flow from env files → DAB variables → app
  config; no hardcoded IDs in source.
- **Work:** Done in source. Remaining: confirm on a second-workspace deploy that only env-file changes
  are needed (operational verification).
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
- **Status (in-repo done):** every module's `common_resource_tags` (all 29 `variables.yml`) now declares
  the cost-allocation tags `cost_center` and `project` (defaults `genesis_workbench`; override the whole
  mapping per install via a one-line JSON `common_resource_tags={...}` in `application.env`, same
  mechanism as `run_as_principal`). `hardening_check.py` gained a **source half for 1.3** that fails CI if
  a module drops them, complementing the existing live ON_DEMAND+tags check, and
  `scripts/smoke_test.py` runs the post-deploy assertion. **Remaining:** author actual cluster *policies*
  (the enforcement guardrail) and set customer-real tag values.

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
- **Status (in-repo done):** `genesis_workbench.mcp_authz` + an identity middleware in `mcp_server.py`.
  Identity comes from the Databricks Apps proxy headers (same trust model as the UI's `auth.py`); groups
  resolve via SCIM using the caller's forwarded token when present (which also validates it), TTL-cached;
  policy is the **same `app_permissions` table the UI enforces** — the caller needs a `module_access`
  grant for the capability's module at `MCP_REQUIRED_ACCESS_LEVEL` (default `view`); `genesis-admin-group`
  (override `GWB_ADMIN_GROUP`) and workspace `admins` bypass. Deny raises a tool error naming the missing
  grant; every decision emits a structured `mcp_authz` audit line (denials at WARNING);
  `list_capabilities` annotates per-caller `authorized`. Modes via `MCP_AUTHZ_MODE` in `mcp_app/app.yml`:
  `enforce` (default) / `permissive` (log-only dry-run) / `disabled`. `permissions_config.MODULES` now
  registers `small_molecule`, `genomics`, and `core` so the existing manager/seeding covers every
  capability module. 24 unit tests cover the decision matrix. **Remaining (operational):** run the
  acceptance test on a live install (entitled vs non-entitled caller), and decide the per-group grant
  matrix with the customer. Note: capability-level (finer than module-level) allow-lists remain a
  possible refinement if a customer needs them.

### 2.2 MCP access-control runbook & default posture
- **Current:** Entitlement is a manual `CAN_USE` edit in `resources/mcp_app.yml`; easy to misconfigure to
  "all users."
- **Target:** Documented, reviewed group-grant process; guardrail preventing "all users" sharing.
- **Work:** Write the runbook; add a deploy-time check that fails if the MCP app is shared broadly.
- **Effort:** S
- **Acceptance:** Runbook exists; broad-share check trips in a test.
- **Status (in-repo done):** the runbook is the "Security & access control" section of
  `app/backend/documentation/mcp_server.md` (two-layer model + end-to-end grant procedure), and
  `hardening_check.py` 2.2 asserts no broad principal in the bundle (source) and on the deployed app
  (live). With per-caller authz (2.1) in enforce mode, a broad accessor grant no longer means broad
  *capability* access — but keep the accessor list scoped anyway (defense in depth).

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
- **Status (in-repo done):** `.github/workflows/ci.yml` added. On every push/PR it runs, with no
  workspace needed: the source hardening checks (`scripts/hardening_check.py --source-only`), the wheel
  version guard (`scripts/check_wheel_version.py`, 4.3), a bundle-YAML parse gate over all 135 bundle files
  (`scripts/check_bundle_yaml.py`), a notebook-aware Python syntax gate on the backends + library + scripts
  (`scripts/check_python_syntax.py`), the wheel unit tests, and the React/Vite frontend build. **Remaining
  (operational):** the `bundle-validate` job is present but off by default — enable it per repo (set the
  `ENABLE_BUNDLE_VALIDATE` / `BUNDLE_VALIDATE_TARGET` variables and the `DATABRICKS_*` secrets) to validate
  bundles against `prod_{aws,azure,gcp}`; and replace the syntax/build gate with a style linter (ruff) once
  the tree is clean. See CONTRIBUTING.md → *Continuous integration*.

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
- **Status (partial):** wheel unit tests are now 65 and run in CI. `scripts/smoke_test.py` executes the
  post-deploy half against a live install — recent GWB job runs all SUCCESS, endpoints READY, payload
  capture on with a sample `COUNT(*)` per `_payload` table (the 5.1 acceptance query), apps RUNNING, and
  an opt-in single inference (`--infer <endpoint> --input '<json>'`, opt-in because it can wake a
  scale-to-zero GPU). Exit-coded and `--json`-capable so it can run nightly. **Remaining:** the
  *ephemeral deploy* part (spin up, deploy core + one light module, smoke, tear down) and a wheel
  coverage threshold.

### 4.3 Release/versioning discipline
- **Current:** Wheel version bumps are manual and have caused stale-wheel import bugs (documented); no
  release tagging automation.
- **Target:** Automated version bump + changelog check + tagged releases; CI fails a PR that changes the
  wheel without a version bump.
- **Work:** Add the version-guard check and release tagging to CI.
- **Effort:** S
- **Acceptance:** Un-bumped wheel change fails CI; releases are tagged.
- **Status (in-repo done):** `scripts/check_wheel_version.py` runs in CI and fails the build if the wheel
  filenames pinned in `app/requirements.txt` / `mcp_app/requirements.txt` drift from the library's
  `pyproject.toml` version — i.e. it catches exactly the documented stale-wheel import bug. On pull
  requests, CI additionally runs it with `--require-bump origin/<base>`: if anything under
  `library/.../src/**` differs from the merge-base but the pyproject version does not, the PR fails
  (uncommitted changes count too, so the same command works pre-commit on a dirty tree).
  Tagged releases: `.github/workflows/release.yml` — when a wheel version bump lands on `main`, it
  builds the wheel and publishes a `wheel-vX.Y.Z` tag + GitHub Release with the artifact attached
  (idempotent; `wheel-` prefix so platform release tags like `v2.3.0` stay separate). **Remaining:** a
  changelog-entry gate if desired.

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
- **Status (in-repo done):** `deploy_model_endpoint()` now enables AI Gateway inference tables on every
  endpoint it creates *or* updates — applied via `put_ai_gateway` after the endpoint is up (one code path
  for both) and **best-effort**, so a capture/permissions problem can never fail a deploy that just spent
  hours provisioning a GPU. Capture lands in `<core_catalog>.<core_schema>.<endpoint>_serving_payload`
  (the table `delete_endpoint()` already archives). On by default; opt out per install with
  `enable_inference_tables=false` in `modules/core/module.env` (threaded env → DAB var → job param →
  notebook), or per call via the `enable_inference_tables` argument / `GWB_ENABLE_INFERENCE_TABLES` env
  var. Pre-existing endpoints: `scripts/backfill_inference_tables.py --catalog … --schema …` (dry-run by
  default, `--apply` to act). **Remaining (operational):** run the back-fill on the live install and
  verify capture — `scripts/smoke_test.py --profile <install>` now executes the acceptance directly
  (capture enabled per endpoint + a sample `COUNT(*)` per `_payload` table). Note: no GWB install is
  reachable from the profiles on this dev machine (checked 2026-08-07), so this must run wherever a
  profile for the install exists. Retention/PII handling still needs a customer decision.

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
