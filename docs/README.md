# Genesis Workbench — Documentation Index

Start here to find the right doc fast. If you're an engineer picking up the repo, read the
**[Engineering Guide](ENGINEERING_GUIDE.md)** first — it ties everything below together.

## By goal

| Goal | Doc |
|---|---|
| **Orient myself as an engineer** (use · demo · maintain · extend) | [Engineering Guide](ENGINEERING_GUIDE.md) |
| **Understand how it fits together** — pipeline, data model, executor, 3 consumers | [Architecture](ARCHITECTURE.md) |
| **Understand the product** — modules, models, datasets | [`../README.md`](../README.md) |
| **Learn one module or submodule** | `modules/<module>/README.md` and `modules/<module>/<submodule>/README.md` |
| **Deploy / destroy** — prerequisites, env files, mechanics | [`../Installation.md`](../Installation.md) · [Module deploy/destroy](Module.md) |
| **Look up a config / `.env` field** | [Configuration reference](CONFIGURATION.md) |
| **Guided, interactive deploy** | [Deploy Wizard skill](../claude_skills/SKILL_GENESIS_WORKBENCH_DEPLOY_WIZARD.md) |
| **Guided teardown** | [Destroy Wizard skill](../claude_skills/SKILL_GENESIS_WORKBENCH_DESTROY_WIZARD.md) |
| **Fix an error** | [Troubleshooting skill](../claude_skills/SKILL_GENESIS_WORKBENCH_TROUBLESHOOTING.md) · [`../CHANGELOG.md`](../CHANGELOG.md) |
| **Add a model / workflow / UI tab** | [Development skill](../claude_skills/SKILL_GENESIS_WORKBENCH_DEVELOPMENT.md) |
| **Add a batch (job-backed) workflow** | [Batch Workflow Pattern skill](../claude_skills/SKILL_GENESIS_WORKBENCH_BATCH_WORKFLOW_PATTERN.md) |
| **Contribute** — hard rules, dev loop, PR checklist | [`../CONTRIBUTING.md`](../CONTRIBUTING.md) |
| **Run a demo / handle an incident** | [Operations runbook](OPERATIONS.md) |
| **Learn each UI workflow** | [In-app documentation index](../modules/core/app/backend/documentation/index.md) |
| **Work on the React + FastAPI app** | [App README](../modules/core/app/README.md) |
| **Run a customer workshop** | [Workshop one-pager](WORKSHOP_ONEPAGER.md) (+ Engineering Guide → Demo) |
| **Run the Elanco workshop** | [Elanco workshop runbook](ELANCO_WORKSHOP.md) (facilitator run-of-show + click-path) |
| **Productionize / harden for a customer** | [`../HARDENING_CHECKLIST.md`](../HARDENING_CHECKLIST.md) |
| **Look up a life-sciences term** | [`../GLOSSARY.md`](../GLOSSARY.md) |

## Design & architecture references

- [Capability Registry design](../CAPABILITY_REGISTRY_DESIGN.md) — how endpoints/workflows become
  callable capabilities shared by the UI, Vortex, and MCP.
- [MCP Server app plan](../MCP_SERVER_APP_PLAN.md) — the companion `mcp-genesis-workbench` server.
- [Vortex convertible fields](../VORTEX_CONVERTIBLE_FIELDS.md) — deterministic wiring / value-shape
  resolution in the Vortex canvas.
- [Workflow migration](../WORKFLOW_MIGRATION.md) — workflow model migration notes.

## Assets in this folder

- `ENGINEERING_GUIDE.md` — engineer front door (this folder's headline doc).
- `ARCHITECTURE.md` — how the pieces fit together (pipeline, layers, data model, consumers).
- `CONFIGURATION.md` — every `.env` field (application / cloud / module) in one reference.
- `OPERATIONS.md` — demo-day runbook + incident-response checklists.
- `WORKSHOP_ONEPAGER.md` — customer-facing life-sciences workshop one-pager.
- `ELANCO_WORKSHOP.md` — account-specific facilitator runbook (animal-health narrative, run-of-show, demo click-path, pre-flight).
- `Module.md` — module deploy/destroy anatomy.
- `diagrams/` — Mermaid (`.mmd`) sources for the deploy/destroy and per-module deployment diagrams.
- `images/` — rendered architecture, deploy/destroy, and per-module PNGs used by the READMEs.
- `deployments/` — workspace-specific deployment logs (gitignored; see its README).

## The claude_skills/ folder

The [`claude_skills/`](../claude_skills/) files are authored as Claude Code skills but are fully
human-readable and are the **deepest** how-to references in the repo (deploy, destroy, troubleshoot,
develop, batch-workflow pattern, plus the workflow user guide and platform overview). The Engineering
Guide links to each at the relevant step.
