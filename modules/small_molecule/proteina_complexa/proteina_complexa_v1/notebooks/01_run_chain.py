# Databricks notebook source
# MAGIC %md
# MAGIC # Executor chain runner — generic batch orchestrator
# MAGIC
# MAGIC Runs the ESMFold(target) → Proteina-Complexa → ESMFold(validate) chain as a
# MAGIC Databricks job instead of inline in the app request.
# MAGIC
# MAGIC **Why this job exists.** Binder design used to run synchronously inside one
# MAGIC HTTP request, streaming progress over SSE. That works while the pipeline stays
# MAGIC under ~10 minutes; past that the browser connection dies with
# MAGIC `TypeError: network error` even though the server-side work completes — the
# MAGIC designs land in MLflow but the user never sees them. Measured on this repo: a
# MAGIC 9.1-minute run succeeded in the UI, a 14.1-minute run with identical parameters
# MAGIC did not.
# MAGIC
# MAGIC The compute here is deliberately a small CPU cluster: every heavy step is a
# MAGIC serving-endpoint call, so this notebook only orchestrates.
# MAGIC
# MAGIC It calls the same `genesis_workbench.executor.run_chain("protein_binder_design")`
# MAGIC the app and the MCP server call, so there is exactly one implementation of the
# MAGIC chain and no drift between the interactive and batch paths.

# COMMAND ----------

# MAGIC %pip install -q databricks-sdk==0.50.0 databricks-sql-connector==4.0.3 mlflow==2.22.0

# COMMAND ----------

dbutils.widgets.text("catalog", "genesis_workbench", "Catalog")
dbutils.widgets.text("schema", "genesis_workbench", "Schema")
dbutils.widgets.text("sql_warehouse_id", "", "SQL Warehouse Id")
dbutils.widgets.text("user_email", "a@b.com", "User Id/Email")

dbutils.widgets.text("mlflow_experiment", "gwb_binder_design", "MLflow experiment tag (short, NOT a path)")
dbutils.widgets.text("mlflow_run_name", "", "MLflow run name")
dbutils.widgets.text("mlflow_run_id", "", "Pre-created MLflow run id (set by dispatcher; empty = create new)")

# Generic across every executor chain: the dispatcher passes the chain name plus
# its inputs/params as JSON, so one job serves protein_binder_design,
# ligand_binder_design, motif_scaffolding, admet_screen and protein_design
# instead of five near-identical orchestrators.
dbutils.widgets.text("chain", "protein_binder_design", "Executor chain name")
dbutils.widgets.text("inputs_json", "{}", "Chain inputs (JSON object)")
dbutils.widgets.text("params_json", "{}", "Chain params (JSON object)")
# Large inputs (a PDB) exceed the job-parameter limit, so the dispatcher stages
# them on a volume and passes {"<key>": {"__volume_path__": "/Volumes/..."}}.

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

# COMMAND ----------

gwb_library_path = None
for lib in dbutils.fs.ls(f"/Volumes/{catalog}/{schema}/libraries"):
    if lib.name.startswith("genesis_workbench"):
        gwb_library_path = lib.path.replace("dbfs:", "")
print(f"Genesis Workbench library wheel: {gwb_library_path}")

# COMMAND ----------

# MAGIC # --no-deps: the pip block above already installs every dependency the wheel
# MAGIC # declares (as floors, not pins). Without it, --force-reinstall re-resolves
# MAGIC # them to latest and pulls a cryptography that breaks pyOpenSSL (GEN_EMAIL).
# MAGIC %pip install {gwb_library_path} --force-reinstall --no-deps
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import json

import mlflow
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
sql_warehouse_id = dbutils.widgets.get("sql_warehouse_id")
user_email = dbutils.widgets.get("user_email")

mlflow_experiment = dbutils.widgets.get("mlflow_experiment")
mlflow_run_name = dbutils.widgets.get("mlflow_run_name")
mlflow_run_id = dbutils.widgets.get("mlflow_run_id") or None

chain = dbutils.widgets.get("chain").strip()
chain_inputs = json.loads(dbutils.widgets.get("inputs_json") or "{}")
chain_params = json.loads(dbutils.widgets.get("params_json") or "{}")

from genesis_workbench.workbench import initialize

databricks_token = (
    dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().getOrElse(None)
)
initialize(
    core_catalog_name=catalog,
    core_schema_name=schema,
    sql_warehouse_id=sql_warehouse_id,
    token=databricks_token,
)

# COMMAND ----------

from genesis_workbench.models import set_mlflow_experiment

mlflow.set_registry_uri("databricks-uc")
mlflow.set_tracking_uri("databricks")

# Pass the SHORT tag, never a full path — set_mlflow_experiment prepends the user
# folder, and re-prepending an already-resolved path yields a doubled path that
# MLflow reports as `BAD_REQUEST: For input string: "None"`.
experiment = set_mlflow_experiment(experiment_tag=mlflow_experiment, user_email=user_email)
print(f"Experiment: {experiment.name} ({experiment.experiment_id})")

def _resolve_volume_refs(d: dict) -> dict:
    """Inline any {"__volume_path__": "..."} placeholder the dispatcher staged."""
    out = {}
    for k, v in d.items():
        if isinstance(v, dict) and "__volume_path__" in v:
            with open(v["__volume_path__"]) as f:
                out[k] = f.read()
            print(f"  inlined {k} from {v['__volume_path__']} ({len(out[k])} chars)")
        else:
            out[k] = v
    return out


chain_inputs = _resolve_volume_refs(chain_inputs)
print(f"Chain: {chain}  inputs={list(chain_inputs)}  params={list(chain_params)}")

# COMMAND ----------

client = mlflow.tracking.MlflowClient()


def _status(status: str) -> None:
    """Advance the progressive job_status tag the Search Past Runs table reads."""
    client.set_tag(mlflow_run_id, "job_status", status)
    print(f"job_status -> {status}")


def _progress(pct: int, msg: str) -> None:
    """run_chain's progress callback. In the job there is no SSE consumer, so
    surface stages as tags + stdout for the run page and the driver log."""
    print(f"[{pct:3d}%] {msg}")
    client.set_tag(mlflow_run_id, "stage", msg[:200])


if not mlflow_run_id:
    # Dispatcher normally pre-creates the run so Search Past Runs shows the job
    # during cluster start-up. Standalone execution still works.
    with mlflow.start_run(run_name=mlflow_run_name, experiment_id=experiment.experiment_id) as r:
        mlflow_run_id = r.info.run_id
    client.set_tag(mlflow_run_id, "origin", "genesis_workbench")
    client.set_tag(mlflow_run_id, "feature", chain)
    client.set_tag(mlflow_run_id, "created_by", user_email)
print(f"MLflow run: {mlflow_run_id}")

# COMMAND ----------

from genesis_workbench.executor import run_chain

# A crashed orchestrator must not leave the run showing "running" forever, so the
# whole body is wrapped: on failure tag job_status=failed + error, then re-raise so
# the Databricks job itself is marked FAILED too.
try:
    _status("started")

    w = WorkspaceClient(config=Config(http_timeout_seconds=600))
    result = run_chain(chain, chain_inputs, chain_params, w, progress=_progress)

    # Chains name their result list differently — binder/ligand use `designs`,
    # motif scaffolding uses `scaffolds`. Count whichever is present; the full
    # result is logged as result.json either way.
    designs = []
    if isinstance(result, dict):
        for key in ("designs", "scaffolds", "molecules", "results"):
            if isinstance(result.get(key), list):
                designs = result[key]
                break
    resolved_target_pdb = result.get("target_pdb") if isinstance(result, dict) else None

    _status("logging")

    with mlflow.start_run(run_id=mlflow_run_id):
        mlflow.log_param("chain", chain)
        for k, v in chain_params.items():
            # Params are scalars by contract; stringify defensively.
            mlflow.log_param(k, v if isinstance(v, (int, float, bool, str)) else str(v)[:250])

        mlflow.log_dict(result if isinstance(result, dict) else {"result": result}, "result.json")
        mlflow.log_metric("num_designs", len(designs))
        # Only chains that fold their outputs report validation; count it when
        # present rather than assuming every chain has the concept.
        validated = sum(
            1 for d in designs if isinstance(d, dict) and d.get("esmfold_validated")
        )
        if any(isinstance(d, dict) and "esmfold_validated" in d for d in designs):
            mlflow.log_metric("num_validated", validated)

        # Artifacts the result dialog reads back: the designs table and each PDB.
        mlflow.log_dict({"designs": designs}, "designs.json")
        if resolved_target_pdb:
            mlflow.log_text(resolved_target_pdb, "target.pdb")
        for i, d in enumerate(designs):
            pdb = d.get("pdb_output") or d.get("esmfold_pdb")
            if pdb:
                mlflow.log_text(pdb, f"designs/design_{i}.pdb")

        mlflow.set_tag("result_location", f"runs:/{mlflow_run_id}/designs.json")

    _status("complete")
    print(f"Done — chain {chain} produced {len(designs)} result(s).")

except Exception as e:
    client.set_tag(mlflow_run_id, "job_status", "failed")
    client.set_tag(mlflow_run_id, "error", str(e)[:500])
    raise

# COMMAND ----------

dbutils.notebook.exit(json.dumps({"mlflow_run_id": mlflow_run_id, "num_designs": len(designs)}))
