#!/usr/bin/env python3
"""Genesis Workbench — wheel version-consistency guard.

`poetry build` (in modules/core/{deploy,update}.sh) emits
`genesis_workbench-<version>-py3-none-any.whl`, where <version> is
`[tool.poetry] version` in the library's pyproject.toml. That file is then
copied into app/backend/lib/ and mcp_app/backend/lib/, and each app's
requirements.txt pins the wheel by its *exact* filename.

If the library version is bumped but a requirements.txt pin is not (or vice
versa), the app silently installs a stale wheel — or fails to install because
the pinned filename no longer exists. That mismatch is a real, recurring bug
(the app imports an old genesis_workbench and behaves like the previous
release). It is also perfectly mechanical to catch, so CI catches it.

Usage
-----
    python scripts/check_wheel_version.py        # human-readable
    python scripts/check_wheel_version.py --json  # machine-readable (CI)

Exit codes: 0 = all pins match the library version, 1 = mismatch/could not read.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

PYPROJECT = REPO / "modules/core/library/genesis_workbench/pyproject.toml"
# Every requirements.txt that pins the wheel by exact filename.
REQUIREMENTS = (
    REPO / "modules/core/app/requirements.txt",
    REPO / "modules/core/mcp_app/requirements.txt",
)

_VERSION_RE = re.compile(r'^\s*version\s*=\s*["\']([^"\']+)["\']', re.M)
_WHEEL_RE = re.compile(r"genesis_workbench-([0-9][^-\s]*)-py3-none-any\.whl")


def library_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    m = _VERSION_RE.search(text)
    if not m:
        raise ValueError(f"no [tool.poetry] version found in {PYPROJECT}")
    return m.group(1)


def pinned_versions(path: Path) -> list[str]:
    """Every genesis_workbench wheel version pinned in a requirements file."""
    if not path.exists():
        return []
    return _WHEEL_RE.findall(path.read_text(encoding="utf-8"))


def check() -> tuple[bool, dict]:
    version = library_version()
    files: list[dict] = []
    ok = True
    for req in REQUIREMENTS:
        pins = pinned_versions(req)
        rel = str(req.relative_to(REPO))
        if not pins:
            ok = False
            files.append({"file": rel, "status": "FAIL",
                          "detail": "no genesis_workbench wheel pinned"})
            continue
        bad = [p for p in pins if p != version]
        if bad:
            ok = False
            files.append({"file": rel, "status": "FAIL", "pinned": pins,
                          "detail": f"pins {sorted(set(bad))} != library {version}"})
        else:
            files.append({"file": rel, "status": "PASS", "pinned": pins})
    return ok, {"library_version": version, "files": files}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true", help="emit JSON (for CI)")
    args = p.parse_args()

    try:
        ok, data = check()
    except Exception as e:  # noqa: BLE001
        print(f"check_wheel_version: could not run ({type(e).__name__}: {e})",
              file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"\nWheel version consistency — library is {data['library_version']}")
        print("=" * 52)
        for f in data["files"]:
            print(f"[{f['status']}] {f['file']}")
            if f.get("detail"):
                print(f"        {f['detail']}")
        print("=" * 52)
        if ok:
            print("All requirements pins match the library version.\n")
        else:
            print("\nMismatch: bump the pins to match "
                  "modules/core/library/genesis_workbench/pyproject.toml, or run "
                  "modules/core/update.sh which rebuilds and re-stages the wheel.\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
