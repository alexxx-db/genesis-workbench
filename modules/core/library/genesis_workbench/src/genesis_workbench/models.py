import os
import mlflow
import time
import numpy as np
from mlflow import MlflowClient
from mlflow.exceptions import RestException
from mlflow.pyfunc import PythonModel
from mlflow.models.model import ModelInfo
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from enum import StrEnum, auto
from datetime import datetime, timedelta
from typing import Union, List
import pandas as pd
import numpy as np
from databricks.sdk import WorkspaceClient
from databricks.sdk import errors
from databricks.sdk.service.serving import (
        EndpointCoreConfigInput,
        ServedEntityInput,
        AutoCaptureConfigInput,
        ServingEndpointDetailed,
        ServingModelWorkloadType,
        EndpointTag,
        AiGatewayConfig,
        AiGatewayInferenceTableConfig,
    )

from .workbench import (UserInfo, 
                        AppContext,
                        get_user_settings,
                         execute_select_query, 
                         execute_non_select_query,
                         execute_parameterized_inserts,
                         execute_workflow,
                         validate_sql_name)
from .adapters import BaseAdapter, GWBModel


class ModelSource(StrEnum):
    UNITY_CATALOG = auto()
    PYPI = auto()
    HUGGINGFACE = auto()

class ModelCategory(StrEnum):
    SINGLE_CELL = auto()
    LARGE_MOLECULE = auto()
    SMALL_MOLECULE = auto()
    GENOMICS = auto()

class ModelDeployPlatform(StrEnum):
    MODEL_SERVING = auto()
    EXTERNAL = auto()

class MLflowExperimentAccessException(Exception):
    """
    A custom exception for access issues to MLflow.
    """
    def __init__(self, message="Error accessing MLflow folder"):
        self.message = message
        super().__init__(self.message)

@dataclass
class GWBModelInfo:
    """Class that contains info about available models"""    
    model_id:int
    model_name : str
    model_display_name : str
    model_source_version : str
    model_origin : ModelSource 
    model_description_url : str #website to find more details about model
    model_uc_name : str
    model_uc_version : int
    model_owner : str
    model_category : ModelCategory
    model_input_schema : str
    model_output_schema : str
    model_params_schema : str
    model_added_by : str #id of user
    model_added_date : datetime
    is_model_deployed : bool
    deployment_ids: str
    is_active: bool 
    deactivated_timestamp : datetime

@dataclass
class ModelDeploymentInfo:
    """Class that contains information on model deployments"""
    deployment_id:int
    deployment_name: str
    deployment_description: str
    model_id:int
    input_adapter:str
    output_adapter:str 
    is_adapter:bool
    deploy_model_uc_name: str
    deploy_model_uc_version: str
    model_deployed_date : datetime
    model_deployed_by : str
    model_deploy_platform : ModelDeployPlatform
    model_endpoint_name: str    
    model_invoke_url : str
    is_active: bool
    deactivated_timestamp : datetime

def set_mlflow_experiment(experiment_tag, user_email, host=None, token=None, shared=False):
    """Route MLflow experiments to one of two base paths:

    - shared=True  -> /Shared/dbx_genesis_workbench_models/<experiment_tag>
      Used by deploy-time module registration jobs (register_boltz, register_esmfold, etc.)
      to log system-level model artifacts. These runs are created once at deploy time.

    - shared=False -> /Users/<user_email>/<mlflow_experiment_folder>/<experiment_tag>
      Used by the app UI when users run workflows (protein folding, single cell analysis,
      bionemo fine-tuning). The folder name (default "mlflow_experiments") is configured
      in the app's Profile page and stored in user_settings.
    """

    user_settings = get_user_settings(user_email=user_email)

    if host and not host.startswith("https://"):
        host = f"https://{host}"

    w = WorkspaceClient() if not token else WorkspaceClient(host=host, token=token, auth_type="pat")

    mlflow_experiment_base_path = ""

    if shared:
        mlflow_experiment_base_path = "Shared/dbx_genesis_workbench_models"
    else:
        mlflow_experiment_base_path = f"Users/{user_email}/{user_settings['mlflow_experiment_folder']}"
    
    try:
        w.workspace.mkdirs(f"/Workspace/{mlflow_experiment_base_path}")
        experiment_path = f"/{mlflow_experiment_base_path}/{experiment_tag}"
        mlflow.set_registry_uri("databricks-uc")
        mlflow.set_tracking_uri("databricks")
        experiment = mlflow.set_experiment(experiment_path)

        mlflow.set_experiment_tags({
            "used_by_genesis_workbench":"yes"
        })
        
        return experiment
    except RestException as e:
        if e.error_code=="RESOURCE_DOES_NOT_EXIST":
            raise MLflowExperimentAccessException("Error accessing the experiment location")
        else:
            raise e

def get_latest_model_version(model_name):
    client = MlflowClient()
    model_version_infos = client.search_model_versions("name = '%s'" % model_name)
    return max([int(model_version_info.version) for model_version_info in model_version_infos])

def get_available_models(model_category : ModelCategory) -> pd.DataFrame:
    
    """Gets all models that are available for deployment"""
    query = f"SELECT \
                model_id, model_name, model_display_name, model_source_version, model_uc_name, model_uc_version \
            FROM \
                {os.environ['CORE_CATALOG_NAME']}.{os.environ['CORE_SCHEMA_NAME']}.models \
            WHERE \
                model_category = :model_category AND is_active=true \
            ORDER BY model_id DESC "
    
    result_df = execute_select_query(query, parameters={"model_category": str(model_category)})
    return result_df

# Per-process cache for endpoint-name lookups. App restarts on each deploy, so
# stale cache entries auto-invalidate then; we don't expire mid-process.
_ENDPOINT_NAME_CACHE: dict[str, str] = {}


def get_endpoint_name_for_uc_model(short_name: str) -> str:
    """Look up the active serving endpoint name for a model by its short name.

    Single source of truth: the `model_deployments` table populated by
    `deploy_model_endpoint()` at deploy time. Avoids the brittle pattern of
    constructing endpoint names client-side from `gwb_{DEV_USER_PREFIX}_{short}_endpoint`
    which silently 404s whenever the env var isn't plumbed through the deploy
    chain correctly (see feedback_apps_volume_filesapi.md for the TEDDY
    annotation incident that motivated this).

    `short_name` matches the last segment of `model_uc_name` (e.g., "teddy",
    "scimilarity_get_embedding", "chemprop_admet"). Lookup is case-sensitive.

    Returns the endpoint name as stored in the deployments table (e.g.,
    "gwb_demo_teddy_endpoint"). Raises RuntimeError if no active deployment
    is found — fail loud so missing-model bugs surface immediately instead
    of silent 404s on every prediction.

    Cached per-process; not invalidated mid-session (app restarts re-deploy).
    """
    if short_name in _ENDPOINT_NAME_CACHE:
        return _ENDPOINT_NAME_CACHE[short_name]

    catalog = os.environ.get("CORE_CATALOG_NAME")
    schema = os.environ.get("CORE_SCHEMA_NAME")
    if not catalog or not schema:
        raise RuntimeError(
            f"CORE_CATALOG_NAME / CORE_SCHEMA_NAME env vars must be set to look "
            f"up endpoint for '{short_name}' from the deployments table."
        )

    # `model_uc_name LIKE '%.<short>'` matches the typical
    # <catalog>.<schema>.<short> pattern. Exact equality covers cases where
    # callers happen to pass the full UC path.
    query = (
        f"SELECT model_endpoint_name "
        f"FROM {catalog}.{schema}.model_deployments md "
        f"INNER JOIN {catalog}.{schema}.models m ON md.model_id = m.model_id "
        f"WHERE (m.model_uc_name = :short_name OR m.model_uc_name LIKE :short_like) "
        f"AND md.is_active = true "
        f"ORDER BY md.deployment_id DESC LIMIT 1"
    )
    df = execute_select_query(
        query, parameters={"short_name": short_name, "short_like": f"%.{short_name}"}
    )
    if df.empty:
        raise RuntimeError(
            f"No active deployment found for model '{short_name}' in "
            f"{catalog}.{schema}.model_deployments. Has the registration job run?"
        )
    endpoint_name = str(df.iloc[0]["model_endpoint_name"])
    _ENDPOINT_NAME_CACHE[short_name] = endpoint_name
    return endpoint_name


def get_deployed_models(model_category : ModelCategory)-> pd.DataFrame:
    """Gets all models that are available for deployment"""
    
    query = f"SELECT models.model_id as model_id, deployment_id, deployment_name, deployment_description, model_display_name, model_source_version, \
                concat(model_uc_name,'/',model_uc_version) as uc_name , model_endpoint_name \
            FROM \
                {os.environ['CORE_CATALOG_NAME']}.{os.environ['CORE_SCHEMA_NAME']}.model_deployments \
            INNER JOIN {os.environ['CORE_CATALOG_NAME']}.{os.environ['CORE_SCHEMA_NAME']}.models ON \
                models.model_id = model_deployments.model_id \
            WHERE \
                model_category = :model_category and model_deployments.is_active=true \
            ORDER BY deployment_id DESC "
    
    result_df = execute_select_query(query, parameters={"model_category": str(model_category)})
    return result_df

def get_batch_models(model_category: str) -> pd.DataFrame:
    """Gets all active batch models for a given category."""
    query = (
        f"SELECT model_display_name, model_description, job_name, cluster_type "
        f"FROM {os.environ['CORE_CATALOG_NAME']}.{os.environ['CORE_SCHEMA_NAME']}.batch_models "
        f"WHERE model_category = :model_category AND is_active = true "
        f"ORDER BY model_display_name"
    )
    return execute_select_query(query, parameters={"model_category": model_category})


def _sql_val(val):
    """Format a Python value as a SQL literal, escaping single quotes and handling None."""
    if val is None:
        return 'NULL'
    s = str(val).replace("'", "''")
    return f"'{s}'"


def upsert_model_info(model_info: GWBModelInfo):
    """Register or update the model in GWB using MERGE INTO keyed on model_uc_name."""
    catalog = os.environ['CORE_CATALOG_NAME']
    schema = os.environ['CORE_SCHEMA_NAME']
    mi = model_info

    query = f"""
        MERGE INTO {catalog}.{schema}.models AS target
        USING (SELECT {_sql_val(mi.model_uc_name)} AS model_uc_name) AS source
        ON target.model_uc_name = source.model_uc_name
        WHEN MATCHED THEN UPDATE SET
            target.model_name = {_sql_val(mi.model_name)},
            target.model_display_name = {_sql_val(mi.model_display_name)},
            target.model_source_version = {_sql_val(mi.model_source_version)},
            target.model_origin = {_sql_val(mi.model_origin)},
            target.model_description_url = {_sql_val(mi.model_description_url)},
            target.model_category = {_sql_val(mi.model_category)},
            target.model_uc_version = {_sql_val(mi.model_uc_version)},
            target.model_owner = {_sql_val(mi.model_owner)},
            target.model_added_by = {_sql_val(mi.model_added_by)},
            target.model_added_date = {_sql_val(mi.model_added_date)},
            target.model_input_schema = {_sql_val(mi.model_input_schema)},
            target.model_output_schema = {_sql_val(mi.model_output_schema)},
            target.model_params_schema = {_sql_val(mi.model_params_schema)},
            target.is_active = true,
            target.deactivated_timestamp = NULL
        WHEN NOT MATCHED THEN INSERT
            (model_id, model_name, model_display_name, model_source_version,
             model_origin, model_description_url, model_category, model_uc_name,
             model_uc_version, model_owner, model_added_by, model_added_date,
             model_input_schema, model_output_schema, model_params_schema,
             is_model_deployed, deployment_ids, is_active, deactivated_timestamp)
        VALUES
            ({mi.model_id}, {_sql_val(mi.model_name)}, {_sql_val(mi.model_display_name)},
             {_sql_val(mi.model_source_version)}, {_sql_val(mi.model_origin)},
             {_sql_val(mi.model_description_url)}, {_sql_val(mi.model_category)},
             {_sql_val(mi.model_uc_name)}, {_sql_val(mi.model_uc_version)},
             {_sql_val(mi.model_owner)}, {_sql_val(mi.model_added_by)},
             {_sql_val(mi.model_added_date)}, {_sql_val(mi.model_input_schema)},
             {_sql_val(mi.model_output_schema)}, {_sql_val(mi.model_params_schema)},
             {mi.is_model_deployed}, {_sql_val(mi.deployment_ids)},
             {mi.is_active}, {_sql_val(mi.deactivated_timestamp)})
    """
    execute_non_select_query(query)


def register_batch_model(model_name: str, model_display_name: str, model_description: str,
                         model_category: str, module: str, job_id: str, job_name: str,
                         cluster_type: str, added_by: str):
    """Register or update a batch (non-realtime) model in the batch_models table."""
    catalog = os.environ['CORE_CATALOG_NAME']
    schema = os.environ['CORE_SCHEMA_NAME']
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    batch_model_id = time.time_ns()

    # Upsert keyed on model_name alone (globally unique across modules). Keying on
    # (model_name, module) would leave a stale active row behind if a model's module
    # is ever renamed; keying on model_name updates module in place instead. Values
    # are bound as parameters (never f-string-interpolated) so a description
    # containing an apostrophe — e.g. "Merck's model" — can't break or inject SQL.
    query = f"""
        MERGE INTO {catalog}.{schema}.batch_models AS target
        USING (SELECT :model_name AS model_name) AS source
        ON target.model_name = source.model_name
        WHEN MATCHED THEN UPDATE SET
            target.model_display_name = :model_display_name,
            target.model_description = :model_description,
            target.model_category = :model_category,
            target.module = :module,
            target.job_id = :job_id,
            target.job_name = :job_name,
            target.cluster_type = :cluster_type,
            target.model_added_by = :added_by,
            target.model_added_date = :now,
            target.is_active = true
        WHEN NOT MATCHED THEN INSERT
            (batch_model_id, model_name, model_display_name, model_description,
             model_category, module, job_id, job_name, cluster_type,
             model_added_by, model_added_date, is_active)
        VALUES
            (:batch_model_id, :model_name, :model_display_name, :model_description,
             :model_category, :module, :job_id, :job_name, :cluster_type,
             :added_by, :now, true)
    """
    execute_non_select_query(query, parameters={
        "model_name": model_name,
        "model_display_name": model_display_name,
        "model_description": model_description,
        "model_category": model_category,
        "module": module,
        "job_id": job_id,
        "job_name": job_name,
        "cluster_type": cluster_type,
        "added_by": added_by,
        "now": now,
        "batch_model_id": batch_model_id,
    })


def get_uc_model_info(model_uc_name_fq : str, model_uc_version:int) -> ModelInfo:
    mlflow.set_registry_uri("databricks-uc")
    model_uri = f"models:/{model_uc_name_fq}/{model_uc_version}"
    model_info = mlflow.models.get_model_info(model_uri)
    return model_info


def get_gwb_model_info(model_id:int)-> GWBModelInfo:
    """Method to get model details using id"""

    query = f"SELECT * FROM \
                {os.environ['CORE_CATALOG_NAME']}.{os.environ['CORE_SCHEMA_NAME']}.models \
            WHERE model_id = :model_id "
        
    result_df = execute_select_query(query, parameters={"model_id": int(model_id)})

    model_info = result_df.apply(lambda row: GWBModelInfo(**row), axis=1).tolist()[0]
    return model_info

def get_gwb_model_deployment_info(deployment_id:int)-> ModelDeploymentInfo:
    """Method to get model deploymenmt details using id"""

    query = f"SELECT * FROM \
                {os.environ['CORE_CATALOG_NAME']}.{os.environ['CORE_SCHEMA_NAME']}.model_deployments \
            WHERE deployment_id = :deployment_id "
        
    result_df = execute_select_query(query, parameters={"deployment_id": int(deployment_id)})

    model_deployment_info = result_df.apply(lambda row: ModelDeploymentInfo(**row), axis=1).tolist()[0]
    return model_deployment_info

def import_model_from_uc(user_email : str,
                        model_category : ModelCategory,
                        model_uc_name : str,
                        model_uc_version: int,                       
                        model_name: None,
                        model_source_version : None,
                        model_display_name:str = None, 
                        model_description_url:str = None                      
                      ) -> int:
    """Imports a UC model intp GWB"""    
    model_info = get_uc_model_info(model_uc_name, model_uc_version)
    #throws exception if not found 
    model_signature = model_info.signature.to_dict()

    if not model_name:
        model_name = model_uc_name.split('.')[2]
    
    if not model_display_name:
        model_display_name = model_name

    gwb_model_id = time.time_ns()

    gwb_model = GWBModelInfo(
        model_id = gwb_model_id, #will be ignored
        model_name = model_name,
        model_display_name = model_display_name,
        model_source_version = model_source_version,
        model_origin = ModelSource.UNITY_CATALOG,
        model_description_url = model_description_url, #website to find more details about model
        model_category = str(model_category),
        model_uc_name = model_uc_name,
        model_uc_version = model_uc_version,
        model_input_schema = model_signature.get("inputs"),
        model_output_schema = model_signature.get("outputs"),
        model_params_schema = model_signature.get("params",None),
        model_owner = "TBD",
        model_added_by = user_email, #id of user
        model_added_date = datetime.now(),
        is_model_deployed = False,
        deployment_ids = "",
        is_active = True,
        deactivated_timestamp=None
    )
    upsert_model_info(gwb_model)

    # Retrieve the persisted model_id (may differ from gwb_model_id if row already existed)
    catalog = os.environ['CORE_CATALOG_NAME']
    schema = os.environ['CORE_SCHEMA_NAME']
    result_df = execute_select_query(
        f"SELECT model_id FROM {catalog}.{schema}.models WHERE model_uc_name = :model_uc_name",
        parameters={"model_uc_name": model_uc_name},
    )
    return int(result_df.iloc[0]['model_id'])


def _inference_tables_enabled(explicit: bool | None = None) -> bool:
    """Whether to enable AI Gateway inference tables on a deployed endpoint
    (HARDENING_CHECKLIST.md 5.1). An explicit argument wins; otherwise the
    GWB_ENABLE_INFERENCE_TABLES env var decides, and the default is ON —
    payload capture is the production posture, so opting *out* is the
    deliberate act (e.g. a data-residency review still pending)."""
    if explicit is not None:
        return explicit
    value = os.environ.get("GWB_ENABLE_INFERENCE_TABLES", "true").strip().lower()
    return value not in ("false", "0", "no", "off")


def _enable_inference_tables(w: WorkspaceClient, endpoint_name: str,
                             catalog_name: str, schema_name: str) -> None:
    """Best-effort: turn on AI Gateway payload capture for an endpoint.

    Called after the endpoint is already deployed and serving, and deliberately
    non-fatal — a gateway/permissions hiccup must not fail a model deploy that
    may have just spent hours provisioning a GPU. On failure it prints the
    remediation (scripts/backfill_inference_tables.py) and moves on."""
    table_prefix = f"{endpoint_name}_serving"
    try:
        w.serving_endpoints.put_ai_gateway(
            name=endpoint_name,
            inference_table_config=AiGatewayInferenceTableConfig(
                catalog_name=catalog_name,
                schema_name=schema_name,
                table_name_prefix=table_prefix,
                enabled=True,
            ),
        )
        print(f"✅ AI Gateway inference tables enabled → "
              f"{catalog_name}.{schema_name}.{table_prefix}_payload")
    except Exception as e:  # noqa: BLE001 — capture is best-effort by design
        print(f"⚠️ Could not enable AI Gateway inference tables on {endpoint_name}: {e}")
        print("   The endpoint is deployed and serving. Enable capture later with "
              "scripts/backfill_inference_tables.py.")


def deploy_model_endpoint(catalog_name: str,
                 schema_name : str,
                 dev_user_prefix:str,
                 fq_model_uc_name : str,
                 model_version: int,
                 workload_type: str,
                 workload_size:str,
                 creating_user_email:str,
                 enable_inference_tables: bool | None = None) -> ServingEndpointDetailed:

    w = WorkspaceClient()

    model_name = fq_model_uc_name.split(".")[2]
    endpoint_name = f"gwb_{dev_user_prefix}_{model_name}_endpoint" if dev_user_prefix and dev_user_prefix.strip() != "" else f"gwb_{model_name}_endpoint"
    scale_to_zero = True

    served_entities = [
        ServedEntityInput(
            entity_name=fq_model_uc_name,
            entity_version=model_version,
            name=model_name,
            workload_type=ServingModelWorkloadType(workload_type),
            workload_size=workload_size,
            scale_to_zero_enabled=scale_to_zero,
        )
    ]
    print(f"Checking if endpoint: {endpoint_name} exists")

    try:
        # try to update the endpoint if already have one
        existing_endpoint = w.serving_endpoints.get(endpoint_name)
        print(f"Updating existing endpoint {endpoint_name}")
        # may take some time to actually do the update
        endpoint_details = w.serving_endpoints.update_config_and_wait(
            name=endpoint_name,
            served_entities=served_entities,
            timeout = timedelta(minutes=360) #wait up to six hours; large/GPU models can provision past 3h
        )
    except errors.platform.ResourceDoesNotExist as e:
        # if no endpoint yet, make it, wait for it to spin up, and put model on endpoint
        print(f"Creating new endpoint {endpoint_name}")
        endpoint_details = w.serving_endpoints.create_and_wait(
            name=endpoint_name,
            config=EndpointCoreConfigInput(
                name=endpoint_name,
                served_entities=served_entities,
            ),
            tags=[
                EndpointTag(key="application", value="genesis_workbench"),
                EndpointTag(key="created_by", value=creating_user_email)
            ],
            timeout = timedelta(minutes=360) #wait up to six hours. some large/GPU models take very long to provision
        )

    # AI Gateway payload capture (HARDENING_CHECKLIST.md 5.1). Applied via
    # put_ai_gateway *after* create/update so both paths share one code path,
    # and best-effort so capture problems never fail the deploy itself.
    # (Replaces the legacy AutoCaptureConfigInput approach; same
    # <endpoint>_serving_payload table name, which delete_endpoint archives.)
    if _inference_tables_enabled(enable_inference_tables):
        _enable_inference_tables(w, endpoint_name, catalog_name, schema_name)
    else:
        print(f"AI Gateway inference tables disabled for {endpoint_name} "
              "(enable_inference_tables=false)")

    return endpoint_details

def deploy_model(user_email: str,
                 gwb_model_id:int,
                 deployment_name:str,
                 deployment_description:str,
                 input_adapter_str:str,
                 output_adapter_str,
                 sample_input_data_dict_as_json:str,
                 sample_params_as_json: str,
                 workload_type:str,
                 workload_size: str):
    print(f"Deploying model id: {gwb_model_id}")
    model_deploy_job_id = os.environ["DEPLOY_MODEL_JOB_ID"]
    params = {
        "gwb_model_id": gwb_model_id,
        "deployment_name" : deployment_name,
        "deployment_description" : deployment_description,
        'input_adapter_str': input_adapter_str,
        'output_adapter_str': output_adapter_str,
        'sample_input_data_dict_as_json': sample_input_data_dict_as_json,
        'sample_params_as_json': sample_params_as_json,
        "workload_type" : workload_type,
        "workload_size" : workload_size,
        "deploy_user": user_email
    }
    
    run_id = execute_workflow(model_deploy_job_id,params)
    return run_id

def delete_endpoint(core_catalog:str, core_schema:str, deployment_id:str):
    """Deletes the endpoint and archives the inference table"""
    
    print("==============================================")
    print(f"⏩️ Getting model details for deployment {deployment_id}")
    deployment_info : ModelDeploymentInfo = get_gwb_model_deployment_info(deployment_id)
    model_info : GWBModelInfo = get_gwb_model_info(deployment_info.model_id)

    model_id = deployment_info.model_id
    endpoint_name = deployment_info.model_endpoint_name

    w = WorkspaceClient()

    print(f"⏩️ Deleting endpoint {endpoint_name}")
    try:
        w.serving_endpoints.delete(name = endpoint_name)
    except Exception as e:
        print(f"Error deleting endpoint {endpoint_name}: {e}. Delete it manually")
    
    print(" ")

    inf_table_name = f"{endpoint_name}_serving_payload"
    print(f"⏩️ Archiving the inference table {inf_table_name}")
    try:
        # Identifiers can't be bound as parameters; validate the parts before
        # they go into the DDL below (endpoint_name comes from the DB row).
        validate_sql_name(core_catalog)
        validate_sql_name(core_schema)
        validate_sql_name(inf_table_name)
        table_exists = execute_select_query(
            f"SELECT 1 FROM {core_catalog}.information_schema.tables "
            f"WHERE table_schema = :schema AND table_name = :table_name",
            parameters={"schema": core_schema, "table_name": inf_table_name},
        )
        if not table_exists.empty:
            bkup_suffix = datetime.now().strftime('%Y%m%d%H%M%S')
            execute_non_select_query(f"""
                ALTER TABLE {core_catalog}.{core_schema}.{inf_table_name}
                RENAME TO {core_catalog}.{core_schema}.{inf_table_name}_bkup_{bkup_suffix}
            """)
        else:
            print(f"  Inference table {inf_table_name} does not exist, skipping archive")
    except Exception as e:
        print(f"  Error archiving inference table {inf_table_name}: {e}. Skipping")
 
    print(" ")

    print(f"⏩️ Deactivating the deployment {deployment_id}")
    execute_non_select_query(
        f"""
        UPDATE {core_catalog}.{core_schema}.model_deployments SET 
          is_active = 'false',
          deactivated_timestamp = current_timestamp()

        WHERE deployment_id = :deployment_id
    """,
        parameters={"deployment_id": int(deployment_id)},
    )

    print(" ")

    print(f"⏩️ Removing deployment from model {model_id}")
    deployed_endpoint_ids = model_info.deployment_ids
    if deployed_endpoint_ids :
      deployed_endpoint_ids_arr = deployed_endpoint_ids.split(",")
      new_deployed_endpoint_ids = ",".join([x for x in deployed_endpoint_ids_arr if x != deployment_id])

      execute_non_select_query(
          f"""
          UPDATE {core_catalog}.{core_schema}.models SET 
            deployment_ids = :deployment_ids

          WHERE model_id = :model_id
    """,
          parameters={"deployment_ids": new_deployed_endpoint_ids, "model_id": int(model_id)},
      )