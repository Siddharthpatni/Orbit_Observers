import { useState } from 'react'
import { Download } from 'lucide-react'
import { useScoped } from '@/store/hooks'
import { Card, CardHeader, PageHeader, StatusBadge, Drawer, Badge, DemoTag, Empty } from '@/components/ui'
import type { CommMsg } from '@/lib/types'
import { cn, download, fmtDT, fmtTime, toCSV } from '@/lib/util'

export default function Comms() {
  const d = useScoped()
  const [sid, setSid] = useState('all')
  const [q, setQ] = useState('')
  const [dir, setDir] = useState('all')
  const [cat, setCat] = useState('all')
  const [msg, setMsg] = useState<CommMsg | null>(null)
  const name = (id: string) => d.satellites.find((s) => s.id === id)?.name ?? d.satellites.find((s) => s.id === id)?.id ?? id
  const cats = Array.from(new Set(d.messages.map((m) => m.category)))
  const rows = d.messages.filter((m) => (sid === 'all' || m.sessionId === sid) && (dir === 'all' || m.dir === dir) && (cat === 'all' || m.category === cat) && `${m.text} ${m.category}`.toLowerCase().includes(q.toLowerCase())).sort((a, b) => b.ts - a.ts)
  const sess = (id: string) => d.sessions.find((s) => s.id === id)
  const exp = (fmt: 'csv' | 'json') => {
    const out = rows.map((m) => ({ time: fmtDT(m.ts), session: m.sessionId, direction: m.dir, category: m.category, message: m.text, state: m.state, policy: m.policyId ?? '' }))
    download(`comms-log.${fmt}`, fmt === 'csv' ? toCSV(out) : JSON.stringify(out, null, 2), fmt === 'csv' ? 'text/csv' : 'application/json')
  }

  return (
    <>
      <PageHeader title="Satellite-to-Satellite Communications" sub="Servicer ↔ customer sessions during approved operations" actions={<><DemoTag text="Simulated - no commands transmitted" /><button className="btn" onClick={() => exp('csv')}><Download size={14} />CSV</button><button className="btn" onClick={() => exp('json')}><Download size={14} />JSON</button></>} />
      <Card className="mb-4 overflow-x-auto">
        <CardHeader title="Sessions" />
        <table className="w-full">
          <thead><tr>{['Session', 'Servicer', 'Customer sat', 'Status', 'Authorization', 'Start', 'End', 'Signal', 'Latency'].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>
            {d.sessions.map((s) => (
              <tr key={s.id} tabIndex={0} className={cn('cursor-pointer hover:bg-panel2', sid === s.id && 'bg-accent/5')} onClick={() => setSid(sid === s.id ? 'all' : s.id)} onKeyDown={(e) => e.key === 'Enter' && setSid(s.id)}>
                <td className="td font-mono">{s.id}</td><td className="td">{name(s.servicerId)}</td><td className="td">{name(s.satId)}</td>
                <td className="td"><StatusBadge s={s.status} /></td><td className="td"><StatusBadge s={s.authorized === 'denied' ? 'denied' : 'authorized'} /></td>
                <td className="td font-mono text-xs">{fmtDT(s.start)}</td><td className="td font-mono text-xs">{s.end ? fmtDT(s.end) : '-'}</td>
                <td className="td">{s.quality ? `${s.quality}%` : '-'}</td><td className="td">{s.latencyMs ? `${s.latencyMs} ms` : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {d.sessions.length === 0 && <Empty text="No sessions." />}
      </Card>
      <div className="flex flex-wrap gap-2 mb-3">
        <input aria-label="Search log" className="input w-64" placeholder="Search messages…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select aria-label="Direction" className="input" value={dir} onChange={(e) => setDir(e.target.value)}><option value="all">All directions</option><option>TX</option><option>RX</option><option>SYS</option></select>
        <select aria-label="Category" className="input" value={cat} onChange={(e) => setCat(e.target.value)}><option value="all">All categories</option>{cats.map((c) => <option key={c}>{c}</option>)}</select>
        {sid !== 'all' && <button className="btn" onClick={() => setSid('all')}>Clear session filter ({sid})</button>}
      </div>
      <Card className="overflow-x-auto">
        <table className="w-full font-mono text-xs">
          <thead><tr><th className="th">Time</th><th className="th">Session</th><th className="th">Dir</th><th className="th">Category</th><th className="th">Message</th><th className="th">State</th></tr></thead>
          <tbody>
            {rows.map((m) => (
              <tr key={m.id} tabIndex={0} className="cursor-pointer hover:bg-panel2" onClick={() => setMsg(m)} onKeyDown={(e) => e.key === 'Enter' && setMsg(m)}>
                <td className="td">{fmtTime(m.ts)}</td><td className="td">{m.sessionId}</td><td className="td"><Badge tone={m.dir === 'TX' ? 'text-accent border-accent/70' : m.dir === 'RX' ? 'text-info border-info/70' : undefined}>{m.dir}</Badge></td>
                <td className="td font-sans">{m.category}</td><td className="td font-sans text-sm">{m.text}</td><td className="td"><StatusBadge s={m.state} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <Empty text="No log entries match." />}
      </Card>
      <Drawer open={!!msg} onClose={() => setMsg(null)} title="Message detail">
        {msg && (
          <dl className="text-sm space-y-3">
            {[['ID', msg.id], ['Timestamp', fmtDT(msg.ts)], ['Session', msg.sessionId], ['Direction', msg.dir], ['Category', msg.category], ['Policy', msg.policyId ?? 'n/a'], ['State', msg.state]].map(([k, v]) => <div key={k}><dt className="text-mute text-xs">{k}</dt><dd>{v}</dd></div>)}
            <div><dt className="text-mute text-xs">Payload</dt><dd className="card p-3 font-mono text-xs">{msg.text}</dd></div>
            <DemoTag text="Simulated message - not transmitted" />
          </dl>
        )}
      </Drawer>
    </>
  )
}
