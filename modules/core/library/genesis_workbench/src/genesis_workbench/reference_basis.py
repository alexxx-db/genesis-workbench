"""Reference basis — what each capability's model or annotation set was built on.

The question every regulated / non-human-species customer asks within the first
ten minutes of seeing a biological model is *"what was this trained on?"*. That
answer belongs in the system, not in the presenter's head: a scientist evaluating
whether ESMFold transfers to a bovine target should not have to ask, and neither
should an auditor reviewing why a prediction was trusted.

This module is the SINGLE authoring home for that answer. Each capability gets:

  - ``text``  — one plain sentence a scientist can act on
  - ``scope`` — a coarse class for filtering / badge colour (see ``Scope``)

Consumed by:
  - ``builtin_nodes``   — stamped onto every curated NodeType at import
  - ``capabilities``    — attached to live endpoint + workflow Capabilities
  - the MCP server      — appended to each tool description
  - the Vortex palette  — rendered as a badge + tooltip
  - the AI generator    — rendered in the catalog prompt lines

Two lookup tables share one set of constants: nodes are keyed by node ``type``,
live endpoints by UC short name, and the two namespaces genuinely differ
(``netsolp`` the node vs ``netsolp_v1`` the registered model). Keys are duplicated
between the tables; the *strings* are authored exactly once.

Accuracy note: these describe the model as shipped by Genesis Workbench. When a
capability is fine-tuned on customer data the basis changes — that is the point of
``Scope.USER``, and of the ``kermt_*`` entries in particular.
"""
from __future__ import annotations

from dataclasses import dataclass


class Scope:
    """Coarse transferability class. Values are plain strings (matching the
    codebase's `kind` / `shape` convention) so they round-trip through JSON."""

    AGNOSTIC = "agnostic"  # sequence-, structure- or chemistry-native; no species assumption
    MULTI = "multi"        # trained across multiple species incl. non-human
    HUMAN = "human"        # human-derived reference/labels; needs a swap for other species
    HOST = "host"          # tied to an expression host or assay system, not the target species
    USER = "user"          # basis is whatever the customer fine-tunes / supplies
    NA = ""                # no model behind it (IO, transforms, plumbing)


@dataclass(frozen=True)
class ReferenceBasis:
    text: str
    scope: str = Scope.NA

    @property
    def is_declared(self) -> bool:
        return bool(self.text)


UNDECLARED = ReferenceBasis("", Scope.NA)


# ─── Authored constants — one per distinct training/annotation basis ─────────

PROTEIN_LM = ReferenceBasis(
    "Species-agnostic — ESM-2 protein language model pretrained on UniRef "
    "(all domains of life). No species assumption in the sequence input.",
    Scope.AGNOSTIC,
)
PROTEIN_STRUCTURE = ReferenceBasis(
    "Species-agnostic — trained on experimental structures from the PDB, which "
    "spans all organisms. Transfers to any protein sequence.",
    Scope.AGNOSTIC,
)
PROTEIN_STRUCTURE_MSA = ReferenceBasis(
    "Species-agnostic — PDB structures plus multiple-sequence alignments over "
    "UniRef/BFD. Accuracy depends on MSA depth for the target family, not on species.",
    Scope.AGNOSTIC,
)
CHEMISTRY = ReferenceBasis(
    "Species-agnostic — learned over molecular structure; chemistry carries no "
    "species assumption. Any species-specific behaviour comes from the assay you score against.",
    Scope.AGNOSTIC,
)
DOCKING = ReferenceBasis(
    "Species-agnostic — trained on protein-ligand complexes (PDBBind-style). "
    "Binding geometry is physical; the target structure you supply sets the species.",
    Scope.AGNOSTIC,
)

SOLUBILITY_HOST = ReferenceBasis(
    "E. coli expression solubility — an expression-host property, not a "
    "target-species one. Valid for any sequence you intend to express in E. coli.",
    Scope.HOST,
)
THERMOSTABILITY_MULTI = ReferenceBasis(
    "Trained on ~35k proteins from the Meltome Atlas spanning 10+ organisms — from "
    "archaea and bacteria (E. coli, T. thermophilus) through yeast, plant, fly, worm, "
    "mouse and human. Takes organism growth temperature and measurement condition as "
    "explicit inputs, so it adapts across species; verify coverage for your organism.",
    Scope.MULTI,
)
HALF_LIFE_CELL_LINE = ReferenceBasis(
    "Trained on protein half-lives from the NIH3T3 mouse fibroblast cell line "
    "(Schwanhäusser 2011); the authors show it generalizes to a human (HeLa) cell "
    "line. It is a relative half-life ranker and a property of the cellular context, "
    "not of the protein's source species — treat it as mammalian cell-line-derived, "
    "not human-specific.",
    Scope.MULTI,
)

IMMUNO_HUMAN_MHC = ReferenceBasis(
    "Human MHC class I only (HLA-A/B/C allele panel). There is no drop-in "
    "equivalent for BoLA (bovine), SLA (swine), DLA (canine) or BF (avian) — "
    "treat this axis as not transferable to veterinary targets.",
    Scope.HUMAN,
)
ADMET_HUMAN_ASSAY = ReferenceBasis(
    "Human clinical and preclinical assay collections (MoleculeNet/TDC-style). "
    "The architecture transfers; the labels are human. Re-train on your own "
    "species-specific assay for veterinary use.",
    Scope.HUMAN,
)
ADMET_FINETUNABLE = ReferenceBasis(
    "Chemistry pretraining is species-agnostic; the fine-tune shipped by default "
    "is human clinical-trial toxicity (TDC ClinTox). Fine-tune on your own assay "
    "to make the basis your species — this is the intended path.",
    Scope.USER,
)

CELL_ATLAS_HUMAN = ReferenceBasis(
    "Human single-cell reference atlas. Cell-type labels and embeddings are "
    "human; no non-human atlas of comparable scale ships with the workbench.",
    Scope.HUMAN,
)

GENOME_PARAMETERIZED = ReferenceBasis(
    "Reference-genome parameterized — runs against whatever reference and known-"
    "sites files you supply, so it applies to any species with an assembled genome.",
    Scope.AGNOSTIC,
)
FORMAT_LEVEL = ReferenceBasis(
    "Format-level operation (VCF/Delta) — no trained model and no species "
    "assumption.",
    Scope.AGNOSTIC,
)
STATISTICAL = ReferenceBasis(
    "Statistical method, not a trained model — applies to any species given a "
    "genotype matrix and phenotypes.",
    Scope.AGNOSTIC,
)
CLINVAR_HUMAN = ReferenceBasis(
    "Human clinical variant significance (ClinVar). No non-human counterpart "
    "exists; for veterinary genomics this stage needs a species-appropriate "
    "annotation source substituted.",
    Scope.HUMAN,
)

FINETUNE_USER = ReferenceBasis(
    "Basis is whatever you fine-tune on — the resulting model inherits the "
    "species and assay of your training data, not the pretrained corpus.",
    Scope.USER,
)

COMPOSITE_STRUCTURE = ReferenceBasis(
    "Composite — inherits the basis of each step. Structure and sequence stages "
    "are species-agnostic; check any developability or annotation stage separately.",
    Scope.AGNOSTIC,
)
COMPOSITE_DEVELOPABILITY = ReferenceBasis(
    "Composite — species-agnostic structure/sequence stages combined with "
    "developability predictors whose bases differ (E. coli solubility, "
    "multi-species Tm, human MHC-I immunogenicity). Weight or disable per axis.",
    Scope.HUMAN,
)
COMPOSITE_ADMET = ReferenceBasis(
    "Composite — species-agnostic generation and scoring chemistry gated by "
    "ADMET models trained on human assays. Re-point the scoring model to change the basis.",
    Scope.HUMAN,
)


# ─── Lookup: curated node `type` → basis ────────────────────────────────────
BASIS_BY_NODE_TYPE: dict[str, ReferenceBasis] = {
    # large molecule — structure & sequence
    "esmfold": PROTEIN_LM,
    "esm2_embeddings": PROTEIN_LM,
    "boltz": PROTEIN_STRUCTURE,
    "proteinmpnn": PROTEIN_STRUCTURE,
    "rfdiffusion": PROTEIN_STRUCTURE,
    "alphafold2": PROTEIN_STRUCTURE_MSA,
    # developability predictors
    "netsolp": SOLUBILITY_HOST,
    "pltnum": HALF_LIFE_CELL_LINE,
    "deepstabp": THERMOSTABILITY_MULTI,
    "mhcflurry": IMMUNO_HUMAN_MHC,
    # small molecule
    "chemprop_admet": ADMET_HUMAN_ASSAY,
    "chemprop_bbbp": ADMET_HUMAN_ASSAY,
    "chemprop_clintox": ADMET_HUMAN_ASSAY,
    "kermt_admet": ADMET_FINETUNABLE,
    "diffdock": DOCKING,
    # single cell
    "teddy": CELL_ATLAS_HUMAN,
    "scgpt_embeddings": CELL_ATLAS_HUMAN,
    "scgpt_perturbation": CELL_ATLAS_HUMAN,
    "scimilarity_get_embedding": CELL_ATLAS_HUMAN,
    # genomics
    "variant_calling": GENOME_PARAMETERIZED,
    "vcf_ingestion": FORMAT_LEVEL,
    "variant_annotation": CLINVAR_HUMAN,
    "gwas": STATISTICAL,
    # batch workflows / chains
    "enzyme_optimization": COMPOSITE_DEVELOPABILITY,
    "molecule_optimization": COMPOSITE_ADMET,
    "protein_design": COMPOSITE_STRUCTURE,
    "admet_screen": COMPOSITE_ADMET,
    "protein_binder_design": COMPOSITE_STRUCTURE,
    "ligand_binder_design": COMPOSITE_STRUCTURE,
    "motif_scaffolding": COMPOSITE_STRUCTURE,
    # fine-tune jobs — the customer supplies the basis
    "esm2_finetune": FINETUNE_USER,
    "kermt_finetune": FINETUNE_USER,
    "kermt_deploy": FINETUNE_USER,
}


# ─── Lookup: deployed endpoint UC short name → basis ────────────────────────
# Deliberately a separate table: registered model names version independently of
# node types (`netsolp` the node, `netsolp_v1` the model).
BASIS_BY_UC_SHORT: dict[str, ReferenceBasis] = {
    "esmfold": PROTEIN_LM,
    "esm2_embeddings": PROTEIN_LM,
    "boltz": PROTEIN_STRUCTURE,
    "proteinmpnn": PROTEIN_STRUCTURE,
    "rfdiffusion_inpainting": PROTEIN_STRUCTURE,
    "rfdiffusion_unconditional": PROTEIN_STRUCTURE,
    "netsolp_v1": SOLUBILITY_HOST,
    "pltnum_v1": HALF_LIFE_CELL_LINE,
    "deepstabp_v1": THERMOSTABILITY_MULTI,
    "mhcflurry_v2": IMMUNO_HUMAN_MHC,
    "chemprop_admet": ADMET_HUMAN_ASSAY,
    "chemprop_bbbp": ADMET_HUMAN_ASSAY,
    "chemprop_clintox": ADMET_HUMAN_ASSAY,
    "kermt_admet": ADMET_FINETUNABLE,
    "genmol": CHEMISTRY,
    "diffdock": DOCKING,
    "diffdock_esm_embeddings": PROTEIN_LM,
    "proteina_complexa": PROTEIN_STRUCTURE,
    "proteina_complexa_ame": PROTEIN_STRUCTURE,
    "proteina_complexa_ligand": PROTEIN_STRUCTURE,
    "scgpt": CELL_ATLAS_HUMAN,
    "teddy": CELL_ATLAS_HUMAN,
    "scgpt_perturbation": CELL_ATLAS_HUMAN,
    "scimilarity_get_embedding": CELL_ATLAS_HUMAN,
}


def basis_for_node_type(node_type: str | None) -> ReferenceBasis:
    """Basis for a curated node `type`; UNDECLARED when none is authored (IO,
    transforms, and anything added without a basis entry)."""
    return BASIS_BY_NODE_TYPE.get(node_type or "", UNDECLARED)


def basis_for_uc_short(uc_short: str | None) -> ReferenceBasis:
    """Basis for a deployed endpoint's UC short name; UNDECLARED when unknown.

    An endpoint deployed without an entry here renders no badge rather than a
    misleading one — absence of a claim, not a claim of absence."""
    return BASIS_BY_UC_SHORT.get((uc_short or "").strip().lower(), UNDECLARED)
