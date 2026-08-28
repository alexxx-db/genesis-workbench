import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'

import { api } from '@/api/client'
import { SequenceSourceControls } from '@/components/SequenceSourceControls'
import { RunSearchSection } from '@/components/RunSearchSection'
import { ChainRunResult } from '@/components/ChainRunResult'
import { cn } from '@/lib/utils'

type InputMode = 'sequence' | 'pdb'

const EXAMPLE_SEQUENCE =
  'MTYKLILNGKTLKGETTTEAVDAATAEKVFKQYANDNGVDGEWTYDAATKTFTVTE'

function ts(): string {
  const d = new Date()
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}_${String(d.getHours()).padStart(2, '0')}${String(d.getMinutes()).padStart(2, '0')}`
}

export function ProteinBinderDesignTab() {
  // Reuse the docking example endpoint for the default PDB — it serves a
  // 50-residue chain-A slice of 6agt that's also a sensible binder target.
  const example = useQuery({
    queryKey: ['small_molecule', 'diffdock', 'example'],
    queryFn: api.diffdockExample,
    staleTime: Infinity,
  })

  const [inputMode, setInputMode] = useState<InputMode>('sequence')
  const [sequence, setSequence] = useState(EXAMPLE_SEQUENCE)
  const [pdb, setPdb] = useState('')
  const [targetChain, setTargetChain] = useState('A')
  const [hotspots, setHotspots] = useState('')
  const [lenMin, setLenMin] = useState(50)
  const [lenMax, setLenMax] = useState(80)
  const [numSamples, setNumSamples] = useState(2)
  const [validateEsmfold, setValidateEsmfold] = useState(true)
  const [experiment, setExperiment] = useState('gwb_binder_design')
  const [runName, setRunName] = useState(`binder_design_${ts()}`)


  // Seed the PDB textarea once the example payload lands. Don't overwrite
  // anything the user has already typed.
  useEffect(() => {
    if (example.data?.pdb) setPdb((cur) => cur || example.data!.pdb)
  }, [example.data])

  // Dispatch as a Databricks job instead of streaming: the pipeline routinely
  // outlives the browser connection, and a lost connection used to mean a lost
  // result even though the work completed and logged to MLflow.
  const [searchToken, setSearchToken] = useState(0)
  const design = useMutation({
    mutationFn: () =>
      api.chainStart({
        feature: 'binder_design',
        inputs: {
          target_pdb: inputMode === 'pdb' ? pdb : '',
          target_sequence: inputMode === 'sequence' ? sequence : '',
        },
        params: {
          target_chain: targetChain,
          hotspot_residues: hotspots,
          binder_length_min: lenMin,
          binder_length_max: lenMax,
          num_samples: numSamples,
          validate_esmfold: validateEsmfold,
        },
        mlflow_run_name: runName,
        mlflow_experiment: experiment,
      }),
    onSuccess: () => setSearchToken((t) => t + 1),
  })

  const canRun =
    !design.isPending &&
    targetChain.trim().length > 0 &&
    experiment.trim() &&
    runName.trim() &&
    lenMin <= lenMax &&
    (inputMode === 'sequence' ? sequence.trim().length > 0 : pdb.trim().length > 0)

  const runDesign = () => design.mutate()





  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold">Design Binders Against a Target</h3>
        <p className="text-xs text-muted-foreground">
          Design novel protein binders against a target. The pipeline takes a target PDB (or folds
          a target sequence first via ESMFold), generates binder candidates with Proteina-Complexa
          conditioned on the target + optional hotspot residues, then optionally re-folds each
          binder with ESMFold to verify the design folds.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(360px,460px)_1fr]">
        {/* Left form */}
        <div className="space-y-3">
          <div className="flex gap-1">
            {(['sequence', 'pdb'] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setInputMode(m)}
                className={cn(
                  'rounded-md border px-3 py-2 text-xs transition-colors',
                  inputMode === m
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:bg-accent',
                )}
              >
                {m === 'sequence' ? 'Protein sequence' : 'Target PDB'}
              </button>
            ))}
          </div>

          {inputMode === 'sequence' ? (
            <label className="block text-xs">
              <span className="mb-1 block uppercase tracking-wide text-muted-foreground">
                Target sequence
              </span>
              <SequenceSourceControls onSequence={setSequence} className="mb-1.5" />
              <textarea
                rows={4}
                value={sequence}
                onChange={(e) => setSequence(e.target.value)}
                placeholder="MTYK…"
                className="w-full rounded-md border border-border bg-background p-3 font-mono text-xs"
              />
              <span className="mt-1 block text-[10px] text-muted-foreground">
                Will be folded by ESMFold to produce the target PDB.
              </span>
            </label>
          ) : (
            <label className="block text-xs">
              <span className="mb-1 block uppercase tracking-wide text-muted-foreground">
                Target PDB
              </span>
              <textarea
                rows={10}
                value={pdb}
                onChange={(e) => setPdb(e.target.value)}
                placeholder="ATOM…"
                className="w-full rounded-md border border-border bg-background p-3 font-mono text-[10px] leading-tight"
              />
            </label>
          )}

          <div className="grid grid-cols-2 gap-3">
            <label className="block text-xs">
              <span className="mb-1 block uppercase tracking-wide text-muted-foreground">
                Target chain
              </span>
              <input
                value={targetChain}
                onChange={(e) => setTargetChain(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </label>
            <label className="block text-xs">
              <span className="mb-1 block uppercase tracking-wide text-muted-foreground">
                Hotspot residues
              </span>
              <input
                value={hotspots}
                onChange={(e) => setHotspots(e.target.value)}
                placeholder="e.g. 10,20,30"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              />
            </label>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <label className="block text-xs">
              <span className="mb-1 block uppercase tracking-wide text-muted-foreground">
                Min binder length
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
                Max binder length
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
              Number of designs
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
              checked={validateEsmfold}
              onChange={(e) => setValidateEsmfold(e.target.checked)}
            />
            <span>Validate each design with ESMFold</span>
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
              onClick={runDesign}
              disabled={!canRun}
              className="flex-1 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {design.isPending ? 'Launching…' : 'Launch Design Job'}
            </button>
            <button
              onClick={() => design.reset()}
              disabled={!design.data && !design.error}
              className="rounded-md border border-border px-4 py-2 text-sm hover:bg-accent disabled:opacity-50"
            >
              Clear
            </button>
          </div>
        </div>

        {/* Right: dispatch banner + Search Past Runs (standard batch-workflow
            pattern — the run appears here immediately and auto-refreshes, so a
            closed tab or dropped connection no longer loses the result). */}
        <div className="space-y-3">
          {design.isSuccess && design.data && (
            <div className="rounded-md border border-success/40 bg-success/10 p-3 text-xs">
              <p className="font-medium text-success">Design job launched</p>
              <p className="mt-1 text-muted-foreground">
                Run <span className="font-mono">{runName}</span> is queued. It appears
                below and updates on its own — you can close this tab.
              </p>
              {design.data.job_run_url && (
                <a
                  href={design.data.job_run_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-block text-primary underline"
                >
                  Open the job run
                </a>
              )}
            </div>
          )}
          {design.isError && (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
              {String(design.error)}
            </div>
          )}

          <RunSearchSection
            searchKey={['binder_design', 'runs']}
            searchFn={api.chainSearch('binder_design')}
            detailLabel="Designs"
            detailColClass="min-w-[140px]"
            initialText="binder_design"
            viewableStatuses={['complete']}
            searchToken={searchToken}
            renderDialog={(run) => <ChainRunResult run={run} />}
          />
        </div>
      </div>
    </div>
  )
}
