import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Check, Lock, Play, Printer } from 'lucide-react'
import { useScoped } from '@/store/hooks'
import { Card, CardHeader, PageHeader, RiskBadge, StatusBadge, DemoTag, Empty } from '@/components/ui'
import { api } from '@/services/api'
import FeasibilityCard from '@/components/FeasibilityCard'
import { canOperate } from '@/lib/access'
import { MISSION_STAGES } from '@/lib/types'
import { cn, fmtDT } from '@/lib/util'

export default function Missions() {
  const d = useScoped()
  const [sp, setSp] = useSearchParams()
  const [err, setErr] = useState('')
  const m = d.missions.find((x) => x.id === sp.get('m')) ?? d.missions[0]
  const sat = (id: string) => d.satellites.find((s) => s.id === id)
  const mayOp = canOperate(d.role)

  if (!m) return <><PageHeader title="Servicing Missions" /><Empty text="No missions." /></>
  const complete = m.stage >= 11
  const gate = m.gates[m.stage]
  const gateAp = d.approvals.find((a) => a.id === gate)
  const blocked = !!gate && gateAp?.status !== 'approved'
  const case_ = d.cases.find((c) => c.id === m.caseId)
  const comp = sat(m.satId)?.components.find((c) => c.id === case_?.componentId)

  return (
    <>
      <PageHeader title="Servicing Missions" sub="Eleven-stage lifecycle with approval gates" actions={<><DemoTag text="Simulated - no spacecraft control" /><select aria-label="Mission" className="input" value={m.id} onChange={(e) => { setSp({ m: e.target.value }); setErr('') }}>{d.missions.map((x) => <option key={x.id} value={x.id}>{x.id} - {x.title}</option>)}</select></>} />
      <div className="grid xl:grid-cols-3 gap-4">
        <Card className="xl:col-span-2">
          <CardHeader title={m.title} sub={`${m.id} · servicer ${sat(m.servicerId)?.name} → ${sat(m.satId)?.name}`} right={<div className="flex gap-2"><RiskBadge risk={m.risk} /><StatusBadge s={m.status} /></div>} />
          <ol className="p-4 space-y-0">
            {MISSION_STAGES.map((s, i) => {
              const done = i < m.stage, cur = i === m.stage && !complete
              const g = m.gates[i]
              return (
                <li key={s} className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <span className={cn('w-6 h-6 rounded-full grid place-items-center text-xs border', done ? 'bg-ok/20 border-ok text-ok' : cur ? 'border-accent text-accent' : 'border-line text-mute')}>{done ? <Check size={12} /> : i + 1}</span>
                    {i < 10 && <span className={cn('flex-1 w-px min-h-4', done ? 'bg-ok/50' : 'bg-line')} />}
                  </div>
                  <div className="pb-3"><div className={cn('text-sm', cur && 'text-accent font-medium', !done && !cur && 'text-mute')}>{s}</div>
                    {g && <div className="text-xs flex items-center gap-1 text-warn"><Lock size={10} />Approval gate: {g} ({d.approvals.find((a) => a.id === g)?.status ?? 'missing'})</div>}</div>
                </li>
              )
            })}
          </ol>
          <div className="px-4 pb-4 border-t border-line pt-3">
            {complete ? <span className="text-ok text-sm">Mission complete.</span> : (
              <div className="flex flex-wrap items-center gap-3">
                <button className="btn btn-primary" disabled={!mayOp} onClick={() => { const r = api.advanceMission(m.id); setErr(r.ok ? '' : r.reason ?? '') }}><Play size={14} />Advance to “{MISSION_STAGES[m.stage + 1] ?? 'Complete'}”</button>
                {!mayOp && <span className="text-xs text-mute">Operator or engineer role required.</span>}
                {blocked && <span className="text-xs text-warn">Blocked: {gate} requires human approval - <Link className="underline" to="/approvals">open approvals</Link></span>}
                {err && <span className="text-xs text-bad" role="alert">{err}</span>}
              </div>
            )}
          </div>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardHeader title="Checklist" sub={`${m.checklist.filter((c) => c.done).length}/${m.checklist.length}`} />
            <ul className="p-4 space-y-1.5 text-sm">{m.checklist.map((c) => <li key={c.text} className={cn('flex gap-2', !c.done && 'text-mute')}><Check size={14} className={c.done ? 'text-ok' : 'opacity-20'} />{c.text}</li>)}</ul>
          </Card>
          <FeasibilityCard sat={sat(m.satId)} />
          <Card className="p-4 text-sm"><h4 className="font-semibold mb-2">Assigned assets</h4>
            <div>{sat(m.servicerId)?.name} <span className="text-mute">({m.servicerId})</span></div><div>{sat(m.satId)?.name} <span className="text-mute">({m.satId})</span></div></Card>
          <Card>
            <CardHeader title="Event log" />
            <ul className="p-4 space-y-1.5 text-xs font-mono max-h-56 overflow-y-auto">{[...m.events].reverse().map((e, i) => <li key={i}><span className="text-mute">{fmtDT(e.ts)}</span> {e.text}</li>)}</ul>
          </Card>
        </div>
      </div>
      {complete && (
        <Card className="mt-4 p-5" >
          <div className="flex justify-between"><h3 className="font-semibold">Mission summary</h3><button className="btn" onClick={() => window.print()}><Printer size={14} />Print / save PDF</button></div>
          <div className="text-sm mt-3 space-y-1.5">
            <p><span className="text-mute">Mission:</span> {m.title} ({m.id})</p>
            <p><span className="text-mute">Outcome:</span> {case_?.report ?? 'Completed.'}</p>
            {comp && <p><span className="text-mute">Component now:</span> {comp.name} - health {comp.health}% ({comp.risk} risk)</p>}
            <p className="text-xs text-warn">All data is simulated demo data.</p>
          </div>
        </Card>
      )}
    </>
  )
}
