"""Unit tests for the reference-basis contract.

The guarantees worth protecting:
  - every model-backed curated node declares a basis (a silent gap is worse than
    a wrong one, because nobody notices it),
  - IO/transform nodes declare none (no model, so no claim),
  - the basis survives the node_catalog round-trip, and a row published before
    the field existed degrades to "undeclared" rather than to a wrong value,
  - the two lookup tables never disagree about the same underlying model.

Run: pytest tests/test_reference_basis.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from genesis_workbench.builtin_nodes import (  # noqa: E402
    CURATED_BY_ENDPOINT,
    CURATED_BY_JOB,
    CURATED_BY_TYPE,
    CURATED_NODES,
)
from genesis_workbench.node_catalog import (  # noqa: E402
    NodeCategory,
    node_from_dict,
    node_to_dict,
)
from genesis_workbench.reference_basis import (  # noqa: E402
    BASIS_BY_NODE_TYPE,
    BASIS_BY_UC_SHORT,
    UNDECLARED,
    Scope,
    basis_for_node_type,
    basis_for_uc_short,
)

_MODEL_BACKED = (NodeCategory.ENDPOINT, NodeCategory.BATCH)
_VALID_SCOPES = {Scope.AGNOSTIC, Scope.MULTI, Scope.HUMAN, Scope.HOST, Scope.USER}


# ── coverage ────────────────────────────────────────────────────────────────
def test_every_model_backed_node_declares_a_basis():
    missing = [n.type for n in CURATED_NODES
               if n.category in _MODEL_BACKED and not n.reference_basis]
    assert not missing, f"model-backed nodes with no reference basis: {missing}"


def test_io_and_transform_nodes_declare_none():
    """No model behind them, so no claim to make."""
    wrong = [n.type for n in CURATED_NODES
             if n.category not in _MODEL_BACKED and n.reference_basis]
    assert not wrong, f"non-model nodes carrying a basis: {wrong}"


def test_scopes_are_from_the_declared_vocabulary():
    bad = [(n.type, n.basis_scope) for n in CURATED_NODES
           if n.reference_basis and n.basis_scope not in _VALID_SCOPES]
    assert not bad, f"nodes with an unrecognised basis_scope: {bad}"


def test_basis_table_has_no_orphan_node_keys():
    """A key in the table that matches no node is a typo — it would silently stop
    stamping the node it was meant for."""
    orphans = sorted(set(BASIS_BY_NODE_TYPE) - set(CURATED_BY_TYPE))
    assert not orphans, f"basis authored for unknown node types: {orphans}"


# ── the lookups agree ───────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "node_type,uc_short",
    [("esmfold", "esmfold"), ("mhcflurry", "mhcflurry_v2"), ("netsolp", "netsolp_v1"),
     ("pltnum", "pltnum_v1"), ("deepstabp", "deepstabp_v1"), ("kermt_admet", "kermt_admet"),
     ("chemprop_clintox", "chemprop_clintox"), ("diffdock", "diffdock")],
)
def test_node_and_uc_tables_agree(node_type, uc_short):
    """The same model reached by either namespace must give the same answer."""
    assert basis_for_node_type(node_type) is basis_for_uc_short(uc_short)


def test_unknown_keys_are_undeclared_not_guessed():
    assert basis_for_node_type("no_such_node") is UNDECLARED
    assert basis_for_uc_short("no_such_model") is UNDECLARED
    assert not UNDECLARED.is_declared


def test_uc_lookup_is_case_insensitive():
    assert basis_for_uc_short("MHCflurry_V2") is basis_for_uc_short("mhcflurry_v2")


# ── the claims that matter for a non-human-species customer ─────────────────
def test_human_only_capabilities_are_flagged_human():
    """These are the ones that must not silently transfer to a veterinary target."""
    for t in ("mhcflurry", "variant_annotation", "scimilarity_get_embedding",
              "chemprop_clintox"):
        assert basis_for_node_type(t).scope == Scope.HUMAN, t


def test_species_agnostic_capabilities_are_flagged_agnostic():
    for t in ("esmfold", "proteinmpnn", "alphafold2", "variant_calling", "gwas"):
        assert basis_for_node_type(t).scope == Scope.AGNOSTIC, t


def test_finetunable_capabilities_point_at_user_data():
    for t in ("kermt_admet", "kermt_finetune", "esm2_finetune"):
        assert basis_for_node_type(t).scope == Scope.USER, t


# ── serialization ───────────────────────────────────────────────────────────
def test_basis_round_trips_through_the_catalog_row():
    node = CURATED_BY_TYPE["mhcflurry"]
    back = node_from_dict(node_to_dict(node))
    assert back.reference_basis == node.reference_basis
    assert back.basis_scope == node.basis_scope


def test_legacy_row_without_basis_degrades_to_undeclared():
    """A catalog published by an older wheel must not produce a wrong claim."""
    d = node_to_dict(CURATED_BY_TYPE["mhcflurry"])
    d.pop("reference_basis"), d.pop("basis_scope")
    back = node_from_dict(d)
    assert back.reference_basis == "" and back.basis_scope == ""


# ── lookups are built from the stamped list ─────────────────────────────────
def test_endpoint_and_job_lookups_carry_the_basis():
    """Regression: these were built from the pre-stamp lists, which handed
    basis-less copies to the executor while the palette showed stamped ones."""
    mhc = CURATED_BY_ENDPOINT.get("MHCflurry Immunogenicity")
    assert mhc is not None and mhc.reference_basis
    enzyme = CURATED_BY_JOB.get("run_enzyme_optimization_gwb")
    assert enzyme is not None and enzyme.reference_basis
