import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Check, FilePlus, Printer } from 'lucide-react'
import { useScoped } from '@/store/hooks'
import { Card, CardHeader, PageHeader, SevBadge, StatusBadge, Drawer, DemoTag, Empty } from '@/components/ui'
import { api } from '@/services/api'
import { canOperate } from '@/lib/access'
import { LIFECYCLE } from '@/lib/types'
import { cn, fmtDT } from '@/lib/util'

export default function Maintenance() {
  const d = useScoped()
  const [sp, setSp] = useSearchParams()
  const [sev, setSev] = useState('all')
  const sel = d.cases.find((c) => c.id === sp.get('c'))
  const rows = d.cases.filter((c) => sev === 'all' || c.severity === sev)
  const sat = (id: string) => d.satellites.find((s) => s.id === id)?.name ?? id
  const comp = (c: typeof rows[0]) => d.satellites.find((s) => s.id === c.satId)?.components.find((x) => x.id === c.componentId)
  const ap = (id?: string) => d.approvals.find((a) => a.id === id)

  return (
    <>
      <PageHeader title="Maintenance & Repair" sub="AI-generated recommendations through completion" actions={<><DemoTag /><select aria-label="Severity" className="input" value={sev} onChange={(e) => setSev(e.target.value)}><option value="all">All severities</option>{['low', 'medium', 'high', 'critical'].map((s) => <option key={s}>{s}</option>)}</select></>} />
      <Card className="overflow-x-auto">
        <table className="w-full">
          <thead><tr>{['Case', 'Satellite', 'Component', 'Problem', 'Severity', 'Urgency', 'Lifecycle', 'Approval'].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id} tabIndex={0} className="cursor-pointer hover:bg-panel2" onClick={() => setSp({ c: c.id })} onKeyDown={(e) => e.key === 'Enter' && setSp({ c: c.id })}>
                <td className="td font-mono text-xs">{c.id}</td><td className="td">{sat(c.satId)}</td><td className="td">{comp(c)?.name}</td><td className="td">{c.problem}</td>
                <td className="td"><SevBadge sev={c.severity} /></td><td className="td text-mute">{c.urgency}</td>
                <td className="td"><Lifecycle stage={c.stage} compact /></td>
                <td className="td">{ap(c.approvalId) ? <StatusBadge s={ap(c.approvalId)!.status} /> : <span className="text-mute text-xs">n/a</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <Empty text="No maintenance cases." />}
      </Card>

      <Drawer open={!!sel} onClose={() => setSp({})} title={sel ? `${sel.id} · ${sat(sel.satId)}` : ''} width="max-w-2xl">
        {sel && (
          <div className="space-y-5 text-sm">
            <Lifecycle stage={sel.stage} />
            <div><h4 className="font-semibold">Detected problem</h4><p className="text-mute">{sel.problem}</p></div>
            <div><h4 className="font-semibold">Supporting evidence</h4><ul className="list-disc pl-5 text-mute">{sel.evidence.map((e) => <li key={e}>{e}</li>)}</ul></div>
            <div><h4 className="font-semibold">Recommendation</h4><p className="text-mute">{sel.recommendation}</p></div>
            <div className="grid grid-cols-2 gap-3">
              <div><div className="text-xs text-mute">Urgency</div>{sel.urgency}</div><div><div className="text-xs text-mute">Suggested window</div>{sel.window}</div>
              <div><div className="text-xs text-mute">Resources</div>{sel.resources.join(', ')}</div><div><div className="text-xs text-mute">Created</div>{fmtDT(sel.createdAt)}</div>
            </div>
            <div className="flex flex-wrap gap-3 text-xs">
              {sel.approvalId && <Link className="text-accent" to="/approvals">Approval {sel.approvalId} ({ap(sel.approvalId)?.status})</Link>}
              {sel.missionId && <Link className="text-accent" to={`/missions?m=${sel.missionId}`}>Mission {sel.missionId}</Link>}
              <Link className="text-accent" to={`/monitoring?sat=${sel.satId}&comp=${encodeURIComponent(sel.componentId)}`}>Telemetry</Link>
            </div>
            {sel.report && <div className="card p-3"><h4 className="font-semibold mb-1">Diagnostic / service report</h4>{sel.report}</div>}
            {canOperate(d.role) && (
              <div className="flex flex-wrap gap-2 border-t border-line pt-3">
                {sel.workOrder ? <span className="text-ok flex items-center gap-1"><Check size={14} />Work order {sel.workOrder}</span> : <button className="btn btn-primary" onClick={() => api.createWorkOrder(sel.id)}><FilePlus size={14} />Create work order</button>}
                {sel.stage < 3 && <button className="btn" onClick={() => api.setCaseStage(sel.id, sel.stage + 1)}>Advance to {LIFECYCLE[sel.stage + 1]}</button>}
                {sel.stage === 3 && <span className="text-warn text-xs self-center">Awaiting human approval - cannot be advanced manually.</span>}
                {sel.report && <button className="btn" onClick={() => window.print()}><Printer size={14} />Print report</button>}
              </div>
            )}
          </div>
        )}
      </Drawer>
    </>
  )
}

export function Lifecycle({ stage, compact }: { stage: number; compact?: boolean }) {
  if (compact) return <span className="text-xs">{LIFECYCLE[stage]} <span className="text-mute">({stage + 1}/8)</span></span>
  return (
    <ol className="flex flex-wrap gap-y-2" aria-label="Maintenance lifecycle">
      {LIFECYCLE.map((s, i) => (
        <li key={s} className="flex items-center">
          <span className={cn('text-xs px-2 py-1 rounded border', i < stage ? 'border-ok/70 text-ok bg-ok/15' : i === stage ? 'border-accent text-accent bg-accent/15' : 'border-line text-mute')}>{s}</span>
          {i < LIFECYCLE.length - 1 && <span className="w-3 h-px bg-line" />}
        </li>
      ))}
    </ol>
  )
}
