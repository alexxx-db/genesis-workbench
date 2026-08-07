#!/usr/bin/env python3
"""Genesis Workbench — Python syntax gate.

Byte-compiles the Python that runs *off* Databricks — the app backend, the MCP
backend, the importable library package, and these scripts — so a syntax error
fails CI instead of a live app deploy or a wheel build. The library's runtime
modules are also exercised by the unit tests, but the FastAPI backends are not
imported anywhere in the test suite, so this is their only fast guard.

Databricks *notebooks* are deliberately skipped. A notebook exported as `.py`
carries a `# Databricks notebook source` first line and uses `%pip` / `%sql`
magics and `dbutils`, which are only valid inside the Databricks runtime and are
a SyntaxError to CPython. Compiling them here would be a false positive, so any
file whose first line is that marker is excluded.

Usage
-----
    python scripts/check_python_syntax.py            # default roots
    python scripts/check_python_syntax.py path ...    # explicit roots
    python scripts/check_python_syntax.py --json

Exit codes: 0 = everything compiles, 1 = at least one real syntax error.
"""
from __future__ import annotations

import argparse
import json
import py_compile
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

DEFAULT_ROOTS = (
    "modules/core/library/genesis_workbench/src",
    "modules/core/app/backend",
    "modules/core/mcp_app/backend",
    "scripts",
)
_SKIP_PARTS = {"node_modules", ".git", "dist", "build", ".venv", "__pycache__"}
_NOTEBOOK_MARKER = "# Databricks notebook source"


def _is_notebook(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8", errors="ignore") as fh:
            return fh.readline().strip() == _NOTEBOOK_MARKER
    except OSError:
        return False


def check(roots: list[str]) -> tuple[bool, dict]:
    errors: list[dict] = []
    compiled = skipped = 0
    for root in roots:
        base = REPO / root
        for path in sorted(base.rglob("*.py")):
            if _SKIP_PARTS & set(path.parts):
                continue
            if _is_notebook(path):
                skipped += 1
                continue
            try:
                py_compile.compile(str(path), doraise=True)
                compiled += 1
            except py_compile.PyCompileError as e:
                errors.append({"file": str(path.relative_to(REPO)),
                               "detail": str(e.msg)})
    return not errors, {"compiled": compiled, "skipped_notebooks": skipped,
                        "errors": errors}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("roots", nargs="*", default=list(DEFAULT_ROOTS),
                   help="directories to compile (default: backends, library, scripts)")
    p.add_argument("--json", action="store_true", help="emit JSON (for CI)")
    args = p.parse_args()

    ok, data = check(args.roots)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"\nPython syntax — {data['compiled']} compiled, "
              f"{data['skipped_notebooks']} Databricks notebook(s) skipped")
        print("=" * 52)
        for e in data["errors"]:
            print(f"[FAIL] {e['file']}")
            print(f"        {e['detail']}")
        print("=" * 52)
        print("all files compile\n" if ok else f"{len(data['errors'])} file(s) failed\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
