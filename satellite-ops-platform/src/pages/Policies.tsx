import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useScoped } from '@/store/hooks'
import { Card, CardHeader, PageHeader, StatusBadge, Modal, Badge, DemoTag } from '@/components/ui'
import { api } from '@/services/api'
import { canEditPolicy } from '@/lib/access'
import type { Policy } from '@/lib/types'
import { cn, fmtDT } from '@/lib/util'
import { useStore } from '@/store/useStore'

const ACTIONS = ['Request telemetry', 'Run diagnostics', 'Draft work orders', 'Generate recommendations', 'Open comm session', 'Send servicing command']
const HUMAN = ['Mission initiation', 'Close-proximity operations', 'Component replacement', 'Configuration change', 'Hazardous command']

export default function Policies() {
  const d = useScoped()
  const [sp, setSp] = useSearchParams()
  const pol = d.policies.find((p) => p.id === sp.get('p')) ?? d.policies[0]
  const [edit, setEdit] = useState<Policy | null>(null)
  const [note, setNote] = useState('')
  const evaluate = useStore((s) => s.evaluateAction)
  const [test, setTest] = useState(HUMAN[2])
  const evals = d.evals.filter((e) => e.policyId === pol?.id)
  const toggle = (arr: string[], v: string) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v])

  if (!pol) return <div className="text-mute">No policies.</div>
  const editable = canEditPolicy(d.role)

  return (
    <>
      <PageHeader title="Service Policy & Compliance" sub="Policies decide what AI agents may do alone and what needs a human"
        actions={<><DemoTag /><select aria-label="Policy" className="input" value={pol.id} onChange={(e) => setSp({ p: e.target.value })}>{d.policies.map((p) => <option key={p.id} value={p.id}>{p.satId} - {p.name}</option>)}</select>
          {editable && <button className="btn btn-primary" onClick={() => { setEdit(structuredClone(pol)); setNote('') }}>Edit policy</button>}</>} />
      <div className="grid xl:grid-cols-3 gap-4">
        <Card className="xl:col-span-2">
          <CardHeader title={`${pol.name}`} sub={`${pol.id} · version ${pol.version} · satellite ${pol.satId}`} />
          <div className="p-4 grid md:grid-cols-2 gap-4 text-sm">
            <Block t="Authorized diagnostics" items={pol.diagnostics} />
            <Block t="Permitted communication categories" items={pol.commCategories} />
            <Block t="Approved servicing procedures" items={pol.procedures} />
            <Block t="Actions permitted for AI agents" items={pol.aiAllowed} tone="text-ok" />
            <Block t="Actions requiring human approval" items={pol.humanRequired} tone="text-warn" />
            <div><h4 className="font-semibold mb-1">Conditions</h4><ul className="text-mute space-y-1">
              <li>IF health &lt; <b className="text-ink">{pol.escalationThreshold}%</b> THEN escalate to human</li>
              <li>ONLY within: <b className="text-ink">{pol.windows}</b></li>
              <li>Customer authorization: <b className="text-ink">{pol.customerAuth ? 'required' : 'not required'}</b></li>
              <li>Emergency hold: {pol.emergencyHold}</li></ul></div>
          </div>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardHeader title="Version history" />
            <ol className="p-4 space-y-2 text-sm">{[...pol.versions].reverse().map((v) => <li key={v.v}><b>v{v.v}</b> <span className="text-mute">{v.date} · {v.author}</span><div className="text-mute">{v.note}</div></li>)}</ol>
          </Card>
          <Card>
            <CardHeader title="Test the policy engine" sub="Generates a real evaluation log" />
            <div className="p-4 flex gap-2">
              <select aria-label="Action to evaluate" className="input flex-1" value={test} onChange={(e) => setTest(e.target.value)}>{[...ACTIONS, ...HUMAN].map((a) => <option key={a}>{a}</option>)}</select>
              <button className="btn btn-primary" onClick={() => evaluate(pol.satId, 'AI Operations Supervisor (test)', test, test)}>Evaluate</button>
            </div>
          </Card>
        </div>
      </div>
      <Card className="mt-4 overflow-x-auto">
        <CardHeader title="Policy evaluation log" sub="Append-only records (conceptual; local demo data is not tamper-proof)" />
        <table className="w-full text-sm">
          <thead><tr>{['Event', 'Time', 'Sat', 'Actor', 'Requested action', 'Policy', 'Decision', 'Reason', 'Ref'].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>{evals.map((e) => (
            <tr key={e.id}><td className="td font-mono text-xs">{e.id}</td><td className="td font-mono text-xs">{fmtDT(e.ts)}</td><td className="td">{e.satId}</td><td className="td">{e.actor}</td><td className="td">{e.action}</td>
              <td className="td">{e.policyId} v{e.version}</td><td className="td"><StatusBadge s={e.decision} /></td><td className="td text-mute">{e.reason}</td><td className="td font-mono text-xs">{e.ref ?? '-'}</td></tr>
          ))}</tbody>
        </table>
        {evals.length === 0 && <div className="p-6 text-center text-sm text-mute">No evaluations for this policy yet.</div>}
      </Card>

      <Modal open={!!edit} onClose={() => setEdit(null)} title={`Edit ${pol.id} → v${pol.version + 1}`}
        footer={<><button className="btn" onClick={() => setEdit(null)}>Cancel</button><button className="btn btn-primary" disabled={!note.trim()} onClick={() => { api.savePolicy(edit!, note); setEdit(null) }}>Save new version</button></>}>
        {edit && (
          <div className="space-y-3 text-sm max-h-[60vh] overflow-y-auto">
            <label className="block">Escalation threshold (health %)<input type="number" min={10} max={95} className="input w-full mt-1" value={edit.escalationThreshold} onChange={(e) => setEdit({ ...edit, escalationThreshold: +e.target.value })} /></label>
            <label className="block">Operating windows<input className="input w-full mt-1" value={edit.windows} onChange={(e) => setEdit({ ...edit, windows: e.target.value })} /></label>
            <label className="flex gap-2"><input type="checkbox" checked={edit.customerAuth} onChange={(e) => setEdit({ ...edit, customerAuth: e.target.checked })} />Customer authorization required</label>
            <fieldset><legend className="font-semibold mb-1">Requires human approval</legend>
              {HUMAN.map((h) => <label key={h} className="flex gap-2"><input type="checkbox" checked={edit.humanRequired.includes(h)} onChange={() => setEdit({ ...edit, humanRequired: toggle(edit.humanRequired, h) })} />{h}</label>)}</fieldset>
            <label className="block">Change note (required)<input className="input w-full mt-1" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why is this changing?" /></label>
          </div>
        )}
      </Modal>
    </>
  )
}

function Block({ t, items, tone }: { t: string; items: string[]; tone?: string }) {
  return <div><h4 className="font-semibold mb-1">{t}</h4><div className="flex flex-wrap gap-1.5">{items.map((i) => <Badge key={i} tone={cn('border-line', tone)}>{i}</Badge>)}</div></div>
}
