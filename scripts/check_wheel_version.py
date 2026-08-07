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

With --require-bump BASE_REF it additionally enforces the release rule from
CONTRIBUTING.md ("bump the wheel version whenever you change the wheel"): if
anything under the library's src/ tree differs from the merge-base with
BASE_REF but the pyproject version does not, the check fails. Uncommitted
changes count, so it works identically in a PR (vs the base branch) and on a
dirty local tree before committing.

Usage
-----
    python scripts/check_wheel_version.py                     # pin consistency
    python scripts/check_wheel_version.py --json               # machine-readable (CI)
    python scripts/check_wheel_version.py --require-bump origin/main   # PR gate

Exit codes: 0 = all pins match the library version (and, with --require-bump,
the version was bumped when src changed), 1 = a check failed / could not read.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
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


SRC_PREFIX = "modules/core/library/genesis_workbench/src/"


def _git(*argv: str) -> str:
    return subprocess.run(("git", *argv), cwd=REPO, check=True,
                          capture_output=True, text=True).stdout.strip()


def check_bump(base_ref: str) -> tuple[bool, dict]:
    """--require-bump: src/ changed relative to merge-base(base_ref) ⇒ the
    pyproject version must differ from the merge-base's version."""
    try:
        base = _git("merge-base", base_ref, "HEAD")
    except subprocess.CalledProcessError:
        base = base_ref                     # shallow/odd history — diff vs the ref itself
    # Two-arg diff (base vs worktree) so uncommitted edits count too.
    changed = [f for f in _git("diff", "--name-only", base).splitlines()
               if f.startswith(SRC_PREFIX)]
    head_version = library_version()
    if not changed:
        return True, {"base": base_ref, "src_changed": [],
                      "detail": "library src unchanged; no bump required"}
    base_pyproject = _git("show", f"{base}:{PYPROJECT.relative_to(REPO).as_posix()}")
    m = _VERSION_RE.search(base_pyproject)
    base_version = m.group(1) if m else None
    ok = head_version != base_version
    return ok, {"base": base_ref, "src_changed": changed,
                "base_version": base_version, "head_version": head_version,
                "detail": ("version bumped" if ok else
                           f"library src changed but version is still {head_version} — "
                           "bump it in pyproject.toml (and re-pin app/mcp requirements)")}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true", help="emit JSON (for CI)")
    p.add_argument("--require-bump", metavar="BASE_REF",
                   help="also fail if library src changed vs BASE_REF without a "
                        "version bump (e.g. origin/main)")
    args = p.parse_args()

    try:
        ok, data = check()
        bump_ok, bump = (True, None)
        if args.require_bump:
            bump_ok, bump = check_bump(args.require_bump)
            data["bump"] = bump
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
        if bump is not None:
            print(f"[{'PASS' if bump_ok else 'FAIL'}] version bump vs {bump['base']} "
                  f"({len(bump['src_changed'])} src file(s) changed)")
            print(f"        {bump['detail']}")
        print("=" * 52)
        if ok and bump_ok:
            print("All wheel version checks pass.\n")
        elif not ok:
            print("\nMismatch: bump the pins to match "
                  "modules/core/library/genesis_workbench/pyproject.toml, or run "
                  "modules/core/update.sh which rebuilds and re-stages the wheel.\n")
        else:
            print("\nThe wheel's source changed but its version did not — the deployed "
                  "app would silently import the stale cached wheel. Bump the version "
                  "in pyproject.toml and update the app/mcp requirements pins.\n")
    return 0 if ok and bump_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
