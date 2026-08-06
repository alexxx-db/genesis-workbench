"""
Configuration file for the Genesis Workbench app permissions system.
Defines modules and submodules that users can access in the web application.
"""

import os
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class ModuleConfig:
    """Configuration for a Genesis Workbench module."""

    name: str
    display_name: str
    description: str
    submodules: List[str]


MODULES = {
    "large_molecule": ModuleConfig(
        name="large_molecule",
        display_name="Large Molecule",
        description="Protein folding and analysis workflows",
        submodules=["settings", "protein_structure_prediction", "protein_design"],
    ),
    "nvidia_bionemo": ModuleConfig(
        name="nvidia_bionemo",
        display_name="NVIDIA BioNeMo",
        description="NVIDIA BioNeMo model workflows",
        submodules=["settings", "esm2_finetune", "esm2_inference"],
    ),
    "single_cell": ModuleConfig(
        name="single_cell",
        display_name="Single Cell Analysis",
        description="Single cell analysis workflows",
        submodules=["settings", "embeddings"],
    ),
    "monitoring_alerts": ModuleConfig(
        name="monitoring_alerts",
        display_name="Monitoring & Alerts",
        description="Monitoring and alerting workflows",
        submodules=["workflows", "dashboard", "alerts"],
    ),
    "master_settings": ModuleConfig(
        name="master_settings",
        display_name="Master Settings",
        description="Administrative settings and configuration",
        submodules=["settings"],
    ),
}

PERMISSION_TYPES = {
    "module_access": "Access to view and use a module",
    "submodule_access": "Access to specific submodule functionality",
}

ACCESS_LEVELS = {
    "view": "Read-only access - can view but not modify",
    "full": "Full access - can view and modify",
}

USER_TYPES = {
    "admin": "Administrative users with full access",
    "user": "Regular users with module-specific access",
}

# TODO: Pull these from variables.yml
DEFAULT_GROUPS = {
    "admin": ["genesis-admin-group"],
    "user": ["genesis-users"],
}

# Catalog/schema that hold the app_permissions table. Sourced from the
# environment rather than hardcoded so a second workspace deploys with only
# env-file changes (HARDENING_CHECKLIST.md 1.2). CORE_CATALOG_NAME /
# CORE_SCHEMA_NAME are exported by genesis_workbench.workbench.initialize() at
# app startup, threaded from the DAB variables core_catalog_name /
# core_schema_name via the settings table. The setup notebook overrides both
# through its catalog_name / schema_name widgets (DAB task parameters), so these
# module-level values are only fallbacks for direct AppPermissionsManager() use.
DEFAULT_CATALOG = os.environ.get("CORE_CATALOG_NAME", "")
DEFAULT_SCHEMA = os.environ.get("PERMISSIONS_SCHEMA", os.environ.get("CORE_SCHEMA_NAME", "permissions"))
PERMISSIONS_TABLE_NAME = "app_permissions"
PERMISSIONS_TABLE_COMMENT = (
    "Application permissions management for Genesis Workbench modules and submodules"
)

DELTA_TABLE_PROPERTIES = {
    "delta.autoOptimize.optimizeWrite": "true",
    "delta.autoOptimize.autoCompact": "true",
    "delta.feature.allowColumnDefaults": "supported",
}

DATABRICKS_API_VERSION = "2.0"
DATABRICKS_SCIM_API_VERSION = "2.0"
