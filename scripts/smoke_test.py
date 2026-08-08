#!/usr/bin/env python3
"""Genesis Workbench — post-deploy smoke test (HARDENING_CHECKLIST.md 4.2).

deploy.sh's "SUCCESS" banner only means the bundle deployed; the register/
deploy/data-prep jobs run asynchronously and can fail afterwards, and a serving
endpoint can sit unready long after the script exits. This harness executes the
post-deploy verification the docs prescribe by hand (CLAUDE.md → "Post-deploy:
monitor jobs"), against a live install:

    jobs       recent GWB job runs that did NOT finish SUCCESS
    endpoints  every GWB serving endpoint is READY
    capture    every GWB endpoint has AI Gateway inference tables enabled (5.1)
    payload    a sample COUNT(*) against each capture table (5.1 acceptance)
    apps       the UI / MCP Databricks Apps are RUNNING
    inference  OPT-IN one real scoring call (--infer + --input), opt-in because
               waking a scale-to-zero GPU endpoint costs money and minutes

Usage
-----
    python scripts/smoke_test.py                          # default profile, prefix gwb
    python scripts/smoke_test.py --profile my-install
    python scripts/smoke_test.py --warehouse-id abc123    # else first RUNNING warehouse
    python scripts/smoke_test.py --infer gwb_esm2_endpoint --input '{"inputs": ["MKT"]}'
    python scripts/smoke_test.py --json                   # machine-readable (CI/nightly)

Exit codes: 0 = all checks pass, 1 = at least one FAIL, 2 = could not run.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


@dataclass
class Result:
    check: str
    status: str
    detail: str = ""
    evidence: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"check": self.check, "status": self.status,
                "detail": self.detail, "evidence": self.evidence}


def _cap(items: list[str], n: int = 10) -> list[str]:
    return items[:n] + ([f"… and {len(items) - n} more"] if len(items) > n else [])


def check_jobs(w, prefix: str, limit: int) -> Result:
    """Any recent, finished GWB job run that is not SUCCESS is a finding."""
    bad = []
    seen = scanned = 0
    for run in w.jobs.list_runs(expand_tasks=False):
        scanned += 1
        if scanned > max(limit * 10, 500):   # don't page a busy workspace forever
            break
        name = run.run_name or ""
        if prefix not in name:
            continue
        seen += 1
        if seen > limit:
            break
        state = getattr(run, "state", None)
        result = str(getattr(state, "result_state", "") or "")
        if result and result != "SUCCESS":
            bad.append(f"{name} — run {run.run_id}: {result}")
    if not seen:
        return Result("jobs", SKIP, f"No recent job runs matching '{prefix}' "
                                    f"in the last {scanned - 1} run(s) scanned.")
    if bad:
        return Result("jobs", FAIL,
                      f"{len(bad)} of the last {min(seen, limit)} GWB job run(s) "
                      "did not succeed. Open the run to see the failing task.",
                      _cap(bad))
    return Result("jobs", PASS, f"Last {min(seen, limit)} GWB job run(s) all SUCCESS "
                                "(or still running).")


def _gwb_endpoints(w, prefix: str) -> list:
    return [ep for ep in w.serving_endpoints.list() if prefix in (ep.name or "")]


def check_endpoints(w, prefix: str) -> tuple[Result, list]:
    eps = _gwb_endpoints(w, prefix)
    if not eps:
        return Result("endpoints", FAIL,
                      f"No serving endpoints matching '{prefix}' — is GWB deployed "
                      "to this workspace / does the profile point at the right one?"), []
    not_ready = [f"{ep.name} — ready={getattr(ep.state, 'ready', None)}, "
                 f"update={getattr(ep.state, 'config_update', None)}"
                 for ep in eps
                 if str(getattr(ep.state, "ready", "")) != "EndpointStateReady.READY"
                 and str(getattr(ep.state, "ready", "")) != "READY"]
    if not_ready:
        return Result("endpoints", FAIL,
                      f"{len(not_ready)} of {len(eps)} GWB endpoint(s) not READY.",
                      _cap(not_ready)), eps
    return Result("endpoints", PASS, f"All {len(eps)} GWB endpoint(s) READY."), eps


def check_capture(w, eps) -> tuple[Result, list[tuple[str, str]]]:
    """5.1 — every endpoint should capture payloads; returns the tables to sample."""
    tables: list[tuple[str, str]] = []          # (endpoint, fq_payload_table)
    if not eps:
        return Result("capture", SKIP, "No endpoints to inspect."), tables
    missing = []
    for ep in eps:
        try:
            detail = w.serving_endpoints.get(ep.name)
        except Exception as e:  # noqa: BLE001
            missing.append(f"{ep.name} — not readable: {e}")
            continue
        itc = getattr(getattr(detail, "ai_gateway", None), "inference_table_config", None)
        if itc and itc.enabled:
            tables.append((ep.name, f"{itc.catalog_name}.{itc.schema_name}."
                                    f"{itc.table_name_prefix}_payload"))
        else:
            missing.append(f"{ep.name} — no AI Gateway inference table")
    if missing:
        return Result("capture", FAIL,
                      f"{len(missing)} endpoint(s) without payload capture. "
                      "Run scripts/backfill_inference_tables.py --catalog … "
                      "--schema … --apply.", _cap(missing)), tables
    return Result("capture", PASS,
                  f"All {len(tables)} endpoint(s) capture payloads."), tables


def check_payload_tables(w, tables, warehouse_id: str | None) -> Result:
    """5.1 acceptance — 'a sample query shows captured requests', executed."""
    if not tables:
        return Result("payload", SKIP, "No capture tables to sample.")
    if not warehouse_id:
        running = [wh for wh in w.warehouses.list()
                   if str(getattr(wh, "state", "")).endswith("RUNNING")]
        warehouse_id = running[0].id if running else None
    if not warehouse_id:
        return Result("payload", SKIP,
                      "No RUNNING SQL warehouse found and none given via "
                      "--warehouse-id; cannot sample the payload tables.")
    counts, empty, errors = [], [], []
    for ep_name, fq in tables:
        try:
            resp = w.statement_execution.execute_statement(
                statement=f"SELECT COUNT(*) FROM {fq}",
                warehouse_id=warehouse_id, wait_timeout="30s")
            state = str(getattr(getattr(resp, "status", None), "state", ""))
            if not state.endswith("SUCCEEDED"):
                err = getattr(getattr(resp, "status", None), "error", None)
                raise RuntimeError(getattr(err, "message", state) or state)
            n = int(resp.result.data_array[0][0])
            (counts if n > 0 else empty).append(f"{fq} — {n} row(s)")
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if "TABLE_OR_VIEW_NOT_FOUND" in msg or "cannot be found" in msg:
                # Capture is on but the table materializes on first request —
                # not an error on a fresh install, but worth surfacing.
                empty.append(f"{fq} — not materialized yet (no requests captured)")
            else:
                errors.append(f"{fq} — {msg[:140]}")
    if errors:
        return Result("payload", FAIL,
                      f"{len(errors)} payload table(s) not queryable.",
                      _cap(errors + empty))
    if counts:
        return Result("payload", PASS,
                      f"{len(counts)} payload table(s) hold captured requests"
                      + (f"; {len(empty)} await their first request." if empty else "."),
                      _cap(counts + empty))
    return Result("payload", PASS,
                  "Capture is enabled everywhere; no endpoint has received a "
                  "request since it was turned on (tables materialize on first "
                  "request).", _cap(empty))


def check_apps(w, app_substr: str) -> Result:
    apps = [a for a in w.apps.list() if app_substr in (a.name or "")]
    if not apps:
        return Result("apps", SKIP, f"No Databricks App matching '{app_substr}'.")
    bad = [f"{a.name} — {getattr(getattr(a, 'app_status', None), 'state', None)}"
           for a in apps
           if not str(getattr(getattr(a, "app_status", None), "state", "")).endswith("RUNNING")]
    if bad:
        return Result("apps", FAIL, f"{len(bad)} of {len(apps)} GWB app(s) not RUNNING.", bad)
    return Result("apps", PASS, f"All {len(apps)} GWB app(s) RUNNING.")


def check_inference(w, endpoint: str, payload: str) -> Result:
    """Opt-in: one real request. May wake a scale-to-zero endpoint (cost/minutes)."""
    try:
        body = json.loads(payload)
    except json.JSONDecodeError as e:
        return Result("inference", FAIL, f"--input is not valid JSON: {e}")
    try:
        resp = w.api_client.do("POST", f"/serving-endpoints/{endpoint}/invocations",
                               body=body)
        preview = json.dumps(resp)[:200]
        return Result("inference", PASS, f"{endpoint} answered.", [preview])
    except Exception as e:  # noqa: BLE001
        return Result("inference", FAIL, f"{endpoint} — {e}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"),
                   help="Databricks CLI profile (default: DEFAULT / env)")
    p.add_argument("--prefix", default="gwb",
                   help="jobs/endpoints whose name contains this (default: gwb)")
    p.add_argument("--app", default="genesis",
                   help="substring matching the GWB Databricks Apps (default: genesis)")
    p.add_argument("--runs", type=int, default=50,
                   help="how many recent job runs to inspect (default: 50)")
    p.add_argument("--warehouse-id", default=None,
                   help="SQL warehouse for the payload sample query "
                        "(default: first RUNNING warehouse)")
    p.add_argument("--infer", metavar="ENDPOINT",
                   help="opt-in: send one scoring request to this endpoint")
    p.add_argument("--input", default=None,
                   help="JSON body for --infer (e.g. '{\"inputs\": [...]}')")
    p.add_argument("--json", action="store_true", help="emit JSON (for CI/nightly)")
    args = p.parse_args()
    if args.infer and not args.input:
        p.error("--infer requires --input")

    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient(profile=args.profile) if args.profile else WorkspaceClient()
        me = w.current_user.me().user_name
        host = w.config.host
    except Exception as e:  # noqa: BLE001
        print(f"smoke_test: could not authenticate ({type(e).__name__}: {e})",
              file=sys.stderr)
        return 2

    results = [check_jobs(w, args.prefix, args.runs)]
    ep_result, eps = check_endpoints(w, args.prefix)
    results.append(ep_result)
    cap_result, tables = check_capture(w, eps)
    results.append(cap_result)
    results.append(check_payload_tables(w, tables, args.warehouse_id))
    results.append(check_apps(w, args.app))
    if args.infer:
        results.append(check_inference(w, args.infer, args.input))

    if args.json:
        print(json.dumps({"host": host, "user": me,
                          "results": [r.as_dict() for r in results]}, indent=2))
    else:
        print(f"\nGenesis Workbench — post-deploy smoke test")
        print(f"{host} as {me}")
        print("=" * 64)
        for r in results:
            print(f"[{r.status}] {r.check:<10} {r.detail}")
            for e in r.evidence:
                print(f"             · {e}")
        counts = {s: sum(1 for r in results if r.status == s) for s in (PASS, FAIL, SKIP)}
        print("=" * 64)
        print(f"{counts[PASS]} passed · {counts[FAIL]} failed · {counts[SKIP]} skipped\n")
    return 1 if any(r.status == FAIL for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
