#!/usr/bin/env python3
"""Seed Genesis Workbench serving endpoints with realistic demo traffic.

Why: `enable_inference_tables` captures every request/response into
<catalog>.<schema>.<endpoint>_serving_payload. On a fresh install those tables
exist but are empty, so the AI Gateway payload-capture feature — and any
monitoring dashboard built on it — demos as a blank page.

This script drives a small amount of *real* traffic through the endpoints using
Genesis Workbench's own reference data (SMILES from repurposing_hub, protein
sequences from gene_sequences), so the capture tables fill with scientifically
plausible payloads rather than synthetic junk.

Safe to re-run; each run adds traffic. Every request is tagged with a
client_request_id prefix so demo traffic can be told apart from real usage.

Usage:
    python scripts/seed_demo_inference.py --catalog alexxx --schema genesis_workbench
    python scripts/seed_demo_inference.py --n 3 --dry-run
"""
import argparse
import json
import subprocess
import sys
import time

REQUEST_ID_PREFIX = "gwb-demo-seed"


def cli(args, timeout=300):
    """Run the databricks CLI and return parsed JSON (or None on failure)."""
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        return None, (p.stderr or p.stdout).strip()[:300]
    try:
        return json.loads(p.stdout), None
    except json.JSONDecodeError:
        return p.stdout.strip(), None


def fetch_column(profile, sql, column, limit):
    out, err = cli(["databricks", "experimental", "aitools", "tools", "query", sql,
                    "--profile", profile])
    if err or not isinstance(out, list):
        print(f"  ! could not fetch {column}: {err}")
        return []
    return [r[column] for r in out if r.get(column)][:limit]


def invoke(profile, endpoint, payload, req_id, retries=1):
    """Invoke an endpoint, retrying once past a cold start.

    Scale-to-zero GPU endpoints take longer than the client timeout to answer their
    first request while the container loads the model. That first call still warms
    the container, so an immediate retry normally succeeds in well under a second.
    """
    args = ["databricks", "serving-endpoints", "query", endpoint,
            "--json", json.dumps(payload),
            "--client-request-id", req_id,
            "--profile", profile]
    for attempt in range(retries + 1):
        out, err = cli(args)
        if not err:
            return out, None, attempt
        if attempt < retries:
            print(f"    cold start — warming {endpoint}, retrying")
            time.sleep(5)
    return None, err, retries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="alexxx")
    ap.add_argument("--schema", default="genesis_workbench")
    ap.add_argument("--profile", default="DEFAULT")
    ap.add_argument("--n", type=int, default=5, help="requests per endpoint")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    fq = f"{a.catalog}.{a.schema}"

    print(f"Pulling seed inputs from {fq} ...")
    # Mid-length drug-like molecules and short proteins keep latency sane; ESMFold in
    # particular scales badly with sequence length.
    smiles = fetch_column(a.profile,
        f"SELECT smiles FROM {fq}.repurposing_hub "
        f"WHERE smiles IS NOT NULL AND length(smiles) BETWEEN 20 AND 70 "
        f"ORDER BY drug_name LIMIT {a.n}", "smiles", a.n)
    seqs = fetch_column(a.profile,
        f"SELECT sequence FROM {fq}.gene_sequences "
        f"WHERE seq_length BETWEEN 80 AND 200 ORDER BY gene LIMIT {a.n}", "sequence", a.n)
    print(f"  {len(smiles)} SMILES, {len(seqs)} protein sequences")
    if not smiles and not seqs:
        print("No seed data available — is the schema populated?")
        return 1

    # (endpoint, inputs, payload builder). Only endpoints whose signature is a
    # simple string/struct are seeded; PDB- and h5ad-driven ones need real study
    # artifacts and are better demoed through the UI.
    plan = [
        ("gwb_alex_chemprop_bbbp_endpoint",     smiles, lambda v: {"inputs": [v]}),
        ("gwb_alex_chemprop_clintox_endpoint",  smiles, lambda v: {"inputs": [v]}),
        ("gwb_alex_genmol_endpoint",            smiles, lambda v: {"inputs": [{"fragment": v}]}),
        ("gwb_alex_esm2_embeddings_endpoint",   seqs,   lambda v: {"inputs": [v]}),
        ("gwb_alex_deepstabp_v1_endpoint",      seqs,
         lambda v: {"inputs": [{"sequence": v, "growth_temp": 37.0, "mt_mode": "cell"}]}),
    ]

    live, err = cli(["databricks", "serving-endpoints", "list", "--profile", a.profile,
                     "--output", "json"])
    ready = set()
    if isinstance(live, list):
        ready = {e["name"] for e in live
                 if (e.get("state") or {}).get("ready") == "READY"}
    elif isinstance(live, dict):
        ready = {e["name"] for e in live.get("endpoints", [])
                 if (e.get("state") or {}).get("ready") == "READY"}

    total_ok = total_fail = 0
    for endpoint, values, build in plan:
        if endpoint not in ready:
            print(f"\n{endpoint}: not READY — skipping")
            continue
        if not values:
            print(f"\n{endpoint}: no seed inputs — skipping")
            continue
        print(f"\n{endpoint}  ({len(values)} requests)")
        for i, v in enumerate(values):
            rid = f"{REQUEST_ID_PREFIX}-{endpoint.split('_')[2]}-{i}"
            if a.dry_run:
                print(f"  [dry-run] {rid}: {json.dumps(build(v))[:90]}")
                continue
            t0 = time.time()
            out, e, tries = invoke(a.profile, endpoint, build(v), rid)
            dt = time.time() - t0
            if e:
                total_fail += 1
                print(f"  x {rid}  {dt:5.1f}s  {e[:120]}", flush=True)
            else:
                total_ok += 1
                preview = json.dumps(out)[:80] if out else ""
                warm = " (after warm-up)" if tries else ""
                print(f"  o {rid}  {dt:5.1f}s{warm}  {preview}", flush=True)

    print(f"\n{total_ok} succeeded, {total_fail} failed.")
    if not a.dry_run and total_ok:
        print("Payload capture is asynchronous — allow a few minutes before the "
              "*_serving_payload tables and the observability dashboard fill.")
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
