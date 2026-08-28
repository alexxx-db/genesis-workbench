"""Generic launch / search / result routes for executor chains run as jobs.

One set of routes serves every chain-backed feature (binder design, ligand binder
design, motif scaffolding, ADMET, protein design). The feature name selects a
ChainSpec; inputs and params pass straight through to the executor.

These exist because the equivalent `/stream` routes run the whole pipeline inside
one HTTP request: the server completes and logs to MLflow, but the browser
connection does not survive, so the user sees `TypeError: network error` and cannot
reach a result that actually exists.
"""
from __future__ import annotations

from typing import Any, Optional

from databricks.sdk import WorkspaceClient
from fastapi import APIRouter, HTTPException, Query, status
from genesis_workbench.workbench import UserInfo
from pydantic import BaseModel, Field

from app.auth import CurrentUserDep
from app.services import chain_jobs
from app.services.databricks_links import job_run_url

router = APIRouter(prefix="/api/chains", tags=["chains"])


def _user_info(user: CurrentUserDep) -> UserInfo:
    w = WorkspaceClient()
    try:
        me = w.current_user.me()
        user_name, display_name = me.user_name, me.display_name
    except Exception:
        user_name = display_name = user.preferred_username
    return UserInfo(
        user_email=user.email,
        user_name=user_name,
        display_name=display_name,
    )


class ChainStartRequest(BaseModel):
    feature: str = Field(..., min_length=1)
    inputs: dict[str, Any] = {}
    params: dict[str, Any] = {}
    mlflow_run_name: str = Field(..., min_length=1)
    mlflow_experiment: Optional[str] = None


class ChainStartResponse(BaseModel):
    job_id: int
    job_run_id: int
    mlflow_run_id: str
    experiment_id: str
    job_run_url: str = ""


class ChainRunRow(BaseModel):
    run_id: str
    run_name: str
    experiment_name: str
    status: str
    progress: str
    detail: str = ""
    start_time_ms: Optional[int] = None
    run_url: str = ""


class ChainSearchResponse(BaseModel):
    runs: list[ChainRunRow]


class ChainResultResponse(BaseModel):
    status: str
    result: dict[str, Any] = {}
    error: str = ""


@router.post("/start", response_model=ChainStartResponse)
def start(payload: ChainStartRequest, user: CurrentUserDep) -> ChainStartResponse:
    if not user.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User email missing from headers")
    if payload.feature not in chain_jobs.CHAINS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unknown feature '{payload.feature}'. Expected one of: "
            f"{sorted(chain_jobs.CHAINS)}",
        )
    try:
        res = chain_jobs.start_chain_job(
            feature=payload.feature,
            user_info=_user_info(user),
            inputs=payload.inputs,
            params=payload.params,
            mlflow_run_name=payload.mlflow_run_name.strip(),
            mlflow_experiment=(payload.mlflow_experiment or "").strip() or None,
        )
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Failed to start job: {e}")
    return ChainStartResponse(
        job_id=res.job_id,
        job_run_id=res.job_run_id,
        mlflow_run_id=res.mlflow_run_id,
        experiment_id=res.experiment_id,
        job_run_url=job_run_url(res.job_id, res.job_run_id),
    )


@router.get("/search", response_model=ChainSearchResponse)
def search(
    user: CurrentUserDep,
    feature: str = Query(..., min_length=1),
    by: str = Query("run_name", pattern=r"^(run_name|experiment_name)$"),
    text: str = Query("", max_length=200),
) -> ChainSearchResponse:
    if not user.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User email missing from headers")
    rows = chain_jobs.search_chain_runs(feature, user.email, text.strip(), by)
    return ChainSearchResponse(runs=[ChainRunRow(**r) for r in rows])


@router.get("/result", response_model=ChainResultResponse)
def result(run_id: str, _: CurrentUserDep) -> ChainResultResponse:
    return ChainResultResponse(**chain_jobs.get_chain_result(run_id))
