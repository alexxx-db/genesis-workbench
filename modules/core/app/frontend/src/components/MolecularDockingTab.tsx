import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'

import { api } from '@/api/client'
import { RunSearchSection } from '@/components/RunSearchSection'
import { ChainRunResult } from '@/components/ChainRunResult'
import { ClipboardPaste } from '@/components/ClipboardPaste'
import { StructurePicker } from '@/components/StructurePicker'

function ts(): string {
  const d = new Date()
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}_${String(d.getHours()).padStart(2, '0')}${String(d.getMinutes()).padStart(2, '0')}`
}

export function MolecularDockingTab() {
  // Defaults: SMILES + 50-residue PDB excerpt of chain A from 6agt, fetched
  // server-side so the React bundle doesn't carry a multi-KB string.
  const example = useQuery({
    queryKey: ['small_molecule', 'diffdock', 'example'],
    queryFn: api.diffdockExample,
    staleTime: Infinity,
  })

  const [smiles, setSmiles] = useState('')
  const [proteinPdb, setProteinPdb] = useState('')
  const [numSamples, setNumSamples] = useState(5)
  const [experiment, setExperiment] = useState('gwb_molecular_docking')
  const [runName, setRunName] = useState(`molecular_docking_${ts()}`)

  // Seed the form once the example payload loads.
  useEffect(() => {
    if (!example.data) return
    setSmiles((cur) => cur || example.data!.smiles)
    setProteinPdb((cur) => cur || example.data!.pdb)
  }, [example.data])

  // Dispatched as a job: this pipeline outlives the browser connection, and a
  // dropped connection used to lose a result that had already completed.
  const [searchToken, setSearchToken] = useState(0)
  const dock = useMutation({
    mutationFn: () =>
      api.chainStart({
        feature: 'molecular_docking',
        inputs: { protein_pdb: proteinPdb, ligand_smiles: smiles },
        params: { samples_per_complex: numSamples },
        mlflow_run_name: runName,
        mlflow_experiment: experiment,
      }),
    onSuccess: () => setSearchToken((t) => t + 1),
  })

  // When a new result arrives, jump to the top-ranked pose so the viewer
  // shows something meaningful immediately.
  const canRun = Boolean(
    smiles.trim() && proteinPdb.trim() && experiment.trim() && runName.trim() && !dock.isPending,
  )

  const runDocking = () => dock.mutate()

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold">Simulate Ligand Binding to a Target</h3>
        <p className="text-xs text-muted-foreground">
          Predict 3D binding poses for a protein–ligand complex using{' '}
          <a
            href="https://github.com/gcorso/DiffDock"
            target="_blank"
            rel="noreferrer"
            className="text-primary hover:underline"
          >
            DiffDock
          </a>{' '}
          — a diffusion model that generates and ranks candidate poses with a confidence score.
          Computes ESM-2 embeddings of the target first, then runs the docking sampler with the
          embeddings pre-computed (split-endpoint pattern keeps each call under the proxy timeout).
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(320px,420px)_1fr]">
        {/* Left form */}
        <div className="space-y-3">
          <label className="block text-xs">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="block uppercase tracking-wide text-muted-foreground">
                Ligand (SMILES)
              </span>
              <ClipboardPaste kind="molecule" label="Paste molecule" onPick={(it) => setSmiles(it.value)} />
            </div>
            <input
              value={smiles}
              onChange={(e) => setSmiles(e.target.value)}
              placeholder="COc(cc1)ccc1C#N"
              className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs"
            />
          </label>

          <label className="block text-xs">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="block uppercase tracking-wide text-muted-foreground">
                Target protein (PDB)
              </span>
              <StructurePicker onPick={setProteinPdb} />
            </div>
            <textarea
              rows={10}
              value={proteinPdb}
              onChange={(e) => setProteinPdb(e.target.value)}
              placeholder="ATOM…  — or use “Pick a structure from a prior run”"
              className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-[10px] leading-tight"
            />
          </label>

          <label className="block text-xs">
            <span className="mb-1 block uppercase tracking-wide text-muted-foreground">
              Number of poses
            </span>
            <input
              type="range"
              min={1}
              max={20}
              step={1}
              value={numSamples}
              onChange={(e) => setNumSamples(parseInt(e.target.value))}
              className="w-full"
            />
            <div className="mt-1 text-muted-foreground">{numSamples}</div>
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
              onClick={runDocking}
              disabled={!canRun}
              className="flex-1 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {dock.isPending ? 'Docking…' : 'Run docking'}
            </button>
            <button
              onClick={() => dock.reset()}
              disabled={!dock.data && !dock.error}
              className="rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50"
            >
              Clear
            </button>
          </div>
        </div>

        {/* Right: dispatch banner + Search Past Runs — the run shows up here
            immediately and refreshes itself, so nothing is lost if the tab
            closes or the connection drops. */}
        <div className="space-y-3">
          {dock.isSuccess && dock.data && (
            <div className="rounded-md border border-success/40 bg-success/10 p-3 text-xs">
              <p className="font-medium text-success">Job launched</p>
              <p className="mt-1 text-muted-foreground">
                Run <span className="font-mono">{runName}</span> is queued. It appears
                below and updates on its own — you can close this tab.
              </p>
              {dock.data.job_run_url && (
                <a href={dock.data.job_run_url} target="_blank" rel="noreferrer"
                   className="mt-1 inline-block text-primary underline">
                  Open the job run
                </a>
              )}
            </div>
          )}
          {dock.isError && (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
              {String(dock.error)}
            </div>
          )}

          <RunSearchSection
            searchKey={['molecular_docking', 'runs']}
            searchFn={api.chainSearch('molecular_docking')}
            detailLabel="Poses"
            detailColClass="min-w-[140px]"
            initialText="molecular_docking"
            viewableStatuses={['complete']}
            searchToken={searchToken}
            renderDialog={(run) => <ChainRunResult run={run} />}
          />
        </div>
      </div>
    </div>
  )
}
