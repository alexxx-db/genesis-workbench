# Genesis Workbench — Life Sciences Glossary

A field guide to the life-sciences terms that appear in Genesis Workbench (GWB) and in early-stage
discovery conversations — scoped so a non-biologist can follow a scientist and explain any GWB
workflow. Grouped by domain.

> **Quick framings for workshops:** the discovery ladder is **target → hit → lead → candidate**, and
> GWB's value is turning weeks of wet-lab iteration into hours of *in silico* ranking to decide **what to
> make next**. Its scores prioritize experiments — they do not replace them.

---

## Discovery process & general biology

- **Target** — the biological molecule (usually a protein) a drug is designed to act on. "Target
  identification/validation" is the earliest discovery stage.
- **Hit / Lead / Candidate** — the maturation ladder: a **hit** is any molecule showing activity; a
  **lead** is an optimized hit worth pursuing; a **candidate** is nominated for development. GWB tools
  live mostly in hit-generation and lead-optimization.
- **Modality** — the *class* of therapeutic: small molecule, large molecule (biologic), cell/gene
  therapy, vaccine. Determines which GWB module matters to a customer.
- **In silico / in vitro / in vivo** — computational / in a test tube / in a living organism. GWB is
  entirely *in silico*; its job is to prioritize what goes to the wet lab.
- **Assay** — a lab measurement of a biological property (e.g., binding, toxicity). Fine-tuning models
  like KERMT means training on a customer's own assay data.
- **ADMET** — Absorption, Distribution, Metabolism, Excretion, Toxicity: the pharmacokinetic/safety
  profile of a drug. A core small-molecule screening axis.
- **Developability** — how manufacturable/drug-like a candidate is (solubility, stability, half-life,
  low immunogenicity). GWB's enzyme-optimization loop scores four developability axes.
- **Foundation model** — a large model pretrained on broad biological data (sequences, structures,
  cells) that teams fine-tune instead of training from scratch.

## Proteins & large molecules (biologics)

- **Amino acid / residue / sequence** — proteins are chains of amino acids; each position is a
  "residue"; the ordered list of letters is the "sequence" (the 1-D representation).
- **Structure (3-D) / fold** — how the sequence folds into a 3-D shape, which determines function.
  "Structure prediction" = sequence → 3-D coordinates.
- **PDB** — Protein Data Bank; also the standard file format for 3-D structures (what the Mol* viewer
  renders).
- **Backbone** — the structural scaffold of a protein without side-chain identities; de novo design
  generates a backbone, then assigns a sequence to it.
- **De novo design** — designing a brand-new protein from scratch (RFdiffusion generates novel
  backbones).
- **Inverse folding / sequence design** — given a fixed 3-D backbone, find sequences that fold into it
  (ProteinMPNN).
- **MSA (Multiple Sequence Alignment)** — a stack of evolutionarily related sequences that boosts
  folding accuracy (AlphaFold2 uses it; ESMFold skips it for speed).
- **pLDDT** — AlphaFold/ESMFold's per-residue confidence score (0–100); a proxy for how trustworthy the
  predicted structure is, not a measure of biological truth.
- **Embedding** — a numeric vector capturing a sequence's meaning; enables similarity search and
  downstream ML (ESM-2 produces 1280-dim protein embeddings).
- **Motif / scaffold** — a functional sub-region (motif) transplanted into a larger supporting structure
  (scaffold); "motif scaffolding" builds a protein around a required functional site.
- **Binder** — a protein or molecule designed to bind a specific target (protein-protein or
  protein-ligand).
- **Half-life / thermostability (Tm) / solubility / immunogenicity** — developability properties: how
  long it lasts in the body, its melting temperature, whether it stays dissolved, and whether it
  triggers an immune response.
- **MHC / HLA / epitope** — the immune-presentation system; MHC-I (HLA genes in humans) displays peptide
  fragments (epitopes) to the immune system. MHCflurry predicts this "immunogenic burden."

## Small molecules (chemistry)

- **Ligand** — a small molecule that binds a protein (often the drug itself).
- **SMILES** — a text string encoding a molecule's structure (the "sequence" of chemistry); the standard
  input format for small-molecule tools.
- **Docking / binding pose** — predicting how and where a ligand fits into a protein's pocket, and its
  3-D orientation (DiffDock).
- **QED** — Quantitative Estimate of Drug-likeness (0–1); a quick "is this molecule reasonable?" score
  used as a constraint in generative design.
- **Toxicity / ClinTox / BBBP** — safety endpoints: general toxicity, clinical-trial toxicity failure,
  and blood-brain-barrier penetration (relevant for CNS drugs).
- **GNN (Graph Neural Network)** — a model that treats a molecule as a graph of atoms/bonds; the
  architecture behind ChemProp and KERMT.

## Single-cell & functional genomics

- **scRNA-seq (single-cell RNA sequencing)** — measures gene expression in individual cells (vs. bulk
  averages); reveals cell-type heterogeneity. The core data type for the single-cell module.
- **Gene expression** — how active each gene is in a cell (its RNA level).
- **AnnData / h5ad** — the standard data object/file format for single-cell datasets (cells × genes
  matrix plus metadata).
- **QC / normalization / HVG** — the standard preprocessing pipeline: quality-control filtering,
  scaling, and selecting **highly variable genes**.
- **Clustering / UMAP** — grouping similar cells, then projecting them to a 2-D map for visualization
  (UMAP is the ubiquitous scatter-plot you'll see).
- **Cell-type annotation** — labeling each cluster with its biological identity (e.g., "NK cell,"
  "monocyte"), done by reference search (SCimilarity, TEDDY).
- **Differential expression (DE)** — finding genes that differ between two cell groups; shown as a
  **volcano plot**.
- **Marker gene** — a gene whose expression identifies a specific cell type.
- **Pathway / enrichment (GO/KEGG/Reactome)** — mapping a gene list to known biological processes;
  "enrichment" tests which pathways are over-represented.
- **Pseudotime / trajectory** — ordering cells along an inferred developmental or disease progression
  path.
- **Perturbation** — computationally simulating a gene knockout or overexpression to predict its effect
  (scGPT).
- **Cell atlas / CELLxGENE Census** — large public reference collections of annotated cells
  (SCimilarity's 23M-cell reference draws from these).

## Human genetics & genomics

- **Genome / exome** — all DNA / just the protein-coding ~2% of it. Genetics centers (Regeneron, deCODE
  at Amgen) sequence these at population scale.
- **Variant / mutation / SNP** — a difference from the reference genome; a SNP is a single-base change.
  The unit of analysis in the genomics module.
- **Germline vs. somatic** — inherited variants (present in every cell) vs. acquired ones (e.g., in a
  tumor). Parabricks does germline calling here.
- **FASTQ / BAM / VCF** — the genomics file pipeline: raw sequencing reads → aligned reads → called
  variants. GWB ingests VCFs into Delta for SQL/Spark.
- **Alignment / variant calling** — mapping reads to the reference genome, then identifying where a
  sample differs (the Parabricks steps).
- **GWAS (Genome-Wide Association Study)** — statistically linking variants across many people to a
  trait or disease.
- **ClinVar / ACMG / pathogenicity** — ClinVar is a public database of variant clinical significance;
  ACMG defines a panel of medically-actionable genes; "pathogenic" = disease-causing. Used for
  annotation and flagging.
- **Zygosity** — whether a variant is on one copy (heterozygous) or both (homozygous) of a chromosome.
- **Reference genome (GRCh38)** — the standard human genome coordinate system everything is compared
  against.

## Model & platform names to recognize

- **AlphaFold2 / ESMFold / Boltz** — protein structure prediction (high-accuracy+slow / fast /
  multi-chain complexes).
- **RFdiffusion / ProteinMPNN** — de novo backbone generation / sequence design for a backbone.
- **ESM-2** — Meta's protein language model; the embedding engine behind similarity search and several
  predictors.
- **scGPT / SCimilarity / TEDDY / Scanpy / rapids-singlecell** — single-cell foundation & analysis tools
  (TEDDY is Merck's; rapids-singlecell is the GPU-accelerated Scanpy).
- **GenMol / ChemProp / KERMT / DiffDock** — small-molecule generation / property prediction /
  fine-tunable ADMET GNN / docking (GenMol and KERMT are NVIDIA/BioNeMo).
- **Proteina-Complexa** — NVIDIA generative binder-design and motif-scaffolding model.
- **BioNeMo / Parabricks** — NVIDIA's digital-biology model framework / GPU-accelerated genomics
  toolkit.
- **Glow** — open-source Spark library for population-scale genomics (VCF ingestion, GWAS).
- **Mol\*** ("mol-star") — the in-browser 3-D molecular structure viewer used throughout the UI.
