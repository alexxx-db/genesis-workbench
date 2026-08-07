#!/usr/bin/env python3
"""Genesis Workbench — bundle YAML parse gate.

Every module is a Databricks Asset Bundle whose behaviour is defined in YAML
(`databricks.yml`, `variables.yml`, and the `resources/*.yml` job/cluster/app
definitions). A malformed one is not caught until `databricks bundle deploy`
fails on the customer's workspace — the most expensive place to find it. This
gate parses them all up front so a bad indent or a dangling anchor fails CI
instead of a live deploy.

It only asserts that each file is *well-formed YAML*, not that it is a valid
bundle (that needs the Databricks CLI + a workspace; see the opt-in
bundle-validate job in .github/workflows/ci.yml). `${var.x}` interpolations are
opaque strings to a YAML parser, which is fine — we are checking syntax.

Usage
-----
    python scripts/check_bundle_yaml.py         # human-readable
    python scripts/check_bundle_yaml.py --json    # machine-readable (CI)

Exit codes: 0 = all files parse, 1 = at least one failed / could not run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODULES = REPO / "modules"

# Bundle-owned YAML. Globbed relative to modules/.
GLOBS = ("**/databricks.yml", "**/variables.yml", "**/resources/*.yml",
         "**/*.job.yml")
_SKIP_PARTS = {"node_modules", ".git", "dist", "build", ".venv"}


def _yaml_files() -> list[Path]:
    seen: set[Path] = set()
    for g in GLOBS:
        for p in MODULES.glob(g):
            if seen.isdisjoint({p}) and not (_SKIP_PARTS & set(p.parts)):
                seen.add(p)
    return sorted(seen)


def check() -> tuple[bool, list[dict]]:
    import yaml  # local import so --help works without PyYAML installed

    results: list[dict] = []
    ok = True
    for p in _yaml_files():
        rel = str(p.relative_to(REPO))
        try:
            # Bundle files are single-document; load_all tolerates multi-doc too.
            list(yaml.safe_load_all(p.read_text(encoding="utf-8")))
            results.append({"file": rel, "status": "PASS"})
        except Exception as e:  # noqa: BLE001
            ok = False
            results.append({"file": rel, "status": "FAIL",
                            "detail": f"{type(e).__name__}: {e}"})
    return ok, results


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true", help="emit JSON (for CI)")
    args = p.parse_args()

    try:
        ok, results = check()
    except Exception as e:  # noqa: BLE001
        print(f"check_bundle_yaml: could not run ({type(e).__name__}: {e})",
              file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"results": results}, indent=2))
    else:
        failures = [r for r in results if r["status"] == "FAIL"]
        print(f"\nBundle YAML parse — {len(results)} file(s) checked")
        print("=" * 52)
        for r in failures:
            print(f"[FAIL] {r['file']}")
            print(f"        {r['detail']}")
        print("=" * 52)
        print(f"{len(results) - len(failures)} passed · {len(failures)} failed\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
