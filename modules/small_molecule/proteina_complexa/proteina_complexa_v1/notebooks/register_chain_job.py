# Databricks notebook source
# MAGIC %md
# MAGIC # Register the generic executor chain runner job
# MAGIC
# MAGIC Records `run_chain_job_id` in the `settings` table and grants the
# MAGIC Genesis Workbench app service principal `CAN_MANAGE_RUN` on the job.
# MAGIC
# MAGIC Without this the app cannot dispatch: `WorkspaceClient().jobs.list(name=...)`
# MAGIC returns empty from the app's context and the dispatcher fails with
# MAGIC "Orchestrator job 'run_chain_gwb' not found".
# MAGIC
# MAGIC The settings row also keeps the grant alive across redeploys —
# MAGIC `core/notebooks/grant_app_permissions.py` iterates every `key LIKE '%_job_id'`
# MAGIC and re-applies the app-SP permission.

# COMMAND ----------

# MAGIC %pip install -q databricks-sdk==0.50.0 databricks-sql-connector==4.0.3 mlflow==2.22.0

# COMMAND ----------

dbutils.widgets.text("catalog", "genesis_workbench", "Catalog")
dbutils.widgets.text("schema", "genesis_workbench", "Schema")
dbutils.widgets.text("run_chain_job_id", "", "Chain Runner Job ID")
dbutils.widgets.text("user_email", "a@b.com", "User email")
dbutils.widgets.text("sql_warehouse_id", "", "SQL Warehouse Id")
dbutils.widgets.text("databricks_app_name", "genesis-workbench", "Databricks App Name")
dbutils.widgets.text(
    "databricks_app_names",
    "genesis-workbench:mcp-genesis-workbench",
    "Databricks App Names (colon/comma-separated, UI + MCP)",
)

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

# COMMAND ----------

gwb_library_path = None
for lib in dbutils.fs.ls(f"/Volumes/{catalog}/{schema}/libraries"):
    if lib.name.startswith("genesis_workbench"):
        gwb_library_path = lib.path.replace("dbfs:", "")
print(f"Genesis Workbench library wheel: {gwb_library_path}")

# COMMAND ----------

# MAGIC # --no-deps: dependencies are already pinned by the pip block above; letting
# MAGIC # --force-reinstall re-resolve them pulls a cryptography that breaks pyOpenSSL.
# MAGIC %pip install {gwb_library_path} --force-reinstall --no-deps
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import os

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
sql_warehouse_id = dbutils.widgets.get("sql_warehouse_id")
user_email = dbutils.widgets.get("user_email")
run_chain_job_id = dbutils.widgets.get("run_chain_job_id")

os.environ["DATABRICKS_APP_NAME"] = dbutils.widgets.get("databricks_app_name")
os.environ["DATABRICKS_APP_NAMES"] = dbutils.widgets.get("databricks_app_names")

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

# Upsert so re-running registration after a redeploy updates the id in place
# rather than accumulating duplicate rows.
spark.sql(
    f"""
MERGE INTO {catalog}.{schema}.settings AS target
USING (SELECT 'run_chain_job_id' AS key,
              '{run_chain_job_id}' AS value,
              'large_molecule' AS module) AS source
ON target.key = source.key
WHEN MATCHED THEN UPDATE SET target.value = source.value, target.module = source.module
WHEN NOT MATCHED THEN INSERT (key, value, module) VALUES (source.key, source.value, source.module)
"""
)
print(f"settings.run_chain_job_id = {run_chain_job_id}")

# COMMAND ----------

from genesis_workbench.workbench import set_app_permissions_for_job

set_app_permissions_for_job(job_id=run_chain_job_id, user_email=user_email)
print("Granted app SP CAN_MANAGE_RUN on the chain runner job.")
