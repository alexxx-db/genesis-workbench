# Databricks notebook source
# MAGIC %md
# MAGIC # Build the unified inference log view
# MAGIC
# MAGIC AI Gateway payload capture writes one table per endpoint
# MAGIC (`<endpoint>_serving_payload`). That is awkward to query and impossible to chart
# MAGIC across models, and the set of tables grows every time a module registers a model.
# MAGIC
# MAGIC This notebook discovers every capture table in the schema and (re)creates
# MAGIC `v_inference_log` — a single view with an `endpoint` column — so dashboards and
# MAGIC Genie can read one stable object. Re-run it after deploying new models.
# MAGIC
# MAGIC It intersects the columns actually present across the capture tables, so a
# MAGIC schema difference between endpoints degrades to fewer columns rather than failing.

# COMMAND ----------

dbutils.widgets.text("catalog", "genesis_workbench", "Catalog")
dbutils.widgets.text("schema", "genesis_workbench", "Schema")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
fq = f"{catalog}.{schema}"

# COMMAND ----------

tables = [
    r.table_name
    for r in spark.sql(f"""
        SELECT table_name
        FROM {catalog}.information_schema.tables
        WHERE table_schema = '{schema}' AND table_name LIKE '%_serving_payload'
        ORDER BY table_name
    """).collect()
]
print(f"Found {len(tables)} payload tables")

if not tables:
    dbutils.notebook.exit("no capture tables yet — nothing to do")

# COMMAND ----------

# AI Gateway only materialises the full schema on an endpoint's first captured
# request, so tables for endpoints that have never been called may carry just a
# placeholder column. Use the intersection of what is actually there.
cols_per_table = {}
for t in tables:
    cols = {
        r.column_name
        for r in spark.sql(f"""
            SELECT column_name FROM {catalog}.information_schema.columns
            WHERE table_schema = '{schema}' AND table_name = '{t}'
        """).collect()
    }
    cols_per_table[t] = cols

# Column names as AI Gateway actually writes them (verified against a live capture
# table): request_time is a TIMESTAMP, not epoch millis, and the duration column is
# execution_duration_ms.
PREFERRED = [
    "databricks_request_id", "client_request_id", "request_date", "request_time",
    "status_code", "execution_duration_ms", "sampling_fraction",
    "request", "response", "served_entity_id", "requester",
]

# Only endpoints that have actually been called carry the real schema; ignore the rest
# so one un-called endpoint cannot collapse the view down to a single column.
usable = {t: c for t, c in cols_per_table.items() if len(c) > 1}
print(f"{len(usable)} of {len(tables)} tables have captured requests")
if not usable:
    dbutils.notebook.exit("capture tables exist but none have data yet — re-run after traffic")

common = set.intersection(*usable.values())
selected = [c for c in PREFERRED if c in common]
print(f"Common columns: {selected}")

# COMMAND ----------

def endpoint_of(table_name: str) -> str:
    return table_name[: -len("_serving_payload")]

parts = []
for t in sorted(usable):
    cols = ", ".join(f"`{c}`" for c in selected)
    parts.append(
        f"SELECT '{endpoint_of(t)}' AS endpoint, {cols} FROM {fq}.`{t}`"
    )

view_sql = f"CREATE OR REPLACE VIEW {fq}.v_inference_log AS\n" + "\nUNION ALL\n".join(parts)
spark.sql(view_sql)
print(f"Created {fq}.v_inference_log over {len(parts)} endpoints")

spark.sql(f"""
COMMENT ON VIEW {fq}.v_inference_log IS
'Unified AI Gateway inference log across every Genesis Workbench serving endpoint.
One row per model request, with an endpoint column identifying which model served it.
Rebuilt by build_inference_log_view; re-run after deploying new models.'
""")

# COMMAND ----------

display(spark.sql(f"""
    SELECT endpoint, count(*) AS requests
    FROM {fq}.v_inference_log
    GROUP BY endpoint ORDER BY requests DESC
"""))
