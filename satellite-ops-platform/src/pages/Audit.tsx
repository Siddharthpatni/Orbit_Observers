import { useState } from 'react'
import { Download } from 'lucide-react'
import { useScoped } from '@/store/hooks'
import { Card, PageHeader, SevBadge, Badge, Drawer, DemoTag, Empty } from '@/components/ui'
import { download, fmtDT, toCSV } from '@/lib/util'
import type { AuditEvent } from '@/lib/types'

export default function Audit() {
  const d = useScoped()
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('all')
  const [sev, setSev] = useState('all')
  const [sat, setSat] = useState('all')
  const [sel, setSel] = useState<AuditEvent | null>(null)
  const rows = d.audit.filter((a) => (cat === 'all' || a.category === cat) && (sev === 'all' || a.severity === sev) && (sat === 'all' || a.satId === sat) &&
    `${a.summary} ${a.actor} ${a.detail ?? ''} ${a.ref ?? ''}`.toLowerCase().includes(q.toLowerCase())).sort((a, b) => b.ts - a.ts)
  const exp = (fmt: 'csv' | 'json') => {
    const out = rows.map((a) => ({ id: a.id, time: fmtDT(a.ts), category: a.category, severity: a.severity, satellite: a.satId ?? '', actor: a.actor, summary: a.summary, detail: a.detail ?? '', ref: a.ref ?? '' }))
    download(`audit-log.${fmt}`, fmt === 'csv' ? toCSV(out) : JSON.stringify(out, null, 2), fmt === 'csv' ? 'text/csv' : 'application/json')
  }
  const report = () => {
    const cases = d.cases.map((c) => `${c.id} | ${c.satId} | ${c.problem} | stage ${c.stage}`).join('\n')
    const ms = d.missions.map((m) => `${m.id} | ${m.title} | phase ${Math.min(m.stage + 1, 11)}/11 | ${m.status}`).join('\n')
    download('mission-maintenance-report.txt', `ORBITCARE DEMO REPORT (simulated data)\nGenerated ${new Date().toISOString()}\n\nMAINTENANCE CASES\n${cases}\n\nMISSIONS\n${ms}\n`, 'text/plain')
  }

  return (
    <>
      <PageHeader title="Audit Logs & Reporting" sub="Unified, append-only record of operations (conceptual - local demo data is not tamper-proof)"
        actions={<><DemoTag /><button className="btn" onClick={() => exp('csv')}><Download size={14} />CSV</button><button className="btn" onClick={() => exp('json')}><Download size={14} />JSON</button><button className="btn btn-primary" onClick={report}>Mission & maintenance report</button></>} />
      <div className="flex flex-wrap gap-2 mb-3">
        <input aria-label="Search audit" className="input w-64" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select aria-label="Category" className="input" value={cat} onChange={(e) => setCat(e.target.value)}><option value="all">All categories</option>{['telemetry', 'agent', 'comms', 'policy', 'approval', 'ticket', 'mission', 'repair', 'system'].map((c) => <option key={c}>{c}</option>)}</select>
        <select aria-label="Severity" className="input" value={sev} onChange={(e) => setSev(e.target.value)}><option value="all">All severities</option>{['info', 'low', 'medium', 'high', 'critical'].map((c) => <option key={c}>{c}</option>)}</select>
        <select aria-label="Satellite" className="input" value={sat} onChange={(e) => setSat(e.target.value)}><option value="all">All satellites</option>{d.satellites.map((s) => <option key={s.id} value={s.id}>{s.id}</option>)}</select>
        <span className="text-xs text-mute self-center">{rows.length} records</span>
      </div>
      <Card className="overflow-x-auto">
        <table className="w-full">
          <thead><tr>{['Time', 'Category', 'Severity', 'Sat', 'Actor', 'Summary'].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>{rows.map((a) => (
            <tr key={a.id} tabIndex={0} className="cursor-pointer hover:bg-panel2" onClick={() => setSel(a)} onKeyDown={(e) => e.key === 'Enter' && setSel(a)}>
              <td className="td font-mono text-xs whitespace-nowrap">{fmtDT(a.ts)}</td><td className="td"><Badge>{a.category}</Badge></td><td className="td"><SevBadge sev={a.severity} /></td>
              <td className="td">{a.satId ?? '-'}</td><td className="td text-mute">{a.actor}</td><td className="td">{a.summary}</td>
            </tr>
          ))}</tbody>
        </table>
        {rows.length === 0 && <Empty text="No audit records match your filters." />}
      </Card>
      <Drawer open={!!sel} onClose={() => setSel(null)} title="Audit record">
        {sel && (
          <dl className="space-y-3 text-sm">
            {[['Record ID', sel.id], ['Timestamp', fmtDT(sel.ts)], ['Category', sel.category], ['Satellite', sel.satId ?? '-'], ['Actor', sel.actor], ['Reference', sel.ref ?? '-']].map(([k, v]) => <div key={k}><dt className="text-xs text-mute">{k}</dt><dd className="font-mono">{v}</dd></div>)}
            <div><dt className="text-xs text-mute">Summary</dt><dd>{sel.summary}</dd></div>
            {sel.detail && <div><dt className="text-xs text-mute">Detail</dt><dd>{sel.detail}</dd></div>}
            <SevBadge sev={sel.severity} />
          </dl>
        )}
      </Drawer>
    </>
  )
}
