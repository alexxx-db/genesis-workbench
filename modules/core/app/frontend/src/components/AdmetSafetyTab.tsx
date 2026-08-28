import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'

import { api } from '@/api/client'
import { RunSearchSection } from '@/components/RunSearchSection'
import { ChainRunResult } from '@/components/ChainRunResult'
import { ClipboardPaste } from '@/components/ClipboardPaste'

const EXAMPLE_SMILES = `COc(cc1)ccc1C#N
CC(=O)Oc1ccccc1C(=O)O
CC(C)NCC(O)c1ccc(O)c(O)c1
C1CCCCC1
c1ccc2[nH]ccc2c1`

function ts(): string {
  const d = new Date()
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}_${String(d.getHours()).padStart(2, '0')}${String(d.getMinutes()).padStart(2, '0')}`
}





export function AdmetSafetyTab() {
  const [smilesText, setSmilesText] = useState(EXAMPLE_SMILES)
  const [runBbbp, setRunBbbp] = useState(true)
  const [runClintox, setRunClintox] = useState(true)
  const [runAdmet, setRunAdmet] = useState(true)
  const [runKermt, setRunKermt] = useState(true)
  const [experiment, setExperiment] = useState('gwb_admet_safety')
  const [runName, setRunName] = useState(`admet_profiling_${ts()}`)

  // Dispatched as a job: this pipeline outlives the browser connection, and a
  // dropped connection used to lose a result that had already completed.
  const [searchToken, setSearchToken] = useState(0)
  const profile = useMutation({
    mutationFn: () =>
      api.chainStart({
        feature: 'admet',
        inputs: { smiles: smilesList },
        params: {
          run_bbbp: runBbbp,
          run_clintox: runClintox,
          run_admet: runAdmet,
          run_kermt: runKermt,
        },
        mlflow_run_name: runName,
        mlflow_experiment: experiment,
      }),
    onSuccess: () => setSearchToken((t) => t + 1),
  })

  const smilesList = useMemo(
    () =>
      smilesText
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean),
    [smilesText],
  )

  const canRun =
    !profile.isPending &&
    smilesList.length > 0 &&
    experiment.trim() &&
    runName.trim() &&
    (runBbbp || runClintox || runAdmet || runKermt)

  const runProfile = () => profile.mutate()



  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold">Profile ADMET and Safety Risks</h3>
        <p className="text-xs text-muted-foreground">
          Score one or more small molecules across absorption / distribution / metabolism /
          excretion / toxicity axes using Chemprop D-MPNN models. Predictors are independent —
          run any subset. Results log to MLflow alongside each prediction set.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(360px,460px)_1fr]">
        {/* Left form */}
        <div className="space-y-3">
          {/* Plain div (not <label>): a <label> proxies dead-area clicks to its first
              labelable descendant — here the ClipboardPaste button — popping the clipboard. */}
          <div className="block text-xs">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="block uppercase tracking-wide text-muted-foreground">
                SMILES (one per line)
              </span>
              <ClipboardPaste
                kind="molecule"
                label="Paste molecule"
                onPick={(it) =>
                  setSmilesText((prev) => {
                    const lines = prev.split('\n').map((s) => s.trim()).filter(Boolean)
                    return lines.includes(it.value) ? prev : [...lines, it.value].join('\n')
                  })
                }
              />
            </div>
            <textarea
              aria-label="SMILES (one per line)"
              rows={8}
              value={smilesText}
              onChange={(e) => setSmilesText(e.target.value)}
              placeholder="COc(cc1)ccc1C#N"
              className="w-full rounded-md border border-border bg-background p-3 font-mono text-xs"
            />
            <span className="mt-1 block text-[10px] text-muted-foreground">
              {smilesList.length} molecule{smilesList.length === 1 ? '' : 's'} parsed
            </span>
          </div>

          <div className="space-y-2 rounded-md border border-border bg-card p-3 text-xs">
            <div className="mb-1 font-medium uppercase tracking-wide text-muted-foreground">
              Predictors
            </div>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={runBbbp}
                onChange={(e) => setRunBbbp(e.target.checked)}
              />
              <span>BBB penetration (blood-brain barrier probability)</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={runClintox}
                onChange={(e) => setRunClintox(e.target.checked)}
              />
              <span>Clinical toxicity (failure probability)</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={runAdmet}
                onChange={(e) => setRunAdmet(e.target.checked)}
              />
              <span>ADMET properties (multi-task regression)</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={runKermt}
                onChange={(e) => setRunKermt(e.target.checked)}
              />
              <span>KERMT toxicity (GROVER — compare side-by-side with Chemprop)</span>
            </label>
          </div>

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
              onClick={runProfile}
              disabled={!canRun}
              className="flex-1 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {profile.isPending ? 'Profiling…' : 'Run ADMET Profiling'}
            </button>
            <button
              onClick={() => profile.reset()}
              disabled={!profile.data && !profile.error}
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
          {profile.isSuccess && profile.data && (
            <div className="rounded-md border border-success/40 bg-success/10 p-3 text-xs">
              <p className="font-medium text-success">Job launched</p>
              <p className="mt-1 text-muted-foreground">
                Run <span className="font-mono">{runName}</span> is queued. It appears
                below and updates on its own — you can close this tab.
              </p>
              {profile.data.job_run_url && (
                <a href={profile.data.job_run_url} target="_blank" rel="noreferrer"
                   className="mt-1 inline-block text-primary underline">
                  Open the job run
                </a>
              )}
            </div>
          )}
          {profile.isError && (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
              {String(profile.error)}
            </div>
          )}

          <RunSearchSection
            searchKey={['admet', 'runs']}
            searchFn={api.chainSearch('admet')}
            detailLabel="Molecules"
            detailColClass="min-w-[140px]"
            initialText="admet_profiling"
            viewableStatuses={['complete']}
            searchToken={searchToken}
            renderDialog={(run) => <ChainRunResult run={run} />}
          />
        </div>
      </div>
    </div>
  )
}
