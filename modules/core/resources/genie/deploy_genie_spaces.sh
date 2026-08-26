#!/bin/bash
# deploy_genie_spaces.sh — create/refresh the Genesis Workbench Genie spaces.
#
# Genie spaces are not yet a DAB resource type, so they are deployed by this
# script rather than by `databricks bundle deploy`. It is idempotent: an existing
# space with the same title is updated in place (its space_id is preserved, so
# saved conversations and shared links keep working).
#
# Usage:  ./deploy_genie_spaces.sh <catalog> <schema> <warehouse_id> [profile]
# Reads the same values deploy.sh already has in application.env.
set -e

CATALOG=${1:?usage: deploy_genie_spaces.sh <catalog> <schema> <warehouse_id> [profile]}
SCHEMA=${2:?missing schema}
WAREHOUSE_ID=${3:?missing warehouse_id}
PROFILE=${4:-DEFAULT}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Genie has no "instructions" field in the serialized payload — the description is
# what the model reads, so these are written as agent instructions, not blurbs.
read -r -d '' DESC_BIO <<'DESC' || true
Answers questions about the biomedical reference data loaded into Genesis Workbench.

Data available:
- repurposing_hub — 5.8K approved/investigational drugs with mechanism of action (moa), protein target, clinical_phase, disease_area and indication.
- target_binders — ChEMBL bioactivity: molecules with measured binding affinity (pchembl) against protein targets. Higher pchembl = more potent; ~6 is 1 micromolar.
- gene_sequences — 20K reviewed SwissProt human proteins with gene symbol, accession, protein name and sequence length.
- cellxgene_cell_counts — per-dataset cell counts for loaded CellxGene single-cell datasets.

Guidance:
- target and moa in repurposing_hub are free text; match with LIKE/ILIKE rather than equality (a drug may list several targets in one field).
- Gene symbols are uppercase (EGFR, PARP1). Compare case-insensitively.
- When asked for "strongest" or "most potent" binders, order by pchembl DESC.
- murcko_scaffold groups molecules into chemical series — use it for "how many distinct scaffolds" questions.
- Never return the full `sequence` column unless explicitly asked; it is very long. Prefer seq_length.
DESC

read -r -d '' DESC_PLATFORM <<'DESC' || true
Answers questions about what Genesis Workbench itself contains — which scientific models are registered, which are deployed, and who has access.

Data available:
- models — every registered model. model_category is the owning module (single_cell, small_molecule, large_molecule, genomics). is_model_deployed flags a live endpoint.
- model_deployments — one row per serving endpoint; join to models on model_id.
- batch_models — models that run as scheduled batch jobs instead of realtime endpoints.
- node_catalog — AI Canvas / Vortex workflow building blocks, by module and kind.
- app_permissions — module/submodule access grants by group and access_level.

Guidance:
- Always filter is_active = true unless the user explicitly asks about retired models or torn-down endpoints.
- "Module" and model_category mean the same thing.
- Join models to model_deployments on models.model_id = model_deployments.model_id.
- model_added_date and model_deployed_date support "when" and "recently" questions.
DESC

create_or_update() {
  # Prints ONLY the space_id on stdout; all progress goes to stderr so the caller
  # can capture the id with command substitution.
  local title="$1" file="$2" desc="$3"
  local payload
  payload=$(sed -e "s/\${CATALOG}/$CATALOG/g" -e "s/\${SCHEMA}/$SCHEMA/g" "$HERE/$file")

  local existing
  existing=$(databricks genie list-spaces --profile "$PROFILE" --output json 2>/dev/null \
    | jq -r --arg t "$title" '.spaces[]? | select(.title==$t) | .space_id' | head -1)

  if [ -n "$existing" ]; then
    echo "  updating $existing — $title" >&2
    databricks genie update-space "$existing" --profile "$PROFILE" \
      --title "$title" --description "$desc" \
      --serialized-space "$payload" >/dev/null
    printf '%s' "$existing"
  else
    echo "  creating — $title" >&2
    databricks genie create-space "$WAREHOUSE_ID" "$payload" --profile "$PROFILE" \
      --title "$title" --description "$desc" --output json \
      | jq -r '.space_id' | tr -d '\n'
  fi
}

echo "▶️ Deploying Genie spaces against $CATALOG.$SCHEMA (warehouse $WAREHOUSE_ID)"
BIO_ID=$(create_or_update "Genesis Workbench — Biomedical Data Explorer" \
  "biomedical_data_explorer.space.json" "$DESC_BIO")
PLAT_ID=$(create_or_update "Genesis Workbench — Platform & Model Catalog" \
  "platform_model_catalog.space.json" "$DESC_PLATFORM")

echo ""
echo "✅ Genie spaces ready:"
echo "   Biomedical Data Explorer : $BIO_ID"
echo "   Platform & Model Catalog : $PLAT_ID"
