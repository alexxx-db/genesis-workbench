"""Phase-3 test: workflow_capabilities derives from the node_catalog table
(NodeType BATCH rows → JOB/CHAIN Capabilities), carrying the full param contract
(options + min/max). Verifies the wheel reads the shared catalog source.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from genesis_workbench import capabilities as cap  # noqa: E402
from genesis_workbench.capabilities import CHAIN, JOB, Capability  # noqa: E402
from genesis_workbench.node_catalog import (  # noqa: E402
    NodeCategory,
    NodeType,
    ParamField,
    Port,
    PortType,
)


JOB_NODE = NodeType(
    type="enzyme_optimization", label="Guided Enzyme Optimization",
    category=NodeCategory.BATCH, kind="databricks_job", module="large_molecule",
    job_name="run_enzyme_optimization_gwb",
    inputs=[Port("motif_pdb", PortType.PDB), Port("substrate_smiles", PortType.SMILES)],
    outputs=[Port("candidates", PortType.JSON)],
    params=[ParamField("strategy", "Reseed strategy", "select", default="resample",
                       options=["resample", "noop"]),
            ParamField("num_iterations", "Iterations", "int", default=10, minimum=1, maximum=50)],
)
CHAIN_NODE = NodeType(
    type="admet_screen", label="ADMET Screen", category=NodeCategory.BATCH,
    kind="endpoint_chain", chain="admet_screen", module="small_molecule",
    inputs=[Port("smiles", PortType.SMILES)], outputs=[Port("profile", PortType.JSON)],
)
IO_NODE = NodeType(type="text_input", label="Text Input", category=NodeCategory.IO,
                   io_kind="text_input", outputs=[Port("value", PortType.ANY)])


def test_workflow_caps_from_catalog(monkeypatch):
    monkeypatch.setattr(cap, "read_catalog_nodes", lambda: [JOB_NODE, CHAIN_NODE, IO_NODE])
    caps = {c.id: c for c in cap.workflow_capabilities()}
    # IO is not a runnable capability — excluded.
    assert set(caps) == {"workflow:enzyme_optimization", "workflow:admet_screen"}

    job = caps["workflow:enzyme_optimization"]
    assert job.kind == JOB and job.job_name == "run_enzyme_optimization_gwb"
    # param contract (enum + range) survives the table → Capability conversion
    by = {p.name: p for p in job.params}
    assert by["strategy"].options == ["resample", "noop"]
    assert by["num_iterations"].minimum == 1 and by["num_iterations"].maximum == 50

    chain = caps["workflow:admet_screen"]
    assert chain.kind == CHAIN and chain.chain_id == "admet_screen"


def test_falls_back_to_legacy_when_no_batch_rows(monkeypatch):
    # node_catalog empty → call the legacy path (here stubbed to prove the branch)
    monkeypatch.setattr(cap, "_live_job_names", lambda: None)
    monkeypatch.setattr(cap, "read_catalog_nodes", lambda: [])
    sentinel = [Capability(id="workflow:legacy", label="L", kind=JOB)]
    monkeypatch.setattr(cap, "_workflow_capabilities_legacy", lambda: sentinel)
    assert cap.workflow_capabilities() == sentinel


def test_publish_node_catalog_sql(monkeypatch):
    # publish_node_catalog writes the built-in CURATED_NODES (no DB — capture SQL).
    sqls = []
    monkeypatch.setattr(cap, "execute_non_select_query", lambda q: sqls.append(q))
    n = cap.publish_node_catalog(catalog="c", schema="s")
    assert n == 44  # every built-in node published
    assert any("CREATE TABLE IF NOT EXISTS c.s.node_catalog" in q for q in sqls)
    assert any(q.startswith("DELETE FROM c.s.node_catalog WHERE source = 'builtin'") for q in sqls)
    inserts = [q for q in sqls if q.startswith("INSERT INTO c.s.node_catalog")]
    assert len(inserts) == 1 and inserts[0].count(", true)") == n  # one value tuple/node


# ── job-existence gate ───────────────────────────────────────────────────────
# The node catalog is published for every module whether or not that module was
# deployed, so a databricks_job node can name a job this workspace doesn't have
# (the genomics nodes on a core+bio install). Endpoint capabilities already derive
# existence from the live deployment registry; these cover the job side.

MISSING_JOB_NODE = NodeType(
    type="gwas", label="GWAS", category=NodeCategory.BATCH, kind="databricks_job",
    module="genomics", job_name="gwas_glow_analysis",
    inputs=[Port("vcf", PortType.PATH)], outputs=[Port("hits", PortType.JSON)],
)


def test_job_cap_unavailable_when_job_absent(monkeypatch):
    monkeypatch.setattr(cap, "read_catalog_nodes", lambda: [JOB_NODE, MISSING_JOB_NODE])
    monkeypatch.setattr(cap, "_live_job_names", lambda: {"run_enzyme_optimization_gwb"})
    caps = {c.id: c for c in cap.workflow_capabilities()}
    assert caps["workflow:enzyme_optimization"].available is True
    assert caps["workflow:gwas"].available is False


def test_chain_cap_untouched_by_job_gate(monkeypatch):
    # endpoint_chain capabilities carry no job_name — the gate must not demote them.
    monkeypatch.setattr(cap, "read_catalog_nodes", lambda: [CHAIN_NODE, MISSING_JOB_NODE])
    monkeypatch.setattr(cap, "_live_job_names", lambda: set())
    caps = {c.id: c for c in cap.workflow_capabilities()}
    assert caps["workflow:admet_screen"].available is True
    assert caps["workflow:gwas"].available is False


def test_job_gate_fails_open_when_lookup_unavailable(monkeypatch):
    # A Jobs API blip with no cached answer must not retract every workflow at
    # once — unknown leaves availability as authored.
    monkeypatch.setattr(cap, "read_catalog_nodes", lambda: [JOB_NODE, MISSING_JOB_NODE])
    monkeypatch.setattr(cap, "_live_job_names", lambda: None)
    caps = {c.id: c for c in cap.workflow_capabilities()}
    assert all(c.available for c in caps.values())


def test_live_job_names_serves_stale_cache_on_failure(monkeypatch):
    monkeypatch.setattr(cap, "_all_job_names_cache", {"cached_job"})
    monkeypatch.setattr(cap, "_all_job_names_cache_ts", 0.0)  # force a refresh attempt

    class Boom:
        def __getattr__(self, _):
            raise RuntimeError("jobs API down")

    monkeypatch.setattr(cap, "WorkspaceClient", Boom)
    assert cap._live_job_names() == {"cached_job"}


def test_live_job_names_returns_none_with_no_cache(monkeypatch):
    monkeypatch.setattr(cap, "_all_job_names_cache", None)
    monkeypatch.setattr(cap, "_all_job_names_cache_ts", 0.0)

    class Boom:
        def __getattr__(self, _):
            raise RuntimeError("jobs API down")

    monkeypatch.setattr(cap, "WorkspaceClient", Boom)
    assert cap._live_job_names() is None
