"""Generic async-job runner for executor chains.

Every long workflow in this app used to run inside one HTTP request and stream
progress over SSE. The server finishes and logs its MLflow run, but the browser
connection does not survive, so the user sees `TypeError: network error` while the
result sits in MLflow unreachable from the UI. Observed across molecular docking,
ligand binder design, motif scaffolding, ADMET and protein binder design.

This module dispatches the same `genesis_workbench.executor.run_chain(...)` as a
Databricks job instead. One orchestrator job serves every chain — the chain name
and its inputs/params travel as job parameters — so adding a feature means adding
a row to CHAINS, not another job.

The chain implementation is untouched: the job calls the identical executor entry
point the SSE routes and the MCP server call, so batch and interactive paths cannot
drift.
"""
from __future__ import annotations

import io
import json
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any, Optional

import mlflow
import pandas as pd
from databricks.sdk import WorkspaceClient
from genesis_workbench.models import set_mlflow_experiment
from genesis_workbench.workbench import UserInfo
from mlflow.tracking import MlflowClient

from app.config import get_settings
from app.services.databricks_links import mlflow_run_url

logger = logging.getLogger(__name__)

ORCHESTRATOR_JOB_NAME = "run_chain_gwb"
STAGING_DIR = "proteina_complexa/chain_inputs"

_job_id_cache: dict[str, int] = {}


@dataclass(frozen=True)
class ChainSpec:
    """A UI feature mapped onto an executor chain."""

    chain: str
    experiment_tag: str
    run_prefix: str
    # Inputs large enough to blow the job-parameter size limit (PDBs, long
    # sequences). These are staged to a UC volume and passed by reference.
    large_inputs: tuple[str, ...] = ()


CHAINS: dict[str, ChainSpec] = {
    "binder_design": ChainSpec(
        chain="protein_binder_design",
        experiment_tag="gwb_binder_design",
        run_prefix="binder_design",
        large_inputs=("target_pdb",),
    ),
    "ligand_binder_design": ChainSpec(
        chain="ligand_binder_design",
        experiment_tag="gwb_ligand_binder_design",
        run_prefix="ligand_binder",
        large_inputs=("ligand_pdb",),
    ),
    "motif_scaffolding": ChainSpec(
        chain="motif_scaffolding",
        experiment_tag="gwb_motif_scaffolding",
        run_prefix="motif_scaffolding",
        large_inputs=("motif_pdb",),
    ),
    "admet": ChainSpec(
        chain="admet_screen",
        experiment_tag="gwb_admet_safety",
        run_prefix="admet_profiling",
    ),
    "molecular_docking": ChainSpec(
        chain="molecular_docking",
        experiment_tag="gwb_molecular_docking",
        run_prefix="molecular_docking",
        large_inputs=("protein_pdb",),
    ),
    "protein_design": ChainSpec(
        chain="protein_design",
        experiment_tag="gwb_protein_design",
        run_prefix="protein_design",
        large_inputs=("pdb",),
    ),
}


@dataclass(frozen=True)
class ChainDispatchResult:
    job_id: int
    job_run_id: int
    mlflow_run_id: str
    experiment_id: str


def _pin_mlflow() -> None:
    """Re-pin tracking + registry URIs.

    Other handlers in this shared process leave the process-global URI pointing
    elsewhere; without re-pinning here, runs intermittently land in the wrong
    store and vanish from Search Past Runs.
    """
    mlflow.set_registry_uri("databricks-uc")
    mlflow.set_tracking_uri("databricks")


def _resolve_job_id(w: Optional[WorkspaceClient] = None) -> int:
    cached = _job_id_cache.get(ORCHESTRATOR_JOB_NAME)
    if cached is not None:
        return cached
    env_id = os.environ.get("RUN_CHAIN_JOB_ID")
    if env_id:
        _job_id_cache[ORCHESTRATOR_JOB_NAME] = int(env_id)
        return _job_id_cache[ORCHESTRATOR_JOB_NAME]
    workspace = w or WorkspaceClient()
    matches = list(workspace.jobs.list(name=ORCHESTRATOR_JOB_NAME))
    if not matches:
        raise RuntimeError(
            f"Orchestrator job '{ORCHESTRATOR_JOB_NAME}' not found. Deploy the "
            "proteina_complexa submodule first: `./deploy.sh small_molecule aws "
            "--only-submodule proteina_complexa/proteina_complexa_v1`"
        )
    _job_id_cache[ORCHESTRATOR_JOB_NAME] = int(matches[0].job_id)
    return _job_id_cache[ORCHESTRATOR_JOB_NAME]


def _stage_large_input(value: str, catalog: str, schema: str, name: str) -> dict:
    """Upload an oversized input to a UC volume, returning a reference the
    orchestrator inlines. The Apps sandbox blocks direct /Volumes writes, so this
    goes through the SDK Files API."""
    path = f"/Volumes/{catalog}/{schema}/{STAGING_DIR}/{uuid.uuid4().hex[:12]}/{name}"
    WorkspaceClient().files.upload(
        file_path=path,
        contents=io.BytesIO(value.encode("utf-8")),
        overwrite=True,
    )
    return {"__volume_path__": path}


def start_chain_job(
    feature: str,
    user_info: UserInfo,
    inputs: dict[str, Any],
    params: dict[str, Any],
    mlflow_run_name: str,
    mlflow_experiment: str | None = None,
) -> ChainDispatchResult:
    """Pre-create the MLflow run, then dispatch the orchestrator job."""
    spec = CHAINS.get(feature)
    if spec is None:
        raise ValueError(f"Unknown chain feature: {feature!r}")

    _pin_mlflow()
    w = WorkspaceClient()
    experiment_tag = mlflow_experiment or spec.experiment_tag
    experiment = set_mlflow_experiment(
        experiment_tag=experiment_tag, user_email=user_info.user_email
    )
    job_id = _resolve_job_id(w)

    s = get_settings()
    staged = dict(inputs)
    for key in spec.large_inputs:
        val = staged.get(key)
        if isinstance(val, str) and len(val) > 4000:
            staged[key] = _stage_large_input(val, s.catalog, s.schema, f"{key}.txt")

    with mlflow.start_run(
        run_name=mlflow_run_name, experiment_id=experiment.experiment_id
    ) as pre_run:
        mlflow_run_id = pre_run.info.run_id
        mlflow.set_tag("origin", "genesis_workbench")
        mlflow.set_tag("feature", spec.chain)
        mlflow.set_tag("created_by", user_info.user_email)
        # `submitted` so the run is visible while the cluster starts. Flipped to
        # `failed` below if run_now raises, so it never sits here forever.
        mlflow.set_tag("job_status", "submitted")

        try:
            job_run = w.jobs.run_now(
                job_id=job_id,
                job_parameters={
                    "chain": spec.chain,
                    "inputs_json": json.dumps(staged),
                    "params_json": json.dumps(params),
                    # Short tag, never a resolved path — the orchestrator prepends
                    # the user folder itself.
                    "mlflow_experiment": experiment_tag,
                    "mlflow_run_name": mlflow_run_name,
                    "mlflow_run_id": mlflow_run_id,
                    "user_email": user_info.user_email,
                },
            )
        except Exception as e:
            mlflow.set_tag("job_status", "failed")
            mlflow.set_tag("error", str(e)[:500])
            raise

        mlflow.set_tag("job_run_id", str(job_run.run_id))

    return ChainDispatchResult(
        job_id=job_id,
        job_run_id=int(job_run.run_id),
        mlflow_run_id=mlflow_run_id,
        experiment_id=str(experiment.experiment_id),
    )


_PROGRESS_MAP = {
    "submitted": "🟩⬜⬜⬜",
    "started": "🟩🟩⬜⬜",
    "logging": "🟩🟩🟩⬜",
    "complete": "🟩🟩🟩🟩",
    "failed": "🟥",
    "error": "🟥",
}


def _progress(status: str) -> str:
    return _PROGRESS_MAP.get((status or "").lower(), "⬜⬜⬜⬜")


def search_chain_runs(
    feature: str, user_email: str, needle: str = "", by: str = "run_name"
) -> list[dict]:
    """Rows for the shared RunSearchSection: run_id, run_name, experiment_name,
    status, progress, detail, start_time_ms, run_url."""
    spec = CHAINS.get(feature)
    if spec is None:
        return []
    _pin_mlflow()
    exp_map = {
        e.experiment_id: e.name
        for e in mlflow.search_experiments(
            filter_string="tags.used_by_genesis_workbench='yes'"
        )
    }
    if not exp_map:
        return []

    parts = [
        f"tags.created_by='{user_email}'",
        "tags.origin='genesis_workbench'",
        f"tags.feature='{spec.chain}'",
    ]
    if needle:
        field = "experimentName" if by == "experiment_name" else "runName"
        parts.append(f"tags.mlflow.{field} LIKE '%{needle}%'")
    try:
        runs = mlflow.search_runs(
            experiment_ids=list(exp_map.keys()),
            filter_string=" AND ".join(parts),
            order_by=["start_time DESC"],
            max_results=100,
        )
    except Exception:
        logger.exception("chain search_runs failed for %s", feature)
        return []
    if runs.empty:
        return []

    out: list[dict] = []
    for _, r in runs.iterrows():
        status = str(r.get("tags.job_status", "unknown"))
        # A crashed orchestrator that never wrote its failure tag would otherwise
        # render as perpetually running.
        if str(r.get("status", "")) in ("FAILED", "KILLED") and status not in (
            "complete",
            "failed",
        ):
            status = "failed"
        exp_id = r.get("experiment_id")
        start_ts = r.get("start_time")
        n = r.get("metrics.num_designs")
        stage = r.get("tags.stage")
        detail = (
            f"{int(n)} result(s)"
            if pd.notna(n)
            else (str(stage) if stage is not None and pd.notna(stage) else "")
        )
        out.append(
            {
                "run_id": str(r["run_id"]),
                "run_name": str(r.get("tags.mlflow.runName", "")),
                "experiment_name": (exp_map.get(exp_id, "") or "").split("/")[-1],
                "status": status,
                "progress": _progress(status),
                "detail": detail,
                "start_time_ms": (
                    int(start_ts.value // 1_000_000) if pd.notna(start_ts) else None
                ),
                "run_url": mlflow_run_url(str(exp_id), str(r["run_id"])),
            }
        )
    return out


def get_chain_result(run_id: str) -> dict:
    """Full chain result for the view dialog. Gated on job_status=complete."""
    _pin_mlflow()
    client = MlflowClient()
    run = client.get_run(run_id)
    status = run.data.tags.get("job_status", "unknown")
    if status != "complete":
        return {"status": status, "result": {}, "error": run.data.tags.get("error", "")}
    try:
        local = client.download_artifacts(run_id, "result.json")
        with open(local) as f:
            result = json.load(f)
    except Exception:
        logger.exception("could not load result.json for run %s", run_id)
        return {"status": status, "result": {}, "error": "result artifact unavailable"}

    # MolstarViewer takes pre-rendered HTML, not PDB text, so build it here the same
    # way the /stream routes do rather than shipping raw PDBs to the browser.
    from app.services.molstar import molstar_html_singlebody

    designs = result.get("designs") if isinstance(result, dict) else None
    if isinstance(designs, list):
        for d in designs:
            if not isinstance(d, dict):
                continue
            pdb = d.get("pdb_output") or d.get("esmfold_pdb")
            if pdb:
                try:
                    d["viewer_html"] = molstar_html_singlebody(
                        pdb, name=str(d.get("sample_id", "design"))
                    )
                except Exception:
                    logger.exception("molstar render failed for a design")
    target_pdb = result.get("target_pdb") if isinstance(result, dict) else None
    if target_pdb:
        try:
            result["target_viewer_html"] = molstar_html_singlebody(
                target_pdb, name="target"
            )
        except Exception:
            logger.exception("molstar render failed for target")

    return {"status": status, "result": result, "error": ""}
