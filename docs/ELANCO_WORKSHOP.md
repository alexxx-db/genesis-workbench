# Genesis Workbench — Elanco Workshop Runbook (Facilitator Guide)

**Account:** Elanco Animal Health · **Format:** half-day, hands-on · **Delivered by:** Entrada

This is the facilitator's run-of-show for an Elanco session. It layers an animal-health
narrative and a concrete click-path on top of the customer-facing
[one-pager](WORKSHOP_ONEPAGER.md). Engineers running the session should also read the
[Engineering Guide](ENGINEERING_GUIDE.md) (Demo section) and the
[Operations runbook](OPERATIONS.md) for pre-flight and incident handling.

> **Assumptions (adjust to the actual booking):** ~3.5 hours; mixed audience of Elanco
> discovery/computational scientists plus platform/IT; a Databricks workspace with GPU
> quota already deployed with `core` + the modules in the [pre-flight](#pre-flight-checklist).
> Swap the illustrative targets below for Elanco's own **public** targets before the day.

---

## 1. Why this lands for Elanco — the species-transferability story

Every other biotech workshop assumes a human target. Elanco's science is **veterinary and
livestock** — cattle, swine, poultry, companion animals (dogs/cats), aquaculture — so the
first question their scientists ask any biological model is *"was this trained on my
species, and if not, can I trust it?"*

Genesis Workbench answers that question **in the product**. Every capability carries a
**reference basis** — a plain sentence plus a coarse transferability class — surfaced as a
coloured dot in the Vortex palette, in the model detail panel, in the MCP tool description,
and in `list_capabilities`. This is the hook: **GWB tells an Elanco scientist, up front,
which models transfer to a bovine or canine target and which were trained on human data and
need a caveat.** No other demo does this.

### Species-transferability cheat-sheet (the spine of the session)

| Bucket | What it means for Elanco | Capabilities |
|---|---|---|
| **Transfers directly (species-agnostic)** | Structure, design and docking are physics/sequence-based, not species-bound — run them on a bovine/canine/porcine target as-is. | ESMFold, AlphaFold2, Boltz, ESM-2 embeddings, ProteinMPNN, RFdiffusion, protein/ligand binder design, motif scaffolding, DiffDock, variant calling (Parabricks), VCF ingestion, GWAS (Glow) |
| **Human-trained — use with a caveat** | Trained on human assays/atlases; treat outputs as a starting hypothesis for an animal target, not a validated read. | ADMET/tox (ChemProp, screen, BBBP, ClinTox), molecule optimization, enzyme optimization, scGPT, SCimilarity, TEDDY, ClinVar/ACMG variant annotation, **MHCflurry (human HLA only — no BoLA/SLA/DLA/BF)** |
| **Multi-species** | Explicitly multi-organism; verify coverage for your organism. | DeepSTABp (Meltome Atlas, growth-temp input), PLTNUM (mouse cell line, generalizes to human) |
| **Host-specific** | A property of the expression host, not the target species — valid regardless. | NetSolP (E. coli solubility) |
| **Fine-tune on *your* data** | The honest answer to "there's no animal model": bring Elanco data and the basis becomes *your* data. | KERMT (fine-tune → deploy ADMET), ESM-2 fine-tune |

**The three teachable moments to hit:**
1. **Structure & design just work** on animal targets (agnostic bucket) — lead with this.
2. **MHCflurry naming the absent BoLA/SLA/DLA/BF equivalents** is the perfect illustration
   of "the platform tells you the truth" — a human-only model that says so.
3. **Fine-tune KERMT/ESM-2 on Elanco data** is the bridge from "art of the possible" to
   "your in-house platform."

---

## 2. Run-of-show (≈3.5 hours)

| Time | Segment | Lead | Notes |
|---|---|---|---|
| 0:00–0:20 | **Framing** — discovery bottleneck in animal health; the GWB approach; the reference-basis promise | Entrada | Set up the species question up front |
| 0:20–0:50 | **Act 1 — Biologics/protein design** on a veterinary antibody target | Scientists | [Click-path §3, Act 1](#act-1--biologics-for-a-companion-animal-target-species-agnostic) |
| 0:50–1:20 | **Act 2 — Small-molecule** for a parasiticide/anti-infective | Scientists | [Click-path §3, Act 2](#act-2--small-molecule-for-a-parasiticide-human-assay-caveat) |
| 1:20–1:45 | **Act 3 — AI-native**: Vortex NL→pipeline (basis dots visible) + MCP as agent tools | All | [Click-path §3, Act 3](#act-3--ai-native-workflows-vortex--mcp) |
| 1:45–2:15 | **Optional — Livestock genomics**: Parabricks variant calling + GWAS on a breeding trait | Scientists | Agnostic bucket; skip if time-boxed |
| 2:15–2:45 | **Under the hood** — UC governance, MLflow serving, Asset Bundles, the shared wheel | Platform/MLOps | [Architecture](ARCHITECTURE.md) |
| 2:45–3:10 | **Governance & security** — lineage, identity, the hardening path (deploy SP, MCP authZ, secrets, AI Gateway) | IT/Security | [HARDENING_CHECKLIST](../HARDENING_CHECKLIST.md) |
| 3:10–3:30 | **Roadmap** — from demo to Elanco's in-house discovery platform | Sponsors | Fine-tune-on-your-data as the wedge |

---

## 3. Live demo click-path

> Each act is written as: **target → clicks → what to say → the basis beat.** Times assume
> endpoints are pre-warmed (see [pre-flight](#pre-flight-checklist)); long GPU runs must be
> **pre-baked** the day before and shown as a completed run, not launched live.

### Act 1 — Biologics for a companion-animal target (species-agnostic)

**Illustrative target:** canine IL-31 (the target class behind anti-itch mAbs for atopic
dermatitis) — swap for an Elanco public target. The point is *this is not a human protein
and the models don't care.*

1. **Protein Structure Prediction** tab → paste the canine IL-31 sequence → run **ESMFold**.
   Structure returns in seconds with a per-residue confidence.
   - *Say:* "This is a dog protein. ESMFold is species-agnostic — it reasons over the
     sequence, not an organism label. Note the green 'species-agnostic' basis on the model."
2. **Protein Binder Design** tab → design binders/backbones against the predicted structure
   with **RFdiffusion + ProteinMPNN** → the workflow **re-folds** each design (ESMFold) to
   self-validate.
   - *Say:* "We just designed novel binders to a veterinary target and auto-validated them
     by re-folding — no GPU, no CUDA, fully governed in Unity Catalog."
3. *(If NetSolP deployed)* show the **solubility** read and call out its basis: *"E. coli
   expression solubility — a property of the host, valid for any target species."*

**Basis beat:** open the same nodes in **Vortex** (Act 3) and show the green dots — the
platform already told the scientist these transfer.

### Act 2 — Small-molecule for a parasiticide (human-assay caveat)

**Illustrative goal:** hit-finding for an antiparasitic against a parasite enzyme target.

1. **Guided Molecule Design** tab → generate candidates with **GenMol** around a seed/target.
2. **ADMET / Safety** tab → profile candidates with **ChemProp** (tox/ADMET).
   - **This is the key honesty beat.** *Say:* "These ADMET models were trained on **human**
     assay data — the platform flags that. For an Elanco program the readout is a
     hypothesis-ranker to prioritize, and the target-species ADMET is exactly what you'd
     **fine-tune KERMT** on with your own data. The model doesn't pretend to be something
     it isn't."
3. **Molecular Docking** tab → dock a top candidate to the target with **DiffDock**
   (species-agnostic — it's structure-based).

**Basis beat:** contrast the green **DiffDock** dot (agnostic) with the amber **ChemProp**
dot (human) side-by-side. Same screen, opposite transferability — that's the product's value.

### Act 3 — AI-native workflows (Vortex + MCP)

1. **Vortex** canvas → type a natural-language goal, e.g. *"predict the structure of this
   sequence, design binders, and check developability."* Vortex assembles a runnable graph.
   - *Say:* "Every node shows its species basis as a coloured dot; typing 'human' in the
     palette surfaces every human-trained capability in one pass. The scientist sees
     transferability while they build."
2. **MCP server** → show `list_capabilities` returning each tool **with its reference
   basis**, then have an agent call a tool. *Say:* "Your own agents can call these models as
   tools, and they get the same species-fit signal an agent needs to choose correctly — no
   UI required."

### Optional — Livestock genomics

- **Variant calling (Parabricks)** and **GWAS (Glow)** are species-agnostic. Run a small
  variant-calling demo and a GWAS on a public livestock breeding-trait dataset. Call out
  that **ClinVar/ACMG annotation is human** (amber basis) — you'd swap in a species-appropriate
  annotation source.

---

## 4. Talking points by audience

- **Scientists:** foundation models on *your* animal targets with zero infrastructure; the
  reference basis tells you what transfers; fine-tuning is the path when it doesn't.
- **Platform / MLOps:** every model is a governed MLflow model in Unity Catalog, served via
  Model Serving, deployed by Asset Bundles; one shared wheel powers UI, Vortex, and MCP
  ([Architecture](ARCHITECTURE.md)).
- **IT / Security:** be upfront about the hardening gaps (bundles deploy under the deploying
  user, MCP has no per-caller authZ, Docker creds) — and show they're already catalogued
  with effort estimates in the [Hardening Checklist](../HARDENING_CHECKLIST.md) and checkable
  via `scripts/hardening_check.py`. This *builds* trust.
- **Sponsors:** GWB is the "art of the possible"; the productionized, Elanco-owned discovery
  platform (their data, their species models, their governance) is the follow-on engagement.

---

## 5. Pre-flight checklist

Run through this **the day before**. Full commands and the failure catalog are in
[OPERATIONS.md](OPERATIONS.md) and the deploy-wizard skill.

**Modules to deploy** (one at a time; wait for each module's first job to reach `RUNNING`):
- [ ] `core` (UI app, MCP app, catalog/schema, settings tables) — first.
- [ ] `large_molecule` — ESMFold, RFdiffusion, ProteinMPNN, binder design (Act 1).
- [ ] `small_molecule` — GenMol, ChemProp, KERMT, DiffDock (Act 2).
- [ ] *(optional)* `genomics` — Parabricks + Glow (livestock genomics). Needs Docker setup
      first (DCS enabled, images pushed, `module.env` creds as **secret-scope refs** — see
      `modules/genomics/module.env.template`).
- [ ] *(optional)* `single_cell` — only if showing SCimilarity/TEDDY/scGPT.

**Data / prerequisites:**
- [ ] Run `modules/core/notebooks/ingest_uniprot_genes.py` once (or let the sequence_search
      workflow's `ingest_gene_sequences` task build `gene_sequences`) so gene→target
      resolution works.
- [ ] Load Elanco's public target sequence(s) and any illustrative small-molecule seed.

**Warm & bake (avoid dead air):**
- [ ] **Pre-warm** the serving endpoints you'll click (ESMFold, ChemProp, DiffDock, etc.) so
      the first request isn't a cold scale-from-zero start.
- [ ] **Pre-bake** any run >~2–3 min (RFdiffusion binder design, docking, variant calling)
      the day before and keep the completed run open in a second tab — GWB's "Past Runs"
      lets you show a finished result instantly. **Do not launch a multi-minute GPU job live.**
- [ ] Confirm every serving endpoint is `READY` (don't trust the deploy `✅ SUCCESS` banner —
      verify endpoint state; see [OPERATIONS.md](OPERATIONS.md)).

**Reference-basis sanity:**
- [ ] Open Vortex and confirm the basis dots render; confirm searching "human" filters the
      palette. This is the demo's centerpiece — verify it works before the room sees it.

---

## 6. Objection handling / FAQ

- **"Is this validated for our regulatory submissions?"** No — GWB is an open-source
  reference architecture for **early-stage discovery**. Outputs (folding confidence,
  predicted developability/tox/immunogenicity) are **hypothesis-ranking to prioritize
  wet-lab**, not experimental or GxP results. That framing is in the one-pager and product
  disclaimer.
- **"Most of these were trained on human data — useless for us?"** The opposite is the point:
  structure/design/docking/genomics are species-agnostic and transfer directly; the
  human-trained property models are clearly flagged and are exactly what you'd fine-tune on
  Elanco data. The platform is honest about which is which.
- **"MHC/immunogenicity for cattle/swine/dogs?"** MHCflurry is human HLA only and **says so**
  (it names the absent BoLA/SLA/DLA/BF equivalents). Treat it as not transferable to
  veterinary targets — a candidate for a fine-tuned/host-specific replacement.
- **"GPU cost?"** Endpoints scale to zero; registration/deploy jobs are the heavy GPU cost.
  Cost governance is a hardening workstream ([HARDENING_CHECKLIST](../HARDENING_CHECKLIST.md)).
- **"Security — the MCP server / who deploys it?"** Known gaps, already catalogued with
  effort and acceptance criteria; `scripts/hardening_check.py` reports them. Productionization
  closes them.

---

## 7. Leave-behinds & follow-on

- [One-pager](WORKSHOP_ONEPAGER.md) (customer-facing).
- [Glossary](../GLOSSARY.md) for scientists new to the model zoo.
- [Hardening Checklist](../HARDENING_CHECKLIST.md) to scope the productionization SOW.
- Follow-on: an Elanco-owned discovery platform — their data, species-specific fine-tunes
  (KERMT/ESM-2), their governance and cost guardrails.

---
*Delivered by Entrada — Databricks life sciences partner. Swap illustrative targets for
Elanco's own public targets before delivery.*
