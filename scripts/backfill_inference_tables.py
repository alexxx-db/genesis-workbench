#!/usr/bin/env python3
"""Genesis Workbench — back-fill AI Gateway inference tables on existing endpoints.

New endpoints get payload capture at deploy time (deploy_model_endpoint(), see
HARDENING_CHECKLIST.md 5.1). Endpoints deployed *before* that change — or whose
capture setup failed and was skipped best-effort — have no inference tables.
This script finds them and turns capture on via put_ai_gateway, matching the
deploy-time convention exactly: capture lands in
<catalog>.<schema>.<endpoint_name>_serving_payload, the table
delete_endpoint() archives when an endpoint is retired.

Dry-run by default: it reports what it *would* change and touches nothing until
--apply is given.

Usage
-----
    python scripts/backfill_inference_tables.py --catalog CAT --schema SCH             # dry-run
    python scripts/backfill_inference_tables.py --catalog CAT --schema SCH --apply
    python scripts/backfill_inference_tables.py ... --endpoint gwb_esm2_endpoint       # just one
    python scripts/backfill_inference_tables.py ... --prefix gwb --profile myprofile

Exit codes: 0 = nothing left to do (or dry-run finished), 1 = an apply failed,
2 = could not run (no SDK / no auth).
"""
from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--catalog", required=True,
                   help="UC catalog for the payload tables (use the GWB core catalog)")
    p.add_argument("--schema", required=True,
                   help="UC schema for the payload tables (use the GWB core schema)")
    p.add_argument("--prefix", default="gwb",
                   help="only endpoints whose name contains this (default: gwb)")
    p.add_argument("--endpoint", action="append", default=[],
                   help="explicit endpoint name (repeatable); overrides --prefix")
    p.add_argument("--apply", action="store_true",
                   help="actually enable capture (default is a dry-run report)")
    p.add_argument("--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"),
                   help="Databricks CLI profile (default: DEFAULT / env)")
    args = p.parse_args()

    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service.serving import AiGatewayInferenceTableConfig
    except ImportError:
        print("databricks-sdk not installed (pip install databricks-sdk)", file=sys.stderr)
        return 2
    try:
        w = WorkspaceClient(profile=args.profile) if args.profile else WorkspaceClient()
        w.current_user.me()
    except Exception as e:  # noqa: BLE001
        print(f"Could not authenticate to the workspace ({type(e).__name__}: {e})",
              file=sys.stderr)
        return 2

    if args.endpoint:
        names = args.endpoint
    else:
        names = [ep.name for ep in w.serving_endpoints.list()
                 if args.prefix in (ep.name or "")]

    already, todo, failed = [], [], []
    for name in sorted(names):
        try:
            ep = w.serving_endpoints.get(name)
        except Exception as e:  # noqa: BLE001
            failed.append(f"{name} — not readable: {e}")
            continue
        itc = getattr(getattr(ep, "ai_gateway", None), "inference_table_config", None)
        if itc and itc.enabled:
            already.append(f"{name} → {itc.catalog_name}.{itc.schema_name}."
                           f"{itc.table_name_prefix}_payload")
            continue
        todo.append(name)
        if not args.apply:
            continue
        try:
            w.serving_endpoints.put_ai_gateway(
                name=name,
                inference_table_config=AiGatewayInferenceTableConfig(
                    catalog_name=args.catalog,
                    schema_name=args.schema,
                    table_name_prefix=f"{name}_serving",
                    enabled=True,
                ),
            )
            print(f"[ENABLED] {name} → {args.catalog}.{args.schema}.{name}_serving_payload")
        except Exception as e:  # noqa: BLE001
            failed.append(f"{name} — put_ai_gateway failed: {e}")

    print(f"\nAI Gateway inference tables — {len(names)} endpoint(s) matched")
    print("=" * 60)
    for line in already:
        print(f"[OK]      {line}")
    if not args.apply:
        for name in todo:
            print(f"[MISSING] {name} → would enable "
                  f"{args.catalog}.{args.schema}.{name}_serving_payload (re-run with --apply)")
    for line in failed:
        print(f"[FAIL]    {line}")
    print("=" * 60)
    print(f"{len(already)} already capturing · {len(todo)} "
          f"{'enabled' if args.apply else 'missing'} · {len(failed)} failed\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
