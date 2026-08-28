import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'

import { api } from '@/api/client'
import { RunSearchSection } from '@/components/RunSearchSection'
import { ChainRunResult } from '@/components/ChainRunResult'

const EXAMPLE_MOTIF_PDB = `ATOM      1  N   HIS B   1       5.123   8.456   2.345  1.00 15.00           N
ATOM      2  CA  HIS B   1       5.891   7.234   2.789  1.00 15.00           C
ATOM      3  C   HIS B   1       7.321   7.567   3.123  1.00 15.00           C
ATOM      4  O   HIS B   1       7.654   8.678   3.567  1.00 15.00           O
ATOM      5  CB  HIS B   1       5.456   6.123   3.678  1.00 15.00           C
ATOM      6  CG  HIS B   1       4.012   5.789   3.456  1.00 15.00           C
ATOM      7  ND1 HIS B   1       3.123   6.567   4.123  1.00 15.00           N
ATOM      8  CE1 HIS B   1       1.890   6.012   3.890  1.00 15.00           C
ATOM      9  NE2 HIS B   1       1.987   4.890   3.123  1.00 15.00           N
ATOM     10  CD2 HIS B   1       3.234   4.678   2.890  1.00 15.00           C
ATOM     11  N   ASP B   2       8.123   6.567   2.890  1.00 15.00           N
ATOM     12  CA  ASP B   2       9.543   6.789   3.234  1.00 15.00           C
ATOM     13  C   ASP B   2      10.234   5.567   3.890  1.00 15.00           C
ATOM     14  O   ASP B   2       9.678   4.456   4.012  1.00 15.00           O
ATOM     15  CB  ASP B   2      10.123   7.890   2.345  1.00 15.00           C
ATOM     16  CG  ASP B   2      11.567   8.123   2.678  1.00 15.00           C
ATOM     17  OD1 ASP B   2      12.234   7.234   3.123  1.00 15.00           O
ATOM     18  OD2 ASP B   2      11.890   9.234   2.345  1.00 15.00           O
ATOM     19  N   SER B   3      11.456   5.678   4.234  1.00 15.00           N
ATOM     20  CA  SER B   3      12.234   4.567   4.890  1.00 15.00           C
ATOM     21  C   SER B   3      13.678   4.890   5.234  1.00 15.00           C
ATOM     22  O   SER B   3      14.123   5.987   5.012  1.00 15.00           O
ATOM     23  CB  SER B   3      11.890   3.234   4.234  1.00 15.00           C
ATOM     24  OG  SER B   3      12.567   2.123   4.678  1.00 15.00           O
HETATM   25  C1  LIG B   1       6.500   3.200   5.100  1.00  5.00           C
HETATM   26  O1  LIG B   1       7.200   2.100   5.500  1.00  5.00           O
HETATM   27  N1  LIG B   1       5.300   3.500   5.800  1.00  5.00           N
END
`

function ts(): string {
  const d = new Date()
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}_${String(d.getHours()).padStart(2, '0')}${String(d.getMinutes()).padStart(2, '0')}`
}

export function MotifScaffoldingTab() {
  const [motifPdb, setMotifPdb] = useState(EXAMPLE_MOTIF_PDB)
  const [targetChain, setTargetChain] = useState('B')
  const [lenMin, setLenMin] = useState(50)
  const [lenMax, setLenMax] = useState(80)
  const [numSamples, setNumSamples] = useState(2)
  const [optimizeMpnn, setOptimizeMpnn] = useState(true)
  const [validateEsmfold, setValidateEsmfold] = useState(true)
  const [experiment, setExperiment] = useState('gwb_motif_scaffolding')
  const [runName, setRunName] = useState(`motif_scaffolding_${ts()}`)


  // Dispatched as a Databricks job: this pipeline outlives the browser
  // connection, and a dropped connection used to lose a result that had in fact
  // completed and been logged to MLflow.
  const [searchToken, setSearchToken] = useState(0)
  const job = useMutation({
    mutationFn: () =>
      api.chainStart({
        feature: 'motif_scaffolding',
        inputs: { motif_pdb: motifPdb },
        params: {
          target_chain: targetChain,
          scaffold_length_min: lenMin,
          scaffold_length_max: lenMax,
          num_samples: numSamples,
          optimize_mpnn: optimizeMpnn,
          validate_esmfold: validateEsmfold,
        },
        mlflow_run_name: runName,
        mlflow_experiment: experiment,
      }),
    onSuccess: () => setSearchToken((t) => t + 1),
  })

  const canRun =
    !job.isPending &&
    motifPdb.trim().length > 0 &&
    targetChain.trim() &&
    experiment.trim() &&
    runName.trim() &&
    lenMin <= lenMax

  const runJob = () => job.mutate()




  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold">Transplant a Motif into New Scaffolds</h3>
        <p className="text-xs text-muted-foreground">
          Generate stable protein scaffolds that preserve a functional motif (active site,
          binding loop, etc.) using Proteina-Complexa-AME. Optionally refine each scaffold's
          sequence with ProteinMPNN and validate folding with ESMFold.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(360px,460px)_1fr]">
        {/* Left form */}
        <div className="space-y-3">
          <label className="block text-xs">
            <span className="mb-1 block uppercase tracking-wide text-muted-foreground">
              Motif PDB (ATOM + optional HETATM)
            </span>
            <textarea
              rows={12}
              value={motifPdb}
              onChange={(e) => setMotifPdb(e.target.value)}
              className="w-full rounded-md border border-border bg-background p-3 font-mono text-[10px] leading-tight"
            />
          </label>

          <label className="block text-xs">
            <span className="mb-1 block uppercase tracking-wide text-muted-foreground">
              Motif chain
            </span>
            <input
              value={targetChain}
              onChange={(e) => setTargetChain(e.target.value)}
              className="w-24 rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="block text-xs">
              <span className="mb-1 block uppercase tracking-wide text-muted-foreground">
                Min scaffold length
              </span>
              <input
                type="number"
                min={20}
                max={200}
                value={lenMin}
                onChange={(e) => setLenMin(parseInt(e.target.value || '20'))}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </label>
            <label className="block text-xs">
              <span className="mb-1 block uppercase tracking-wide text-muted-foreground">
                Max scaffold length
              </span>
              <input
                type="number"
                min={20}
                max={300}
                value={lenMax}
                onChange={(e) => setLenMax(parseInt(e.target.value || '300'))}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </label>
          </div>

          <label className="block text-xs">
            <span className="mb-1 block uppercase tracking-wide text-muted-foreground">
              Number of scaffolds
            </span>
            <input
              type="range"
              min={1}
              max={10}
              step={1}
              value={numSamples}
              onChange={(e) => setNumSamples(parseInt(e.target.value))}
              className="w-full"
            />
            <div className="mt-1 text-muted-foreground">{numSamples}</div>
          </label>

          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={optimizeMpnn}
              onChange={(e) => setOptimizeMpnn(e.target.checked)}
            />
            <span>Optimise sequence with ProteinMPNN</span>
          </label>
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={validateEsmfold}
              onChange={(e) => setValidateEsmfold(e.target.checked)}
            />
            <span>Validate each scaffold with ESMFold</span>
          </label>

          <div className="rounded-md border border-border bg-card p-3 text-xs">
            <div className="mb-2 font-medium uppercase tracking-wide text-muted-foreground">
              MLflow tracking
            </div>
            <label className="block">
              <span className="mb-1 block text-muted-foreground">Experiment</span>
              <input
                value={experiment}
                onChange={(e) => setExperiment(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </label>
            <label className="mt-2 block">
              <span className="mb-1 block text-muted-foreground">Run name</span>
              <input
                value={runName}
                onChange={(e) => setRunName(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </label>
          </div>

          <div className="flex gap-2">
            <button
              onClick={runJob}
              disabled={!canRun}
              className="flex-1 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {job.isPending ? 'Generating…' : 'Generate Scaffolds'}
            </button>
            <button
              onClick={() => job.reset()}
              disabled={!job.data && !job.error}
              className="rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50"
            >
              Clear
            </button>
          </div>
        </div>

        {/* Right: dispatch banner + Search Past Runs. The run appears here
            immediately and refreshes itself, so a closed tab or a dropped
            connection no longer costs you the result. */}
        <div className="space-y-3">
          {job.isSuccess && job.data && (
            <div className="rounded-md border border-success/40 bg-success/10 p-3 text-xs">
              <p className="font-medium text-success">Job launched</p>
              <p className="mt-1 text-muted-foreground">
                Run <span className="font-mono">{runName}</span> is queued. It appears
                below and updates on its own — you can close this tab.
              </p>
              {job.data.job_run_url && (
                <a href={job.data.job_run_url} target="_blank" rel="noreferrer"
                   className="mt-1 inline-block text-primary underline">
                  Open the job run
                </a>
              )}
            </div>
          )}
          {job.isError && (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
              {String(job.error)}
            </div>
          )}

          <RunSearchSection
            searchKey={['motif_scaffolding', 'runs']}
            searchFn={api.chainSearch('motif_scaffolding')}
            detailLabel="Scaffolds"
            detailColClass="min-w-[140px]"
            initialText="motif_scaffolding"
            viewableStatuses={['complete']}
            searchToken={searchToken}
            renderDialog={(run) => <ChainRunResult run={run} />}
          />
        </div>
      </div>
    </div>
  )
}
