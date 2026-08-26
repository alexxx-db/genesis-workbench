#!/bin/bash
# render_dashboards.sh — expand dashboard templates before `bundle deploy`.
#
# DAB does NOT interpolate ${var.*} inside a dashboard's file_path JSON; it hands the
# file to terraform, which then reads ${...} as its own interpolation and fails with
# `invalid dependency "${var.core_catalog_name}", no such node ""`. So any dashboard
# whose queries reference the GWB catalog/schema is kept as a .tmpl here and rendered
# to a concrete .lvdash.json at deploy time. deploy.sh and update.sh both call this.
#
# Usage: ./render_dashboards.sh <catalog> <schema>
set -e
CATALOG=${1:?usage: render_dashboards.sh <catalog> <schema>}
SCHEMA=${2:?missing schema}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

shopt -s nullglob
for tmpl in "$HERE"/*.lvdash.json.tmpl; do
    out="${tmpl%.tmpl}"
    sed -e "s/__CATALOG__/$CATALOG/g" -e "s/__SCHEMA__/$SCHEMA/g" "$tmpl" > "$out"
    echo "  rendered $(basename "$out")"
done
