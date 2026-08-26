# Databricks notebook source
# MAGIC %md
# MAGIC # Annotate Genesis Workbench tables for Genie
# MAGIC
# MAGIC Genie answers natural-language questions by reading Unity Catalog metadata.
# MAGIC Without table/column comments it guesses from column names alone, which is the
# MAGIC single largest driver of wrong SQL. This notebook is idempotent — re-run it
# MAGIC after a schema change so the Genie spaces stay accurate.
# MAGIC
# MAGIC Run after `initialize_core_job`, and after any module registers new models.

# COMMAND ----------

dbutils.widgets.text("catalog", "genesis_workbench", "Catalog")
dbutils.widgets.text("schema", "genesis_workbench", "Schema")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
fq = f"{catalog}.{schema}"
print(f"Annotating {fq}")

# COMMAND ----------

# (table, table_comment, {column: comment})
ANNOTATIONS = [
    (
        "models",
        "Catalog of every scientific model registered into Genesis Workbench. One row per model "
        "version. This is the authoritative inventory of what the platform can run.",
        {
            "model_name": "Internal model identifier, e.g. scgpt_Get_Embedding.",
            "model_display_name": "Human-readable model name shown in the Genesis Workbench UI.",
            "model_category": "Owning GWB module: single_cell, small_molecule, large_molecule, or genomics.",
            "model_source_version": "Upstream version of the scientific model, e.g. v0.2.4.",
            "model_origin": "Where the model artifact came from, e.g. unity_catalog or huggingface.",
            "model_uc_name": "Fully-qualified Unity Catalog model name.",
            "model_uc_version": "Unity Catalog model version number.",
            "model_added_by": "Email of the user who registered the model.",
            "model_added_date": "Timestamp when the model was registered into Genesis Workbench.",
            "is_model_deployed": "TRUE when the model has at least one live serving endpoint.",
            "is_active": "FALSE means the model was retired; filter to is_active = true for current inventory.",
        },
    ),
    (
        "model_deployments",
        "One row per serving-endpoint deployment of a registered model. Join to models on model_id "
        "to see which model each endpoint serves.",
        {
            "deployment_name": "Name of the deployment as shown in the UI.",
            "model_id": "Foreign key to models.model_id.",
            "model_endpoint_name": "Databricks Model Serving endpoint name, e.g. gwb_alex_scgpt_endpoint.",
            "model_invoke_url": "HTTPS URL used to invoke the endpoint.",
            "model_deployed_by": "Email of the user who deployed the endpoint.",
            "model_deployed_date": "Timestamp when the endpoint was created.",
            "model_deploy_platform": "Serving platform used for this deployment.",
            "is_active": "FALSE means the endpoint was torn down; filter to is_active = true for live endpoints.",
        },
    ),
    (
        "batch_models",
        "Models that run as scheduled batch jobs rather than realtime serving endpoints.",
        {
            "model_category": "Owning GWB module.",
            "module": "GWB module that contributed this batch model.",
            "job_id": "Databricks job id that executes the batch inference.",
            "cluster_type": "Compute profile the batch job requests, e.g. GPU_SMALL.",
        },
    ),
    (
        "node_catalog",
        "Catalog of AI Canvas / Vortex workflow nodes. Each row is a building block users can chain "
        "into a scientific workflow. Read by the workflow executor and the MCP server.",
        {
            "type": "Node type identifier.",
            "category": "Functional grouping of the node.",
            "kind": "Node kind, e.g. model, transform, or io.",
            "module": "GWB module that contributed the node.",
            "source": "Where the node definition came from.",
            "is_active": "FALSE means the node is hidden from the canvas.",
        },
    ),
    (
        "app_permissions",
        "Module- and submodule-level access grants backing the Genesis Workbench permission system. "
        "Controls which groups can see and run each capability.",
        {
            "module_name": "GWB module the grant applies to.",
            "submodule_name": "Specific submodule, or ALL for module-wide grants.",
            "user_type": "admin or user.",
            "access_level": "view (read-only) or full (can run workflows).",
            "groups": "Databricks groups the grant is bound to.",
        },
    ),
    (
        "repurposing_hub",
        "Broad Institute Drug Repurposing Hub: approved and investigational drugs annotated with "
        "mechanism of action, protein target, clinical phase and disease area. Use for questions "
        "about what drugs exist for a target, indication or disease area.",
        {
            "drug_name": "Common name of the drug.",
            "smiles": "SMILES string describing the molecular structure.",
            "moa": "Mechanism of action, e.g. 'EGFR inhibitor'.",
            "target": "Protein target(s) the drug acts on, as gene symbols.",
            "clinical_phase": "Furthest clinical phase reached, e.g. Launched, Phase 3, Preclinical.",
            "disease_area": "Broad therapeutic area, e.g. oncology, neurology.",
            "indication": "Specific condition the drug is indicated for.",
        },
    ),
    (
        "target_binders",
        "ChEMBL-derived bioactivity: small molecules with measured binding affinity against protein "
        "targets. Higher pchembl means stronger binding. Use for potency and structure-activity questions.",
        {
            "gene": "Gene symbol of the protein target.",
            "target_chembl_id": "ChEMBL identifier of the target.",
            "molecule_chembl_id": "ChEMBL identifier of the binding molecule.",
            "binder_smiles": "SMILES string of the binding molecule.",
            "murcko_scaffold": "Bemis-Murcko scaffold — the molecule's core framework, used to group chemical series.",
            "pchembl": "Negative log of binding affinity (pIC50/pKi). Higher is more potent; 6 is roughly 1 micromolar.",
        },
    ),
    (
        "gene_sequences",
        "Reviewed SwissProt human protein sequences ingested from UniProt. One row per protein. "
        "Use for questions about protein length, gene symbols and sequence lookup.",
        {
            "gene": "HGNC gene symbol, e.g. PARP1.",
            "accession": "UniProt accession, e.g. P09874.",
            "entry_name": "UniProt entry name.",
            "protein_name": "Full descriptive protein name.",
            "organism": "Source organism; this table is human (NCBI taxon 9606).",
            "sequence": "Amino-acid sequence in single-letter code.",
            "seq_length": "Number of amino acids in the sequence.",
        },
    ),
    (
        "sequence_db",
        "Large reference protein sequence database backing Genesis Workbench sequence search "
        "(121M+ sequences). Query with filters — it is far too large to scan unfiltered.",
        {
            "seq_id": "Sequence identifier.",
            "sequence": "Amino-acid sequence in single-letter code.",
            "description": "Free-text description of the sequence record.",
            "seq_length": "Number of amino acids in the sequence.",
        },
    ),
    (
        "cellxgene_cell_counts",
        "Per-dataset cell counts for CellxGene single-cell datasets loaded into Genesis Workbench.",
        {
            "dataset_id": "CellxGene dataset identifier.",
            "count": "Number of cells in the dataset.",
        },
    ),
]

# COMMAND ----------

applied, skipped = 0, 0
for table, table_comment, columns in ANNOTATIONS:
    full = f"{fq}.{table}"
    try:
        spark.sql(f"COMMENT ON TABLE {full} IS '{table_comment.replace(chr(39), chr(39)*2)}'")
        applied += 1
    except Exception as e:
        print(f"  skip table {table}: {e}")
        skipped += 1
        continue
    existing = {r.col_name for r in spark.sql(f"DESCRIBE TABLE {full}").collect()}
    for col, comment in columns.items():
        if col not in existing:
            print(f"  skip {table}.{col}: column not present")
            skipped += 1
            continue
        try:
            safe = comment.replace(chr(39), chr(39) * 2)
            spark.sql(f"ALTER TABLE {full} ALTER COLUMN {col} COMMENT '{safe}'")
            applied += 1
        except Exception as e:
            print(f"  skip {table}.{col}: {e}")
            skipped += 1
    print(f"annotated {table}")

print(f"\nDone — {applied} comments applied, {skipped} skipped.")
