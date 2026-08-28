#!/bin/bash
# sync_dashboards.sh — pull UI edits back into the repo before deploying.
#
# Lakeview dashboards are editable in the workspace, and DAB refuses to deploy once
# a dashboard has drifted ("has been modified remotely"). Forcing past that silently
# discards whatever was changed in the UI. This script does the opposite: it exports
# the live dashboard over the repo copy, so a UI edit lands in git as a reviewable
# diff and the next deploy is a no-op instead of a conflict.
#
# Only bundle-managed dashboards with a checked-in .lvdash.json are synced.
# Templated dashboards (*.lvdash.json.tmpl) are skipped — they are generated, so the
# workspace copy has catalog/schema baked in and would clobber the placeholders.
#
# Usage: ./sync_dashboards.sh [profile]
set -e
PROFILE=${1:-DEFAULT}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

changed=0
shopt -s nullglob
for f in "$HERE"/*.lvdash.json; do
    base="$(basename "$f")"
    [ -f "$HERE/$base.tmpl" ] && continue   # generated — never sync back

    # Match on the display_name declared in the sibling .yml for this JSON.
    display=$(grep -h -B4 "file_path: $base" "$HERE"/*.yml 2>/dev/null \
              | grep 'display_name:' | head -1 | sed 's/.*display_name: *"\?\([^"]*\)"\?.*/\1/')
    [ -z "$display" ] && continue

    id=$(databricks lakeview list --profile "$PROFILE" --output json 2>/dev/null \
         | jq -r --arg d "$display" '.[]? | select(.display_name==$d) | .dashboard_id' | head -1)
    [ -z "$id" ] && continue   # not deployed yet — nothing to pull

    tmp="$(mktemp)"
    if ! databricks lakeview get "$id" --profile "$PROFILE" --output json 2>/dev/null \
         | jq -r '.serialized_dashboard' > "$tmp"; then
        rm -f "$tmp"; continue
    fi
    # jq . normalises formatting so only real content changes show up as a diff
    if jq -e . "$tmp" >/dev/null 2>&1 && ! jq -S . "$tmp" | diff -q - <(jq -S . "$f") >/dev/null 2>&1; then
        jq . "$tmp" > "$f"
        echo "  pulled UI changes into $base — review with 'git diff'"
        changed=$((changed + 1))
    fi
    rm -f "$tmp"
done

[ "$changed" -eq 0 ] && echo "  dashboards in sync"
exit 0
