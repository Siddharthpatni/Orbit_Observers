import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, X, HelpCircle, Pause } from 'lucide-react'
import { useScoped } from '@/store/hooks'
import { Card, PageHeader, StatusBadge, RiskBadge, Modal, DemoTag, Empty } from '@/components/ui'
import { api } from '@/services/api'
import { canDecide } from '@/lib/access'
import type { Approval } from '@/lib/types'
import { cn, fmtDT } from '@/lib/util'

type Decision = 'approved' | 'rejected' | 'hold' | 'info-requested'
const LABEL: Record<Decision, string> = { approved: 'Approve', rejected: 'Reject', hold: 'Place on hold', 'info-requested': 'Request more information' }

export default function Approvals() {
  const d = useScoped()
  const [filter, setFilter] = useState('pending')
  const [selId, setSelId] = useState<string>()
  const [err, setErr] = useState('')
  const [dlg, setDlg] = useState<Decision | null>(null)
  const [notes, setNotes] = useState('')
  const list = d.approvals.filter((a) => filter === 'all' || (filter === 'pending' ? ['pending', 'hold', 'info-requested'].includes(a.status) : a.status === filter))
  const sel = d.approvals.find((a) => a.id === selId) ?? list[0]
  const mayDecide = canDecide(d.role)
  const open = sel && ['pending', 'hold', 'info-requested'].includes(sel.status)
  const needNotes = dlg === 'approved' || dlg === 'rejected'
  const sat = (a: Approval) => d.satellites.find((s) => s.id === a.satId)?.name ?? a.satId

  return (
    <>
      <PageHeader title="Human-in-the-Loop Approvals" sub="Mission-critical actions are never authorized until a human decision is recorded" actions={<DemoTag />} />
      <div className="flex gap-2 mb-4">{['pending', 'approved', 'rejected', 'all'].map((f) => <button key={f} className={cn('btn capitalize', filter === f && 'btn-primary')} onClick={() => setFilter(f)}>{f}</button>)}</div>
      <div className="grid xl:grid-cols-3 gap-4">
        <div className="space-y-2">
          {list.length === 0 && <Card><Empty text="No requests in this view." /></Card>}
          {list.map((a) => (
            <Card key={a.id} onClick={() => setSelId(a.id)} className={cn('p-3', sel?.id === a.id && 'border-accent')}>
              <div className="flex justify-between"><span className="font-mono text-xs text-mute">{a.id}</span><StatusBadge s={a.status} /></div>
              <div className="text-sm font-medium mt-1">{a.operation}</div>
              <div className="flex gap-2 mt-2"><RiskBadge risk={a.risk} /><span className="text-xs text-mute">{a.kind}</span></div>
            </Card>
          ))}
        </div>
        <Card className="xl:col-span-2 p-5">
          {!sel ? <Empty text="Select a request." /> : (
            <div className="space-y-4 text-sm">
              <div className="flex justify-between items-start gap-3">
                <div><h2 className="text-lg font-semibold">{sel.operation}</h2><p className="text-mute">{sel.id} · {sel.kind} · {sat(sel)}</p></div>
                <div className="flex gap-2"><RiskBadge risk={sel.risk} /><StatusBadge s={sel.status} /></div>
              </div>
              {sel.status !== 'approved' && <div className="border border-warn/70 bg-warn/5 text-warn rounded p-2 text-xs">NOT AUTHORIZED - this action must not proceed until a human approval is recorded.</div>}
              {sel.status === 'approved' && <div className="border border-ok/70 bg-ok/5 text-ok rounded p-2 text-xs">Authorized by {sel.decidedBy} at {fmtDT(sel.decidedAt!)}.</div>}
              <dl className="grid md:grid-cols-2 gap-3">
                {[['Requester', sel.requester], ['Assigned reviewer', sel.reviewer], ['Created', fmtDT(sel.createdAt)], ['Applicable policy', sel.policyId]].map(([k, v]) => <div key={k}><dt className="text-xs text-mute">{k}</dt><dd>{v}</dd></div>)}
                <div><dt className="text-xs text-mute">Mission / ticket</dt><dd>{sel.missionId && <Link className="text-accent" to={`/missions?m=${sel.missionId}`}>{sel.missionId}</Link>} {sel.caseId && <Link className="text-accent" to="/maintenance">{sel.caseId}</Link>}</dd></div>
              </dl>
              <div><h4 className="font-semibold">Technical justification</h4><p className="text-mute">{sel.justification}</p></div>
              <div><h4 className="font-semibold">Supporting telemetry</h4><ul className="list-disc pl-5 text-mute">{sel.telemetry.map((t) => <li key={t}>{t}</li>)}</ul><Link className="text-accent text-xs" to={`/monitoring?sat=${sel.satId}`}>Open telemetry →</Link></div>
              <div className="grid md:grid-cols-2 gap-3"><div><h4 className="font-semibold">Consequences</h4><p className="text-mute">{sel.consequences}</p></div><div><h4 className="font-semibold">Proposed mitigation</h4><p className="text-mute">{sel.mitigation}</p></div></div>
              {sel.notes && <div className="card p-3"><div className="text-xs text-mute">Decision notes</div>{sel.notes}</div>}
              {open && (mayDecide ? (
                <div className="flex flex-wrap gap-2 pt-2 border-t border-line">
                  <button className="btn btn-ok" onClick={() => { setDlg('approved'); setNotes('') }}><Check size={14} />Approve</button>
                  <button className="btn btn-bad" onClick={() => { setDlg('rejected'); setNotes('') }}><X size={14} />Reject</button>
                  <button className="btn" onClick={() => { setDlg('info-requested'); setNotes('') }}><HelpCircle size={14} />Request more info</button>
                  <button className="btn btn-warn" onClick={() => { setDlg('hold'); setNotes('') }}><Pause size={14} />Place on hold</button>
                </div>
              ) : <p className="text-xs text-mute pt-2 border-t border-line">Switch to the “Human Approval Authority” role to decide (role simulation only).</p>)}
            </div>
          )}
        </Card>
      </div>
      <Modal open={!!dlg} onClose={() => setDlg(null)} title={dlg ? `${LABEL[dlg]}: ${sel?.id}` : ''}
        footer={<><button className="btn" onClick={() => setDlg(null)}>Cancel</button><button className={cn('btn', dlg === 'approved' ? 'btn-ok' : dlg === 'rejected' ? 'btn-bad' : 'btn-primary')} disabled={needNotes && !notes.trim()} onClick={async () => { const r = await api.decideApproval(sel!.id, dlg!, notes || LABEL[dlg!]); if (r.ok) { setErr(''); setDlg(null) } else setErr(r.reason ?? 'Rejected by server') }}>Confirm</button></>}>
        <p className="text-sm text-mute mb-2">{dlg === 'approved' ? 'This records authorization and advances the linked ticket and mission.' : 'This decision is written to the audit log.'}</p>
        {err && <p className="text-sm text-bad mb-2" role="alert">{err}</p>}
        <label className="text-sm">Decision notes {needNotes && <span className="text-bad">*</span>}<textarea className="input w-full mt-1 h-24" value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
      </Modal>
    </>
  )
}
