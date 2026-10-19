import { useEffect, useState } from 'react'
import { Card, CardHeader } from '@/components/ui'
import { fetchFeasibility, type Feasibility } from '@/services/api'
import { TIER_LABEL, type Satellite } from '@/lib/types'
import { cn } from '@/lib/util'

const pct = (x: number) => `${(x * 100).toFixed(1)}%`

/** Shows Monte Carlo evidence for approaching this client given its serviceability tier. Evidence only: a human still decides. */
export default function FeasibilityCard({ sat }: { sat?: Satellite }) {
  const [f, setF] = useState<Feasibility | null | undefined>(undefined)
  const tier = sat?.serviceTier
  const tumble = sat?.estTumbleDegS
  useEffect(() => {
    let live = true
    if (tier && tumble !== undefined) fetchFeasibility(tier, tumble).then((r) => live && setF(r))
    else setF(null)
    return () => { live = false }
  }, [tier, tumble])

  return (
    <Card>
      <CardHeader title="Approach feasibility (model evidence)" sub={tier ? `${TIER_LABEL[tier]} · est. tumble ${tumble} °/s` : 'No serviceability tier recorded'} />
      <div className="p-4 text-sm space-y-2">
        {!tier && <p className="text-mute">Client has no recorded provisions; treat as C0 (unprepared) until confirmed.</p>}
        {tier && f === undefined && <p className="text-mute">Loading…</p>}
        {f && (
          <>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div><div className={cn('text-lg font-semibold', f.cell.p_terminal_pass >= 0.9 ? 'text-ok' : f.cell.p_terminal_pass >= 0.5 ? 'text-warn' : 'text-bad')}>{pct(f.cell.p_terminal_pass)}</div><div className="text-xs text-mute">terminal window met<br />[{pct(f.cell.p_terminal_pass_ci95_low)}–{pct(f.cell.p_terminal_pass_ci95_high)}]</div></div>
              <div><div className="text-lg font-semibold">{pct(f.cell.p_abort)}</div><div className="text-xs text-mute">abort</div></div>
              <div><div className="text-lg font-semibold">{f.cell.n_unsafe}/{f.cell.n_runs}</div><div className="text-xs text-mute">keep-out violations</div></div>
            </div>
            {!f.withinRange && <p className="text-xs text-bad" role="alert">Outside the tested range — no evidence for this tumble rate.</p>}
            {f.notes.map((n) => <p key={n} className="text-xs text-warn">{n}</p>)}
            <p className="text-xs text-mute">{f.provenance.model_version} · config {f.provenance.config_hash} · seed {f.provenance.master_seed} · {f.provenance.paired_seeds_per_cell} paired seeds/cell · source: {f.source}</p>
            <p className="text-xs text-mute">{f.caveat}</p>
          </>
        )}
        {f === null && tier && <p className="text-mute">No campaign data for this tier.</p>}
      </div>
    </Card>
  )
}
