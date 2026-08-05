# Genesis Workbench — Operations Runbook

Fast, checklist-style procedures for **demo day** and **incident response**. This complements the
narrative Maintain/Demo sections of the [Engineering Guide](ENGINEERING_GUIDE.md); use that for the "why,"
use this for the "what to do right now."

---

## Demo-day runbook

### T-minus days
- [ ] Confirm the target workspace has **GPU quota** (T4 + A10; multi-GPU on Azure) with the account team.
- [ ] Deploy **only the modules you'll demo** (`./deploy.sh core <cloud>` then the module(s), one at a time).
- [ ] Wait until all cluster-based jobs reach `SUCCEEDED`/`RUNNING` and endpoints reach `READY`
      (`databricks serving-endpoints list | grep gwb_`).
- [ ] Pre-run anything slow/costly (AlphaFold long sequences, Accurate-mode enzyme optimization ~$22 GPU)
      and **save the results** to show — don't run these live.
- [ ] Do a full dry run of the exact click-path you'll demo, on the customer's target(s).

### T-minus 30 minutes
- [ ] **Pre-warm endpoints:** app → Settings → Endpoint Management → **Start All Endpoints**, duration
      covering the whole session (cold starts are 5–20 min for big models).
- [ ] Open `/api/health` and the app home to confirm the app is up.
- [ ] Confirm the demo user/group is on the app's accessor list.

### During
- Lead with fast + visual: ESMFold structure prediction, SCimilarity/TEDDY annotation with UMAP.
- Keep long/expensive runs as pre-baked results.
- For technical audiences: show Vortex (goal → generated pipeline) and the MCP server.

### Teardown (ephemeral workspaces)
- [ ] `./destroy.sh <module> <cloud>` for each module, **core last**.
- [ ] Remember Vector Search indexes + large reference tables (SCimilarity, TEDDY) are **preserved** on
      destroy — remove manually only if you truly want a clean slate.

---

## Incident response

### Triage: where did it fail?

| Symptom | First place to look |
|---|---|
| Deploy/registration job failed | Job run output; traceback usually lands in `load_context()`/`predict()` |
| Endpoint won't start / errors | Serving → `<endpoint>` → **Logs** (container build + invocation) |
| App error / blank page | Databricks App logs for `genesis-workbench` |
| MCP tool call fails | App logs for `mcp-genesis-workbench`; check accessor list + grants |
| Workflow "run not found" / empty Search Past Runs | Check the MLflow run was pre-created; check job `CAN_MANAGE_RUN` grant |

Always cross-check [`CHANGELOG.md`](../CHANGELOG.md) (root-cause decision log) and the
[Troubleshooting skill](../claude_skills/SKILL_GENESIS_WORKBENCH_TROUBLESHOOTING.md) (categorized fixes).

### Common fixes (quick index)

| Problem | Fix |
|---|---|
| Jobs came up `SPOT_WITH_FALLBACK` despite YAML | `databricks jobs get <id>` then `databricks jobs reset --json <spec>` to force `ON_DEMAND` |
| Endpoint 404 / wrong name | Look it up in the `model_deployments` table (`get_endpoint_name_for_uc_model`), not env vars |
| Serving payload schema error | Use `inputs=` / `dataframe_records=[{...}]`, never `dataframe_split=` |
| SCimilarity `Request size cannot exceed 16777216 bytes` | Batch cells ~5 per request |
| `numpy._core.multiarray` crash in `log_model` | Pin `transformers==5.5.0`, do **not** install `accelerate` |
| scGPT dtype error | `self.model.float()` after load, before `.to(device)` |
| App can't write to `/Volumes/...` | Use the SDK Files API (`w.files.upload/download`), not POSIX `open()`; ensure `WRITE VOLUME` grant |
| Redeploy imported stale wheel | Bump `pyproject.toml` version in the wheel |
| `destroy.sh` "rm: .deployed: No such file" | Harmless; scripts use `rm -f` |

### Safe vs. destructive actions

- **Safe:** `./update.sh <cloud> [--ui-only]` (redeploy app), `Start All Endpoints`, `databricks jobs reset`,
  re-running a single register job.
- **Destructive — confirm first:** `./deploy.sh core` on a populated install (**drops the settings/registry
  tables**), `./destroy.sh`, manually deleting script-created resources in the workspace UI (breaks
  build/destroy — always use the scripts).

### Cost incidents
- Endpoints not scaling to zero → check whether a **Start All Endpoints** keep-alive is still running; let
  it expire or stop the job.
- Unexpected GPU spend → registration/optimization jobs on A10/multi-GPU are the usual cause; confirm they
  completed and clusters terminated.

---

## Health-check one-liners

```bash
databricks apps get genesis-workbench            # UI app status + URL
databricks apps get mcp-genesis-workbench        # MCP app status + URL  (server at <url>/mcp)
databricks serving-endpoints list | grep gwb_    # endpoint states
databricks jobs list | grep -i gwb               # job inventory
curl -s <app-url>/api/health                     # UI backend smoke test (no auth required)
```
