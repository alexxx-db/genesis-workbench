"""Per-caller authorization for the Genesis Workbench MCP server
(HARDENING_CHECKLIST.md 2.1).

The MCP app executes every capability as its own service principal, so the SP's
entitlements say nothing about who *asked*. This module decides, per tool call,
whether the human (or agent acting for them) behind the request may run the
capability — using the same policy store the UI already enforces: the
``app_permissions`` table managed by ``privilege_management`` and seeded by the
``setup_permissions`` task of the ``initialize_core`` job.

How a decision is made
----------------------
1. **Identity** comes from the Databricks Apps reverse proxy, which
   authenticates every request via workspace SSO and injects
   ``X-Forwarded-Email`` / ``X-Forwarded-Access-Token`` &c. — the identical
   trust model the UI backend uses (``app/auth.py``). The MCP server captures
   the headers in an ASGI middleware and parks them in a contextvar for the
   duration of the request.
2. **Groups** are resolved via SCIM — with the caller's own forwarded token
   when present (which simultaneously proves the token is live), else by the
   app SP looking the user up by email. Cached with a TTL so one agent
   conversation costs one lookup, not one per tool call.
3. **Policy**: the caller needs an active ``module_access`` row for the
   capability's module (``large_molecule`` / ``small_molecule`` /
   ``single_cell`` / ``genomics``; capabilities without a module count as
   ``core``) at ``MCP_REQUIRED_ACCESS_LEVEL`` (default ``view``). Members of
   the admin group (``GWB_ADMIN_GROUP``, default ``genesis-admin-group``) and
   workspace ``admins`` are always allowed.
4. Every decision is **audited** as a structured log line (Databricks Apps
   retains app logs); denials raise with the exact grant that is missing.

Modes (``MCP_AUTHZ_MODE``): ``enforce`` (default) denies unauthorized calls;
``permissive`` logs the would-be denial but allows (rollout/dry-run);
``disabled`` restores the legacy SP-only behavior. The app accessor list
(mcp_app.yml) remains the outer gate — this module decides *which* of the
admitted users may run *what*.
"""
from __future__ import annotations

import json
import logging
import os
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Callable, Mapping

logger = logging.getLogger("gwb_mcp.authz")

MODE_ENFORCE, MODE_PERMISSIVE, MODE_DISABLED = "enforce", "permissive", "disabled"

# Capabilities that declare no module (rare) are gated as this pseudo-module.
FALLBACK_MODULE = "core"

_caller: ContextVar["CallerIdentity | None"] = ContextVar("gwb_mcp_caller", default=None)


@dataclass(frozen=True)
class CallerIdentity:
    """What the Databricks Apps proxy tells us about the caller."""
    email: str | None = None
    username: str | None = None
    user_id: str | None = None
    access_token: str | None = None

    @property
    def label(self) -> str:
        return self.email or self.username or self.user_id or "<unidentified>"

    @property
    def cache_key(self) -> str:
        return self.email or self.username or self.user_id or ""


@dataclass
class AuthzDecision:
    allowed: bool
    reason: str
    caller: str = "<unidentified>"
    module: str | None = None
    groups: list[str] = field(default_factory=list)
    mode: str = MODE_ENFORCE


def identity_from_headers(headers: Mapping[str, str]) -> CallerIdentity | None:
    """Parse the Apps proxy identity headers (case-insensitive). Returns None
    when none are present — i.e. the request did not come through the proxy."""
    h = {k.lower(): v for k, v in headers.items()}
    email = h.get("x-forwarded-email")
    username = h.get("x-forwarded-preferred-username")
    user_id = h.get("x-forwarded-user")
    token = h.get("x-forwarded-access-token")
    if not any((email, username, user_id, token)):
        return None
    return CallerIdentity(email=email, username=username, user_id=user_id,
                          access_token=token)


def set_caller(identity: CallerIdentity | None):
    """Park the request's identity in the contextvar (returns reset token)."""
    return _caller.set(identity)


def reset_caller(token) -> None:
    _caller.reset(token)


def current_caller() -> CallerIdentity | None:
    return _caller.get()


def authz_mode() -> str:
    mode = os.environ.get("MCP_AUTHZ_MODE", MODE_ENFORCE).strip().lower()
    return mode if mode in (MODE_ENFORCE, MODE_PERMISSIVE, MODE_DISABLED) else MODE_ENFORCE


def required_level() -> str:
    lvl = os.environ.get("MCP_REQUIRED_ACCESS_LEVEL", "view").strip().lower()
    return lvl if lvl in ("view", "full") else "view"


def admin_groups() -> set[str]:
    """Groups whose members may run everything. `admins` is the workspace
    admins group — the operational escape hatch that can never be locked out."""
    return {os.environ.get("GWB_ADMIN_GROUP", "genesis-admin-group"), "admins"}


# ─── TTL cache (identity → groups, groups → grants) ─────────────────────────

class _TTLCache:
    def __init__(self, ttl_seconds: float):
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, key: str):
        hit = self._store.get(key)
        if hit is None:
            return None
        ts, value = hit
        if time.monotonic() - ts > self.ttl:
            self._store.pop(key, None)
            return None
        return value

    def put(self, key: str, value) -> None:
        self._store[key] = (time.monotonic(), value)

    def clear(self) -> None:
        self._store.clear()


def _cache_ttl() -> float:
    try:
        return float(os.environ.get("MCP_AUTHZ_CACHE_TTL", "300"))
    except ValueError:
        return 300.0


_groups_cache = _TTLCache(_cache_ttl())
_grants_cache = _TTLCache(_cache_ttl())


def clear_caches() -> None:
    """For tests and for forcing a re-read after a grant change."""
    _groups_cache.clear()
    _grants_cache.clear()


# ─── group resolution (SCIM) ─────────────────────────────────────────────────

def _scim_groups_with_user_token(identity: CallerIdentity) -> list[str]:
    """Resolve groups with the caller's own token — also proves the token is
    live, because a revoked/forged token cannot answer SCIM /Me."""
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient(host=os.environ.get("DATABRICKS_HOST"),
                        token=identity.access_token, auth_type="pat")
    me = w.current_user.me()
    groups = [g.display for g in (me.groups or []) if g.display]
    if not groups and me.id:
        # Some SCIM backends omit groups on /Me; the per-user read has them.
        detail = w.users.get(id=me.id)
        groups = [g.display for g in (detail.groups or []) if g.display]
    return groups


def _scim_groups_via_app_sp(identity: CallerIdentity) -> list[str]:
    """No user token forwarded — look the user up as the app SP (ambient
    auth). Requires the SP to be able to read users; failures mean 'unknown'."""
    from databricks.sdk import WorkspaceClient
    if not identity.email:
        return []
    w = WorkspaceClient()
    hits = list(w.users.list(filter=f'userName eq "{identity.email}"',
                             attributes="id,userName,groups", count=1))
    if not hits:
        return []
    return [g.display for g in (hits[0].groups or []) if g.display]


def resolve_groups(identity: CallerIdentity,
                   _user_path: Callable = _scim_groups_with_user_token,
                   _sp_path: Callable = _scim_groups_via_app_sp) -> list[str]:
    """The caller's workspace groups, TTL-cached. Empty list = could not
    resolve (treated as 'no entitlements', not as an error)."""
    key = identity.cache_key
    if key:
        cached = _groups_cache.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
    try:
        groups = _user_path(identity) if identity.access_token else _sp_path(identity)
    except Exception as e:  # noqa: BLE001 — an unresolvable caller is denied, not crashed
        logger.warning("group resolution failed for %s: %s", identity.label, e)
        groups = []
    if key:
        _groups_cache.put(key, groups)
    return groups


# ─── policy (app_permissions) ────────────────────────────────────────────────

def _fetch_module_grants(groups: list[str]) -> dict[str, str]:
    """Active module_access grants overlapping the caller's groups, as
    {module_name: best_access_level}. One query per caller per TTL window."""
    from .workbench import execute_select_query, sql_in_params

    if not groups:
        return {}
    in_clause, params = sql_in_params("grp", groups)
    catalog = os.environ["CORE_CATALOG_NAME"]
    schema = os.environ["CORE_SCHEMA_NAME"]
    # Groups are bound parameters; the identifiers come from the same env the
    # whole library already trusts (set by initialize()).
    query = f"""
        SELECT module_name, access_level
        FROM {catalog}.{schema}.app_permissions
        WHERE permission_type = 'module_access'
          AND submodule_name IS NULL
          AND is_active = true
          AND arrays_overlap(groups, array{in_clause})
    """
    df = execute_select_query(query, parameters=params)
    grants: dict[str, str] = {}
    for _, row in df.iterrows():
        m, lvl = str(row["module_name"]), str(row["access_level"]).lower()
        if grants.get(m) != "full":       # keep the strongest level seen
            grants[m] = lvl
    return grants


def module_grants(groups: list[str],
                  _fetch: Callable = _fetch_module_grants) -> dict[str, str]:
    key = "|".join(sorted(groups))
    cached = _grants_cache.get(key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    grants = _fetch(groups)
    _grants_cache.put(key, grants)
    return grants


def _level_satisfies(have: str, need: str) -> bool:
    return have == "full" or have == need


# ─── the decision ────────────────────────────────────────────────────────────

def authorize(module: str | None,
              identity: CallerIdentity | None = None,
              *,
              audit: bool = True,
              _resolve_groups: Callable = resolve_groups,
              _module_grants: Callable = module_grants) -> AuthzDecision:
    """Decide whether the current caller may run a capability of `module`.

    Never raises: returns a decision the caller enforces (the MCP layer raises
    PermissionError on deny-in-enforce). Decisions are audit-logged unless
    audit=False (used for advisory checks like list_capabilities annotations,
    which would otherwise flood the log with non-execution decisions)."""
    mode = authz_mode()
    module = module or FALLBACK_MODULE
    if identity is None:
        identity = current_caller()

    def done(allowed: bool, reason: str, groups: list[str] | None = None) -> AuthzDecision:
        d = AuthzDecision(allowed=allowed, reason=reason,
                          caller=identity.label if identity else "<unidentified>",
                          module=module, groups=groups or [], mode=mode)
        if audit:
            _audit(d)
        return d

    if mode == MODE_DISABLED:
        return done(True, "authz disabled (MCP_AUTHZ_MODE=disabled)")

    if identity is None:
        verdict = mode != MODE_ENFORCE
        return done(verdict,
                    "no caller identity — request did not carry the Databricks "
                    "Apps identity headers (X-Forwarded-*). Access the MCP "
                    "server through its Databricks Apps URL.")

    groups = _resolve_groups(identity)
    admin_hit = admin_groups() & set(groups)
    if admin_hit:
        return done(True, f"member of admin group {sorted(admin_hit)}", groups)

    need = required_level()
    grants = _module_grants(groups)
    have = grants.get(module)
    if have and _level_satisfies(have, need):
        return done(True, f"module_access '{module}' level '{have}'", groups)

    reason = (
        f"caller has no active '{module}' module_access grant at level "
        f"'{need}' in app_permissions. An admin can grant it: "
        f"AppPermissionsManager.grant_module_access(module_name='{module}', "
        f"groups=['<caller-group>'], access_level='{need}') — or add the "
        f"caller to the admin group."
    )
    if mode == MODE_PERMISSIVE:
        return done(True, f"[permissive — would deny] {reason}", groups)
    return done(False, reason, groups)


def _audit(d: AuthzDecision) -> None:
    """One structured line per decision; Databricks Apps keeps the app logs.
    DENY at warning so it stands out in the logs tab."""
    line = json.dumps({
        "event": "mcp_authz",
        "decision": "ALLOW" if d.allowed else "DENY",
        "caller": d.caller,
        "module": d.module,
        "mode": d.mode,
        "groups": d.groups,
        "reason": d.reason,
    })
    (logger.info if d.allowed else logger.warning)(line)
