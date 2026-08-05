#!/usr/bin/env python3
"""Genesis Workbench — executable hardening checks.

HARDENING_CHECKLIST.md states acceptance criteria in prose. This script executes
the subset of them that can be decided mechanically, against a live workspace and
against this source tree, and reports PASS / FAIL / SKIP per checklist item.

The point is not to make the checklist look satisfied. A demo-grade install is
*expected* to fail several of these on first run — that failing report is the
useful artifact, because it is evidence of the gap rather than an assertion about
it. Fix items, re-run, and the delta is the productionization progress.

Usage
-----
    python scripts/hardening_check.py                     # all checks
    python scripts/hardening_check.py --source-only       # no workspace needed
    python scripts/hardening_check.py --json              # machine-readable (CI)
    python scripts/hardening_check.py --profile myprofile # named CLI profile

Exit codes: 0 = no failures, 1 = at least one FAIL, 2 = could not run.

Checks map 1:1 onto HARDENING_CHECKLIST.md section numbers:
    1.1  jobs run as a service principal, not a human
    1.2  no hardcoded workspace-specific defaults in source
    1.3  job clusters are ON_DEMAND and carry cost-allocation tags
    2.2  the MCP app is not shared broadly
    3.1  no plaintext credentials in job definitions
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"

# Tags every cluster-backed job must carry for cost allocation (checklist 1.3 /
# 6.1). Override for a customer's own tagging standard.
REQUIRED_TAGS = ("cost_center", "project")

# Job-setting keys whose values must be secret references, never literals.
_SECRETISH = re.compile(r"(token|secret|password|passwd|credential|api[_-]?key)", re.I)
_SECRET_REF = re.compile(r"\{\{\s*secrets/")
# A literal that looks like a real credential rather than a placeholder.
_PLACEHOLDER = re.compile(r"^(|none|null|todo|changeme|<[^>]*>|\$\{[^}]*\})$", re.I)

# Groups that mean "effectively everyone" on a Databricks workspace.
_BROAD_PRINCIPALS = {"users", "account users", "all users"}


@dataclass
class Result:
    item: str            # HARDENING_CHECKLIST.md section, e.g. "1.1"
    title: str
    status: str
    detail: str = ""
    evidence: list[str] = field(default_factory=list)   # offending objects, capped

    def as_dict(self) -> dict:
        return {"item": self.item, "title": self.title, "status": self.status,
                "detail": self.detail, "evidence": self.evidence}


def _cap(items: list[str], n: int = 10) -> list[str]:
    """Show the first n offenders; a wall of 400 job names helps nobody."""
    return items[:n] + ([f"… and {len(items) - n} more"] if len(items) > n else [])


# ─── source checks (no workspace credentials required) ───────────────────────

def check_hardcoded_defaults() -> Result:
    """1.2 — workspace-specific literals must not be baked into source.

    The checklist names these explicitly; grep for them so the acceptance
    criterion ("grep for known literals returns none") is actually executed."""
    patterns = [
        (r'DEFAULT_CATALOG\s*=\s*["\']genesis_workbench["\']',
         "hardcoded default catalog"),
        (r'DEFAULT_SCHEMA\s*=\s*["\'][a-z_]+["\']', "hardcoded default schema"),
        # A bare 16-hex warehouse id assigned in source is workspace-specific.
        (r'sql_warehouse_id\s*[=:]\s*["\'][0-9a-f]{16}["\']',
         "hardcoded SQL warehouse id"),
        (r'["\'][0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}["\']\s*'
         r'#\s*(app|sp|service.principal)', "hardcoded service-principal id"),
    ]
    hits: list[str] = []
    for path in REPO.rglob("*.py"):
        if any(p in path.parts for p in ("node_modules", ".git", "dist", "build")):
            continue
        if path.name == Path(__file__).name:
            continue                      # the patterns themselves live here
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat, label in patterns:
            for m in re.finditer(pat, text):
                line = text[: m.start()].count("\n") + 1
                hits.append(f"{path.relative_to(REPO)}:{line} — {label}")
    if hits:
        return Result("1.2", "No hardcoded workspace-specific defaults", FAIL,
                      f"{len(hits)} hardcoded value(s) found; these must flow from "
                      "env files → DAB variables → app config.", _cap(hits))
    return Result("1.2", "No hardcoded workspace-specific defaults", PASS,
                  "No known workspace-specific literals in source.")


def check_bundle_run_as() -> Result:
    """1.1 (source half) — bundles must not declare run_as as the deploying human.

    Complements the live check below: this one fails even before a deploy, which
    is where you want to catch it."""
    hits: list[str] = []
    for path in REPO.rglob("databricks.yml"):
        if "node_modules" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"run_as:\s*\n\s*user_name:\s*(\S+)", text):
            line = text[: m.start()].count("\n") + 1
            hits.append(f"{path.relative_to(REPO)}:{line} — run_as user_name: {m.group(1)}")
    if hits:
        return Result("1.1", "Bundles declare a service-principal run_as", FAIL,
                      f"{len(hits)} bundle target(s) run as a user. Jobs should "
                      "run_as a runtime service principal so ownership survives "
                      "off-boarding.", _cap(hits))
    return Result("1.1", "Bundles declare a service-principal run_as", PASS,
                  "No bundle target runs as a named user.")


def check_mcp_broad_share_declared() -> Result:
    """2.2 (source half) — the MCP app bundle must not grant a broad principal."""
    path = REPO / "modules/core/resources/mcp_app.yml"
    if not path.exists():
        return Result("2.2", "MCP app is not shared broadly", SKIP,
                      "mcp_app.yml not found.")
    text = path.read_text(encoding="utf-8", errors="ignore")
    hits = [f"{path.relative_to(REPO)} — group_name: {m.group(1)}"
            for m in re.finditer(r"group_name:\s*[\"']?([^\"'\n]+)", text)
            if m.group(1).strip().lower() in _BROAD_PRINCIPALS]
    if hits:
        return Result("2.2", "MCP app is not shared broadly", FAIL,
                      "The MCP server runs every capability as the app SP with no "
                      "per-caller authorization; a broad grant makes every "
                      "capability callable by every workspace user.", hits)
    return Result("2.2", "MCP app is not shared broadly", PASS,
                  "No broad principal granted in the app bundle.")


# ─── live-workspace checks ──────────────────────────────────────────────────

def _jobs(w, prefix: str | None):
    """GWB-owned jobs. Name prefix filter keeps the report scoped to this install
    rather than every job in a shared workspace."""
    out = []
    for j in w.jobs.list(expand_tasks=True):
        name = (getattr(j.settings, "name", "") or "") if j.settings else ""
        if prefix and prefix not in name:
            continue
        out.append(j)
    return out


def check_jobs_run_as_sp(w, prefix) -> Result:
    """1.1 (live half) — deployed jobs must run as a service principal."""
    offenders = []
    for j in _jobs(w, prefix):
        s = j.settings
        name = getattr(s, "name", str(j.job_id))
        if getattr(s, "run_as_service_principal_name", None):
            continue
        user = getattr(s, "run_as_user_name", None) or getattr(j, "creator_user_name", None)
        if user and "@" in str(user):          # a human, not an SP application id
            offenders.append(f"{name} — run_as {user}")
    if offenders:
        return Result("1.1", "Deployed jobs run as a service principal", FAIL,
                      f"{len(offenders)} job(s) run as a human user. Off-boarding "
                      "or rotating that person breaks the ownership chain.",
                      _cap(offenders))
    return Result("1.1", "Deployed jobs run as a service principal", PASS,
                  "All matched jobs run as a service principal.")


def check_clusters_on_demand_and_tagged(w, prefix) -> Result:
    """1.3 — every job cluster is ON_DEMAND and carries cost-allocation tags.

    The changelog records DAB occasionally creating SPOT_WITH_FALLBACK clusters
    despite the YAML saying otherwise, which is exactly why this is asserted
    post-deploy rather than trusted from source."""
    spot, untagged = [], []
    for j in _jobs(w, prefix):
        s = j.settings
        name = getattr(s, "name", str(j.job_id))
        job_tags = {k.lower() for k in (getattr(s, "tags", None) or {})}
        for jc in (getattr(s, "job_clusters", None) or []):
            spec = getattr(jc, "new_cluster", None)
            if spec is None:
                continue
            for attr in ("aws_attributes", "azure_attributes", "gcp_attributes"):
                cloud = getattr(spec, attr, None)
                avail = str(getattr(cloud, "availability", "") or "")
                if avail and "SPOT" in avail.upper():
                    spot.append(f"{name} / {jc.job_cluster_key} — {avail}")
            tags = job_tags | {k.lower() for k in (getattr(spec, "custom_tags", None) or {})}
            missing = [t for t in REQUIRED_TAGS if t not in tags]
            if missing:
                untagged.append(f"{name} / {jc.job_cluster_key} — missing {','.join(missing)}")
    problems = spot + untagged
    if problems:
        return Result("1.3", "Job clusters are ON_DEMAND and cost-tagged", FAIL,
                      f"{len(spot)} spot-availability cluster(s), "
                      f"{len(untagged)} missing required tags {REQUIRED_TAGS}.",
                      _cap(problems))
    return Result("1.3", "Job clusters are ON_DEMAND and cost-tagged", PASS,
                  "All job clusters are on-demand and carry the required tags.")


def check_no_plaintext_secrets(w, prefix) -> Result:
    """3.1 — job definitions must carry no plaintext credentials.

    The checklist's acceptance criterion is literally "an API dump of job
    definitions contains no plaintext tokens", so dump and scan."""
    offenders = []
    for j in _jobs(w, prefix):
        s = j.settings
        name = getattr(s, "name", str(j.job_id))
        try:
            blob = s.as_dict() if hasattr(s, "as_dict") else {}
        except Exception:  # noqa: BLE001 — a job we can't serialize shouldn't abort the scan
            continue

        def walk(node, path=""):
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(v, f"{path}.{k}" if path else str(k))
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")
            elif isinstance(node, str):
                key = path.rsplit(".", 1)[-1]
                if (_SECRETISH.search(key)
                        and not _SECRET_REF.search(node)
                        and not _PLACEHOLDER.match(node.strip())):
                    offenders.append(f"{name} — {path} (plaintext value, {len(node)} chars)")

        walk(blob)
    if offenders:
        return Result("3.1", "No plaintext credentials in job definitions", FAIL,
                      f"{len(offenders)} credential-shaped setting(s) hold a literal "
                      "value. These are readable by anyone with job-read access; "
                      "move them to a secret scope and reference {{secrets/...}}.",
                      _cap(offenders))
    return Result("3.1", "No plaintext credentials in job definitions", PASS,
                  "No credential-shaped job settings hold literal values.")


def check_mcp_app_permissions(w, mcp_app_name) -> Result:
    """2.2 (live half) — the deployed MCP app's grants, as the workspace has them.

    Source can say one thing and the workspace another: permissions drift by hand
    edit, and the bundle is only re-asserted on redeploy."""
    try:
        app = w.apps.get(name=mcp_app_name)
    except Exception as e:  # noqa: BLE001
        return Result("2.2", "Deployed MCP app is not shared broadly", SKIP,
                      f"App '{mcp_app_name}' not readable ({type(e).__name__}).")
    try:
        perms = w.apps.get_permissions(app_name=app.name)
        acls = getattr(perms, "access_control_list", None) or []
    except Exception as e:  # noqa: BLE001
        return Result("2.2", "Deployed MCP app is not shared broadly", SKIP,
                      f"Permissions not readable ({type(e).__name__}).")
    broad = [f"{a.group_name} — {[str(p.permission_level) for p in (a.all_permissions or [])]}"
             for a in acls
             if (a.group_name or "").strip().lower() in _BROAD_PRINCIPALS]
    if broad:
        return Result("2.2", "Deployed MCP app is not shared broadly", FAIL,
                      "Every workspace user can invoke every capability the app SP "
                      "is entitled to — there is no per-caller authorization yet.",
                      broad)
    return Result("2.2", "Deployed MCP app is not shared broadly", PASS,
                  f"{len(acls)} grant(s), none to a broad principal.")


# ─── driver ─────────────────────────────────────────────────────────────────

def run(args) -> list[Result]:
    results = [check_bundle_run_as(), check_hardcoded_defaults(),
               check_mcp_broad_share_declared()]
    if args.source_only:
        return results

    try:
        from databricks.sdk import WorkspaceClient
    except ImportError:
        results.append(Result("—", "Live workspace checks", SKIP,
                              "databricks-sdk not installed (pip install databricks-sdk), "
                              "or run with --source-only."))
        return results
    try:
        w = WorkspaceClient(profile=args.profile) if args.profile else WorkspaceClient()
        w.current_user.me()
    except Exception as e:  # noqa: BLE001
        results.append(Result("—", "Live workspace checks", SKIP,
                              f"Could not authenticate to the workspace ({type(e).__name__}: {e})."))
        return results

    results.append(check_jobs_run_as_sp(w, args.job_prefix))
    results.append(check_clusters_on_demand_and_tagged(w, args.job_prefix))
    results.append(check_no_plaintext_secrets(w, args.job_prefix))
    results.append(check_mcp_app_permissions(w, args.mcp_app_name))
    return results


_GLYPH = {PASS: "PASS", FAIL: "FAIL", SKIP: "SKIP"}


def report(results: list[Result]) -> None:
    width = max(len(r.title) for r in results) + 2
    print()
    print("Genesis Workbench — hardening checks")
    print("Acceptance criteria from HARDENING_CHECKLIST.md, executed.")
    print("=" * (width + 20))
    for r in results:
        print(f"[{_GLYPH[r.status]}] {r.item:<5} {r.title}")
        if r.detail:
            print(f"        {r.detail}")
        for e in r.evidence:
            print(f"          · {e}")
    counts = {s: sum(1 for r in results if r.status == s) for s in (PASS, FAIL, SKIP)}
    print("=" * (width + 20))
    print(f"{counts[PASS]} passed · {counts[FAIL]} failed · {counts[SKIP]} skipped")
    if counts[FAIL]:
        print("\nFailures are findings, not errors — each maps to a numbered "
              "workstream in HARDENING_CHECKLIST.md with effort and acceptance criteria.")
    print()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source-only", action="store_true",
                   help="run only checks that need no workspace credentials")
    p.add_argument("--json", action="store_true", help="emit JSON (for CI)")
    p.add_argument("--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"),
                   help="Databricks CLI profile (default: DEFAULT / env)")
    p.add_argument("--job-prefix", default="gwb",
                   help="only inspect jobs whose name contains this (default: gwb)")
    p.add_argument("--mcp-app-name", default="mcp-genesis-workbench",
                   help="deployed MCP app name")
    args = p.parse_args()

    try:
        results = run(args)
    except Exception as e:  # noqa: BLE001
        print(f"hardening_check: could not run ({type(e).__name__}: {e})", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"results": [r.as_dict() for r in results]}, indent=2))
    else:
        report(results)
    return 1 if any(r.status == FAIL for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
