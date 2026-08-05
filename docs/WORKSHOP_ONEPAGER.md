# Genesis Workbench — Life Sciences AI Workshop

**A half-day, hands-on session showing how biological foundation models run governed, GPU-accelerated,
and code-free on Databricks.**

> This is a customer-facing one-pager. Engineers running the session should also read the
> [Engineering Guide](ENGINEERING_GUIDE.md) (Demo section) for the pre-flight checklist.

---

**What it is** — Genesis Workbench (GWB) is an open-source Databricks accelerator that packages ~25 open
biological foundation models — protein folding & design, single-cell genomics, small-molecule discovery,
and human genetics — behind an intuitive app. Scientists run advanced models without touching GPUs, CUDA,
model registries, or serving endpoints. Everything is built on Databricks primitives (Unity Catalog,
MLflow, Model Serving, Asset Bundles, Apps), so every run is governed, reproducible, and traceable.

**Who it's for** — Discovery research, computational biology, and data-platform teams in biopharma and
life sciences (e.g., Regeneron, Amgen, Pfizer, Merck). Tailored to your primary modality —
biologics/protein design, small molecule, single-cell, or human genetics.

**What you'll see (live)**
- **Protein design** — predict a structure from sequence in seconds (ESMFold), then design novel
  binders/backbones (RFdiffusion + ProteinMPNN) with automatic re-fold validation.
- **Single-cell & target biology** — annotate cell types and disease state against a 23M-cell reference
  (SCimilarity, Merck's TEDDY), plus perturbation prediction with scGPT.
- **Small-molecule discovery** — generate candidates (GenMol), profile ADMET/toxicity (ChemProp/KERMT),
  and dock to a target (DiffDock).
- **Human genetics** — GPU variant calling (Parabricks), GWAS (Glow), and ClinVar/ACMG annotation.
- **AI-native workflows** — describe a goal in natural language and get a runnable pipeline (Vortex);
  expose every model as a tool for your own agents (MCP server).

**Suggested agenda (≈3.5 hours)**

| Time | Segment | Audience |
|---|---|---|
| 0:00–0:20 | Framing: the discovery bottleneck & the GWB approach | All |
| 0:20–1:15 | Live workflows on *your* targets (2–3 fast demos) | Scientists |
| 1:15–1:45 | Vortex + MCP: AI-generated & agent-callable workflows | All |
| 1:45–2:30 | Under the hood: UC governance, MLflow serving, Asset Bundles | Platform / MLOps |
| 2:30–3:00 | Governance & security: lineage, identity, hardening path | IT / Security |
| 3:00–3:30 | Roadmap: from demo to your production discovery platform | Sponsors |

**What we need from you (before the day)**
- A Databricks workspace with **GPU quota** (A10/T4; multi-GPU on Azure) and workspace-admin access.
- A **UC catalog + dedicated schema** and a 2X-Small SQL warehouse for the app.
- Optional: a **public target/dataset** representative of your program so demos run on *your* science.

**Outcomes** — Your scientists see foundation models applied to your own targets with zero infrastructure
work; your platform team sees a governed reference architecture they could own and extend; your
leadership gets a concrete roadmap for a productionized, in-house discovery platform.

**Important** — GWB is an open-source solution accelerator for **early-stage discovery research** — a
demonstrable reference architecture, not validated/GxP software. Model outputs (folding confidence,
predicted developability, immunogenicity) are **hypothesis-ranking to prioritize wet-lab**, not
experimental results. Productionization (security hardening, CI/CD, your data & governance, cost
guardrails) is a natural follow-on engagement — see [`../HARDENING_CHECKLIST.md`](../HARDENING_CHECKLIST.md).

---
*Delivered by Entrada — Databricks life sciences partner.*
