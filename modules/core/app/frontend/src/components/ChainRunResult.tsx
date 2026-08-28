import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { useMemo, useState } from 'react'

import { api } from '@/api/client'
import { DataTable } from '@/components/DataTable'
import { MolstarViewer } from '@/components/MolstarViewer'
import type { DBRunRow } from '@/types/api'

type Design = {
  sample_id?: string
  sequence?: string
  rewards?: number
  pdb_output?: string
  esmfold_pdb?: string
  esmfold_validated?: boolean
  viewer_html?: string
  [k: string]: unknown
}

/**
 * View dialog for any chain run dispatched through /api/chains.
 *
 * Chains return different shapes, so this renders the two things they have in
 * common — a `designs` list and any scalar fields — rather than pretending every
 * chain looks like binder design. Structures render in Molstar when a chain
 * emitted PDB text.
 */
export function ChainRunResult({ run }: { run: DBRunRow }) {
  const res = useQuery({
    queryKey: ['chain', 'result', run.run_id],
    queryFn: () => api.chainResult(run.run_id),
  })
  const [selected, setSelected] = useState(0)

  const result = (res.data?.result ?? {}) as Record<string, unknown>
  // Chains name their result list differently (designs / scaffolds / molecules).
  const designs = useMemo<Design[]>(() => {
    for (const key of ['designs', 'scaffolds', 'molecules', 'results']) {
      const v = result[key]
      if (Array.isArray(v)) return v as Design[]
    }
    return []
  }, [result])

  const columns = useMemo<ColumnDef<Design, unknown>[]>(() => {
    const cols: ColumnDef<Design, unknown>[] = [
      { id: 'sample_id', header: 'Sample', accessorFn: (r) => r.sample_id ?? '—' },
    ]
    if (designs.some((d) => d.sequence)) {
      cols.push({
        id: 'sequence',
        header: 'Sequence',
        cell: (ctx) => {
          const s = ctx.row.original.sequence ?? ''
          return s.length > 60 ? `${s.slice(0, 60)}…` : s
        },
        meta: { tdClass: 'whitespace-normal break-all font-mono text-[10px]' },
      })
    }
    // Only include columns a chain actually populated — an always-empty column
    // reads as a bug.
    if (designs.some((d) => typeof d.rewards === 'number')) {
      cols.push({
        id: 'rewards',
        header: 'Reward',
        accessorFn: (r) => (typeof r.rewards === 'number' ? r.rewards.toFixed(4) : '—'),
      })
    }
    if (designs.some((d) => d.esmfold_validated != null)) {
      cols.push({
        id: 'validated',
        header: 'ESMFold',
        cell: (ctx) =>
          ctx.row.original.esmfold_validated ? (
            <span className="text-success">OK</span>
          ) : (
            <span className="text-muted-foreground">—</span>
          ),
      })
    }
    return cols
  }, [designs])

  // The backend renders Molstar HTML server-side (same helper the /stream routes
  // use), so the dialog never handles raw PDB text.
  const viewerHtml = useMemo(() => {
    const d = designs[selected] as { viewer_html?: string } | undefined
    return d?.viewer_html ?? (result.target_viewer_html as string | undefined) ?? null
  }, [designs, selected, result])

  if (res.isPending) return <p className="text-sm text-muted-foreground">Loading result…</p>
  if (res.error) return <p className="text-sm text-destructive">{String(res.error)}</p>
  if (res.data && res.data.status !== 'complete') {
    return (
      <p className="text-sm text-muted-foreground">
        This run is <strong>{res.data.status}</strong>
        {res.data.error ? ` — ${res.data.error}` : '. Results appear when it completes.'}
      </p>
    )
  }

  const scalars = Object.entries(result).filter(
    ([, v]) => typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean',
  )

  return (
    <div className="flex flex-col gap-4">
      {scalars.length > 0 && (
        <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs sm:grid-cols-3">
          {scalars.map(([k, v]) => (
            <div key={k}>
              <dt className="text-muted-foreground">{k.replace(/_/g, ' ')}</dt>
              <dd className="font-mono">{String(v).slice(0, 120)}</dd>
            </div>
          ))}
        </dl>
      )}

      {designs.length > 0 && (
        <>
          <DataTable data={designs} columns={columns} />
          {designs.length > 1 && (
            <label className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground">Show structure for</span>
              <select
                className="rounded-md border border-border bg-background px-2 py-1"
                value={selected}
                onChange={(e) => setSelected(Number(e.target.value))}
              >
                {designs.map((d, i) => (
                  <option key={i} value={i}>
                    {d.sample_id ?? `Design ${i + 1}`}
                  </option>
                ))}
              </select>
            </label>
          )}
          {viewerHtml && <MolstarViewer viewerHtml={viewerHtml} height={420} />}
        </>
      )}

      {designs.length === 0 && scalars.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Run completed but produced no tabular result. Open it in MLflow for the raw
          artifacts.
        </p>
      )}
    </div>
  )
}
