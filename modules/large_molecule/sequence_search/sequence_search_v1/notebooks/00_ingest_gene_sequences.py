# Databricks notebook source
# MAGIC %md
# MAGIC ### Ingest SwissProt (reviewed) human proteins → `gene_sequences`
# MAGIC Builds the gene-keyed Delta table that the human-gene companion index
# MAGIC (`05_batch_embed_gene_sequences` → `06_create_gene_vector_index`) and the app's
# MAGIC Target Resolver read. Runs first in this workflow so the table exists before the
# MAGIC embed step, rather than relying on someone running it by hand.
# MAGIC
# MAGIC NOTE: this is the same ingest as core's `modules/core/notebooks/ingest_uniprot_genes.py`
# MAGIC (which stays the canonical copy the app documents). Keep the two in sync — they are
# MAGIC duplicated only because a DAB job task cannot reference a notebook in another bundle.
# MAGIC Only this notebook (not the running app) touches UniProt, and only at ingest time on
# MAGIC a cluster with outbound internet.

# COMMAND ----------

dbutils.widgets.text("catalog", "genesis_workbench", "Catalog")
dbutils.widgets.text("schema", "genesis_schema", "Schema")
dbutils.widgets.text("organism_id", "9606", "NCBI organism id (9606 = human)")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
organism_id = dbutils.widgets.get("organism_id")

# COMMAND ----------

import re
import urllib.request

# Bulk FASTA of reviewed proteins for the organism.
url = (
    "https://rest.uniprot.org/uniprotkb/stream?"
    f"query=reviewed:true+AND+organism_id:{organism_id}&format=fasta"
)
print(f"Downloading reviewed proteome from {url}")
with urllib.request.urlopen(url, timeout=600) as resp:
    fasta = resp.read().decode("utf-8")
print(f"Downloaded {len(fasta)} bytes")

# COMMAND ----------

# Header: >sp|P09874|PARP1_HUMAN Poly [ADP-ribose] polymerase 1 OS=Homo sapiens OX=9606 GN=PARP1 PE=1 SV=4
hdr = re.compile(
    r"^>\w+\|(?P<acc>[^|]+)\|(?P<entry>\S+)\s+(?P<name>.*?)\s+OS=(?P<org>.*?)\s+OX=.*?"
    r"(?:\sGN=(?P<gene>\S+))?(?:\sPE=.*)?$"
)
rows = []
acc = entry = name = gene = org = None
seq = []


def _flush():
    if acc and gene and seq:
        s = "".join(seq)
        rows.append((gene, acc, entry, name, org or "", s, len(s)))


for line in fasta.splitlines():
    if line.startswith(">"):
        _flush()
        m = hdr.match(line)
        if m:
            acc, entry, name, gene, org = (
                m.group("acc"), m.group("entry"), m.group("name"),
                m.group("gene"), m.group("org"),
            )
        else:
            acc = entry = name = gene = org = None
        seq = []
    else:
        seq.append(line.strip())
_flush()
print(f"Parsed {len(rows)} proteins with a gene symbol")

# COMMAND ----------

cols = ["gene", "accession", "entry_name", "protein_name", "organism", "sequence", "seq_length"]
df = spark.createDataFrame(rows, cols)
(
    df.write.mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{catalog}.{schema}.gene_sequences")
)
print(f"Wrote {df.count()} rows to {catalog}.{schema}.gene_sequences")
display(spark.sql(f"SELECT gene, accession, seq_length FROM {catalog}.{schema}.gene_sequences WHERE upper(gene)='PARP1'"))
