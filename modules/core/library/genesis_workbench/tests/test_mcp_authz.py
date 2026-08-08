"""Per-caller MCP authorization (mcp_authz) — pure-logic tests, no workspace.

The seams that touch the outside world (SCIM group resolution, the
app_permissions query) are injectable, so these tests cover the decision
matrix: modes, identity presence, admin bypass, grant levels, fallback module,
caching, and the audit-worthy deny reasons.
"""
from __future__ import annotations

import pandas as pd
import pytest

from genesis_workbench import mcp_authz as az
from genesis_workbench.mcp_authz import (
    CallerIdentity,
    authorize,
    clear_caches,
    identity_from_headers,
    module_grants,
    resolve_groups,
)

ALICE = CallerIdentity(email="alice@corp.com", access_token="tok")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    """Every test starts with default mode/level, empty caches, no ambient caller."""
    for var in ("MCP_AUTHZ_MODE", "MCP_REQUIRED_ACCESS_LEVEL", "GWB_ADMIN_GROUP"):
        monkeypatch.delenv(var, raising=False)
    clear_caches()
    yield
    clear_caches()


# ─── identity parsing ────────────────────────────────────────────────────────

def test_identity_from_headers_full():
    ident = identity_from_headers({
        "X-Forwarded-Email": "a@b.com",
        "X-Forwarded-Preferred-Username": "a",
        "X-Forwarded-User": "123",
        "X-Forwarded-Access-Token": "tok",
    })
    assert ident.email == "a@b.com"
    assert ident.username == "a"
    assert ident.user_id == "123"
    assert ident.access_token == "tok"
    assert ident.label == "a@b.com"


def test_identity_headers_case_insensitive():
    ident = identity_from_headers({"x-forwarded-email": "a@b.com"})
    assert ident is not None and ident.email == "a@b.com"


def test_no_identity_headers_is_none():
    assert identity_from_headers({"user-agent": "curl"}) is None


# ─── modes ───────────────────────────────────────────────────────────────────

def test_default_mode_is_enforce():
    assert az.authz_mode() == "enforce"


def test_garbage_mode_falls_back_to_enforce(monkeypatch):
    monkeypatch.setenv("MCP_AUTHZ_MODE", "yolo")
    assert az.authz_mode() == "enforce"


def test_disabled_mode_allows_without_identity(monkeypatch):
    monkeypatch.setenv("MCP_AUTHZ_MODE", "disabled")
    d = authorize("single_cell", identity=None, audit=False)
    assert d.allowed and "disabled" in d.reason


def test_enforce_denies_without_identity():
    d = authorize("single_cell", identity=None, audit=False)
    assert not d.allowed
    assert "X-Forwarded" in d.reason


def test_permissive_allows_without_identity(monkeypatch):
    monkeypatch.setenv("MCP_AUTHZ_MODE", "permissive")
    d = authorize("single_cell", identity=None, audit=False)
    assert d.allowed


# ─── admin bypass ────────────────────────────────────────────────────────────

def test_admin_group_bypasses_grants():
    d = authorize("genomics", identity=ALICE, audit=False,
                  _resolve_groups=lambda i: ["genesis-admin-group"],
                  _module_grants=lambda g: {})
    assert d.allowed and "admin group" in d.reason


def test_workspace_admins_bypass():
    d = authorize("genomics", identity=ALICE, audit=False,
                  _resolve_groups=lambda i: ["admins"],
                  _module_grants=lambda g: {})
    assert d.allowed


def test_custom_admin_group_env(monkeypatch):
    monkeypatch.setenv("GWB_ADMIN_GROUP", "plat-admins")
    d = authorize("genomics", identity=ALICE, audit=False,
                  _resolve_groups=lambda i: ["plat-admins"],
                  _module_grants=lambda g: {})
    assert d.allowed


# ─── grant matching ──────────────────────────────────────────────────────────

def _authz(module, grants, groups=("researchers",), **kw):
    return authorize(module, identity=ALICE, audit=False,
                     _resolve_groups=lambda i: list(groups),
                     _module_grants=lambda g: grants, **kw)


def test_view_grant_allows():
    assert _authz("single_cell", {"single_cell": "view"}).allowed


def test_full_grant_satisfies_view_requirement():
    assert _authz("single_cell", {"single_cell": "full"}).allowed


def test_missing_module_grant_denies_with_remediation():
    d = _authz("genomics", {"single_cell": "view"})
    assert not d.allowed
    assert "genomics" in d.reason
    assert "grant_module_access" in d.reason      # tells the admin how to fix it


def test_view_grant_fails_full_requirement(monkeypatch):
    monkeypatch.setenv("MCP_REQUIRED_ACCESS_LEVEL", "full")
    assert not _authz("single_cell", {"single_cell": "view"}).allowed
    assert _authz("single_cell", {"single_cell": "full"}).allowed


def test_capability_without_module_gated_as_core():
    assert _authz(None, {"core": "view"}).allowed
    d = _authz(None, {"single_cell": "view"})
    assert not d.allowed and d.module == "core"


def test_permissive_records_would_deny(monkeypatch):
    monkeypatch.setenv("MCP_AUTHZ_MODE", "permissive")
    d = _authz("genomics", {})
    assert d.allowed and "would deny" in d.reason


def test_unresolvable_groups_deny():
    d = authorize("single_cell", identity=ALICE, audit=False,
                  _resolve_groups=lambda i: [],
                  _module_grants=lambda g: {})
    assert not d.allowed


# ─── caching ─────────────────────────────────────────────────────────────────

def test_resolve_groups_caches_per_identity():
    calls = []

    def fetch(identity):
        calls.append(identity.email)
        return ["g1"]

    assert resolve_groups(ALICE, _user_path=fetch) == ["g1"]
    assert resolve_groups(ALICE, _user_path=fetch) == ["g1"]
    assert len(calls) == 1                       # second hit served from cache
    clear_caches()
    resolve_groups(ALICE, _user_path=fetch)
    assert len(calls) == 2


def test_resolve_groups_failure_is_empty_not_raise():
    def boom(identity):
        raise RuntimeError("scim down")
    assert resolve_groups(ALICE, _user_path=boom) == []


def test_module_grants_cached_by_group_set():
    calls = []

    def fetch(groups):
        calls.append(tuple(groups))
        return {"single_cell": "view"}

    assert module_grants(["a", "b"], _fetch=fetch) == {"single_cell": "view"}
    assert module_grants(["b", "a"], _fetch=fetch) == {"single_cell": "view"}
    assert len(calls) == 1                       # order-insensitive cache key


# ─── the SQL seam ────────────────────────────────────────────────────────────

def test_fetch_module_grants_binds_groups_and_keeps_strongest(monkeypatch):
    captured = {}

    def fake_select(query, parameters=None):
        captured["query"] = query
        captured["params"] = parameters
        return pd.DataFrame([
            {"module_name": "single_cell", "access_level": "view"},
            {"module_name": "single_cell", "access_level": "full"},
            {"module_name": "genomics", "access_level": "view"},
        ])

    monkeypatch.setenv("CORE_CATALOG_NAME", "cat")
    monkeypatch.setenv("CORE_SCHEMA_NAME", "sch")
    import genesis_workbench.workbench as wb
    monkeypatch.setattr(wb, "execute_select_query", fake_select)

    grants = az._fetch_module_grants(["team a", "team-b"])
    assert grants == {"single_cell": "full", "genomics": "view"}
    # groups are bound parameters, never string-interpolated
    assert "arrays_overlap" in captured["query"]
    assert ":grp0" in captured["query"] and ":grp1" in captured["query"]
    assert captured["params"] == {"grp0": "team a", "grp1": "team-b"}
    assert "cat.sch.app_permissions" in captured["query"]


def test_fetch_module_grants_empty_groups_no_query(monkeypatch):
    def explode(*a, **k):
        raise AssertionError("must not query with no groups")
    import genesis_workbench.workbench as wb
    monkeypatch.setattr(wb, "execute_select_query", explode)
    assert az._fetch_module_grants([]) == {}


# ─── contextvar plumbing ─────────────────────────────────────────────────────

def test_caller_contextvar_roundtrip():
    assert az.current_caller() is None
    token = az.set_caller(ALICE)
    try:
        assert az.current_caller() is ALICE
    finally:
        az.reset_caller(token)
    assert az.current_caller() is None
