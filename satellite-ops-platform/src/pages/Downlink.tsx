import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useScoped } from '@/store/hooks'
import { Card, CardHeader, PageHeader, DemoTag, Badge } from '@/components/ui'
import { cn } from '@/lib/util'
import raw from '@/data/downlink.json'

interface Rec { seq: number; kind: string; sev: string; text: string; created: number; bytes: number; sent: number | null; received: number | null; attempts: number; pass: number | null; status: string; hash: string }
interface Pass { pass_id: number; start_s: number; duration_s: number; rate_bps: number; capacity_b: number; used_b: number; sent: number; delivered: number; lost: number; ground_available: boolean }
interface Sat { id: string; regime: string; buffer_bytes: number; rate_bps: number; loss: number; chain: { ok: boolean; dropped: number[]; undelivered_not_dropped: number[] }; passes: Pass[]; records: Rec[] }
const DATA = raw as unknown as { horizon_s: number; note: string; satellites: Sat[] }

const hms = (s: number | null | undefined) => (s == null ? '-' : `${String(Math.floor(s / 3600)).padStart(2, '0')}:${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`)
const dur = (s: number) => (s < 90 ? `${s.toFixed(0)} s` : s < 5400 ? `${(s / 60).toFixed(1)} min` : `${(s / 3600).toFixed(1)} h`)
const median = (a: number[]) => (a.length ? [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)] : null)
const STATUS_COLOR: Record<string, string> = { delivered: '#4ade80', retrying: '#fcd34d', buffered: '#7aa2ff', dropped: '#ff7b7b' }
const KINDS = ['audit', 'critical', 'event', 'housekeeping']

function stats(s: Sat) {
  const by = (st: string) => s.records.filter((r) => r.status === st).length
  const lat = (k?: string) => median(s.records.filter((r) => r.received != null && (!k || r.kind === k)).map((r) => r.received! - r.created))
  const delivered = by('delivered')
  const last = Math.max(0, ...s.records.map((r) => r.received ?? 0))
  return { total: s.records.length, delivered, buffered: by('buffered'), retrying: by('retrying'), dropped: by('dropped'), lastRx: last, auditLat: lat('audit'), allLat: lat(),
    missed: s.passes.filter((p) => !p.ground_available).length }
}

function Timeline({ sat }: { sat: Sat }) {
  const W = 960, H = 150, L = 78, T = DATA.horizon_s, x = (t: number) => L + ((W - L - 8) * t) / T
  const lane = (k: string) => 28 + KINDS.indexOf(k) * 20
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`24-hour downlink timeline for ${sat.id}`}>
      {[0, 4, 8, 12, 16, 20, 24].map((h) => <g key={h}><line x1={x(h * 3600)} x2={x(h * 3600)} y1={14} y2={H - 18} stroke="currentColor" strokeOpacity={0.12} /><text x={x(h * 3600)} y={H - 4} fontSize={10} textAnchor="middle" fill="currentColor" opacity={0.6}>{String(h).padStart(2, '0')}:00</text></g>)}
      <text x={4} y={10} fontSize={10} fill="currentColor" opacity={0.6}>contact passes</text>
      {sat.passes.map((p) => <rect key={p.pass_id} x={x(p.start_s)} y={14} width={Math.max(1.5, x(p.start_s + p.duration_s) - x(p.start_s))} height={8} rx={2} fill={p.ground_available ? '#4ade80' : '#ff7b7b'} opacity={0.85}><title>{`Pass ${p.pass_id} ${hms(p.start_s)} for ${dur(p.duration_s)}: ${p.ground_available ? `${p.delivered} delivered, ${p.lost} lost, ${p.used_b}/${p.capacity_b} B` : 'ground station unavailable - nothing sent'}`}</title></rect>)}
      {KINDS.map((k) => <text key={k} x={4} y={lane(k) + 14} fontSize={10} fill="currentColor" opacity={0.7}>{k}</text>)}
      {sat.records.map((r) => <circle key={r.seq} cx={x(r.created)} cy={lane(r.kind) + 10} r={r.kind === 'audit' ? 3 : 2} fill={STATUS_COLOR[r.status]} opacity={0.9}><title>{`#${r.seq} ${r.kind} created ${hms(r.created)} - ${r.status}${r.received != null ? `, received ${hms(r.received)}` : ''}`}</title></circle>)}
    </svg>
  )
}

function GroundAudit() {
  const base = import.meta.env.VITE_API_URL as string | undefined
  const [v, setV] = useState<{ ok: boolean } | null>(null)
  const [rows, setRows] = useState<{ seq: number; ts: number; category: string; actor: string; summary: string; hash: string }[]>([])
  useEffect(() => {
    if (!base) return
    let live = true
    const load = async () => { try { const [a, b] = await Promise.all([fetch(`${base}/audit/verify`).then((r) => r.json()), fetch(`${base}/audit?limit=8`).then((r) => r.json())]); if (live) { setV(a); setRows(b) } } catch { /* offline */ } }
    load(); const t = setInterval(load, 5000)
    return () => { live = false; clearInterval(t) }
  }, [base])
  return (
    <Card>
      <CardHeader title="Ground audit log (live)" sub={base ? 'Hash-chained log on the platform server' : 'Set VITE_API_URL to show the server log'} right={v && <Badge tone={v.ok ? 'text-ok border-ok/70 bg-ok/15' : 'text-bad border-bad/70 bg-bad/15'}>{v.ok ? 'chain intact' : 'CHAIN BROKEN'}</Badge>} />
      <ul className="p-4 space-y-1 text-xs font-mono max-h-48 overflow-y-auto">
        {rows.length === 0 && <li className="text-mute">{base ? 'No entries yet - approve or advance something.' : 'Not connected.'}</li>}
        {rows.map((r) => <li key={r.seq}><span className="text-mute">{new Date(r.ts * 1000).toLocaleTimeString()}</span> [{r.category}] {r.actor}: {r.summary} <span className="text-mute">#{r.hash.slice(0, 8)}</span></li>)}
      </ul>
    </Card>
  )
}

export default function Downlink() {
  const d = useScoped()
  const [sp, setSp] = useSearchParams()
  const visible = useMemo(() => DATA.satellites.filter((s) => d.satellites.some((x) => x.id === s.id)), [d.satellites])
  const sat = visible.find((s) => s.id === sp.get('sat')) ?? visible[0]
  const [kind, setKind] = useState('all')
  const [status, setStatus] = useState('all')
  if (!sat) return <><PageHeader title="Logs & Downlink" /><p className="text-mute">No satellites in scope.</p></>
  const name = (id: string) => d.satellites.find((s) => s.id === id)?.name ?? id
  const st = stats(sat)
  const rows = sat.records.filter((r) => (kind === 'all' || r.kind === kind) && (status === 'all' || r.status === status)).slice(-200).reverse()

  return (
    <>
      <PageHeader title="Logs & Downlink" sub="How and when each satellite sent its logs and audit records to the ground"
        actions={<><DemoTag text="Simulated 24 h - assumed traffic and links" /></>} />
      <Card className="mb-4 overflow-x-auto">
        <CardHeader title="Fleet downlink status" sub="Click a row. Latency = created on board → acknowledged at ground (median)" />
        <table className="w-full text-sm">
          <thead className="text-xs text-mute text-left"><tr>{['Satellite', 'Link', 'Passes (missed)', 'Records', 'Delivered', 'Waiting', 'Dropped', 'Audit latency', 'Last received', 'Chain'].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
          <tbody>
            {visible.map((s) => { const x = stats(s); return (
              <tr key={s.id} className={cn('border-t border-line cursor-pointer hover:bg-panel2', s.id === sat.id && 'bg-accent/10')} onClick={() => setSp({ sat: s.id })}>
                <td className="px-3 py-2">{name(s.id)} <span className="text-mute">({s.id})</span></td>
                <td className="px-3 py-2">{s.regime} · {(s.rate_bps / 1000).toFixed(1)} kbps</td>
                <td className="px-3 py-2">{s.passes.length}{x.missed > 0 && <span className="text-bad"> ({x.missed})</span>}</td>
                <td className="px-3 py-2">{x.total}</td>
                <td className="px-3 py-2">{((100 * x.delivered) / x.total).toFixed(0)}%</td>
                <td className="px-3 py-2">{x.buffered + x.retrying}</td>
                <td className={cn('px-3 py-2', x.dropped > 0 && 'text-bad')}>{x.dropped}</td>
                <td className="px-3 py-2">{x.auditLat == null ? '-' : dur(x.auditLat)}</td>
                <td className="px-3 py-2 font-mono text-xs">{hms(x.lastRx)}</td>
                <td className="px-3 py-2">{s.chain.dropped.length > 0 ? <span className="text-warn">gaps: {s.chain.dropped.length}</span> : <span className="text-ok">intact</span>}</td>
              </tr>) })}
          </tbody>
        </table>
      </Card>

      <div className="grid xl:grid-cols-3 gap-4 mb-4">
        <Card className="xl:col-span-2">
          <CardHeader title={`${name(sat.id)} - timeline`} sub={`${sat.regime}, buffer ${(sat.buffer_bytes / 1024).toFixed(0)} KB, link loss ${(100 * sat.loss).toFixed(0)}%. Dots = records at creation time; colour = status now`} />
          <div className="p-3"><Timeline sat={sat} />
            <div className="flex flex-wrap gap-3 text-xs mt-1">{Object.entries(STATUS_COLOR).map(([k, c]) => <span key={k} className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full" style={{ background: c }} />{k}</span>)}<span className="flex items-center gap-1"><span className="w-4 h-2 rounded bg-ok" />pass</span><span className="flex items-center gap-1"><span className="w-4 h-2 rounded bg-bad" />missed pass</span></div>
          </div>
        </Card>
        <div className="space-y-4">
          <Card className="p-4 text-sm space-y-1">
            <h4 className="font-semibold mb-1">How a record travels</h4>
            <p className="text-xs text-mute">1. Written to the on-board buffer with a sequence number and a hash that includes the previous record.</p>
            <p className="text-xs text-mute">2. Sent only during a contact pass, in priority order: audit, critical event, event, housekeeping, within the pass byte budget.</p>
            <p className="text-xs text-mute">3. Lost packets stay in the buffer and are retried next pass until acknowledged.</p>
            <p className="text-xs text-mute">4. If the buffer fills, housekeeping goes first and audit last; every drop leaves a visible gap in the sequence.</p>
            <p className="text-xs text-mute">5. The ground recomputes each hash and checks the chain.</p>
          </Card>
          <GroundAudit />
        </div>
      </div>

      <div className="grid xl:grid-cols-2 gap-4">
        <Card className="overflow-x-auto">
          <CardHeader title="Contact passes" sub={`${st.missed} missed · ${sat.passes.filter((p) => p.ground_available).length} held`} />
          <table className="w-full text-xs"><thead className="text-mute text-left"><tr>{['Pass', 'Start', 'Length', 'Rate', 'Bytes used / capacity', 'Sent', 'Delivered', 'Lost'].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
            <tbody className="font-mono">{sat.passes.filter((p) => p.sent > 0 || !p.ground_available).slice(0, 60).map((p) => (
              <tr key={p.pass_id} className={cn('border-t border-line', !p.ground_available && 'text-bad')}>
                <td className="px-3 py-1.5">{p.pass_id}</td><td className="px-3 py-1.5">{hms(p.start_s)}</td><td className="px-3 py-1.5">{dur(p.duration_s)}</td><td className="px-3 py-1.5">{(p.rate_bps / 1000).toFixed(1)}k</td>
                <td className="px-3 py-1.5">{p.ground_available ? `${p.used_b} / ${p.capacity_b}` : 'ground unavailable'}</td><td className="px-3 py-1.5">{p.sent}</td><td className="px-3 py-1.5">{p.delivered}</td><td className="px-3 py-1.5">{p.lost}</td></tr>))}</tbody></table>
        </Card>
        <Card className="overflow-x-auto">
          <CardHeader title="Records" sub="Latest 200 matching" right={<div className="flex gap-2">
            <select aria-label="Kind" className="input !py-1" value={kind} onChange={(e) => setKind(e.target.value)}><option value="all">all kinds</option>{KINDS.map((k) => <option key={k}>{k}</option>)}</select>
            <select aria-label="Status" className="input !py-1" value={status} onChange={(e) => setStatus(e.target.value)}><option value="all">all status</option>{Object.keys(STATUS_COLOR).map((k) => <option key={k}>{k}</option>)}</select></div>} />
          <table className="w-full text-xs"><thead className="text-mute text-left"><tr>{['#', 'Kind', 'Created', 'Sent', 'Received', 'Latency', 'Tries', 'Status', 'Hash'].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
            <tbody className="font-mono">{rows.map((r) => (
              <tr key={r.seq} className="border-t border-line" title={r.text}>
                <td className="px-3 py-1.5">{r.seq}</td><td className="px-3 py-1.5">{r.kind}</td><td className="px-3 py-1.5">{hms(r.created)}</td><td className="px-3 py-1.5">{hms(r.sent)}</td><td className="px-3 py-1.5">{hms(r.received)}</td>
                <td className="px-3 py-1.5">{r.received != null ? dur(r.received - r.created) : '-'}</td><td className="px-3 py-1.5">{r.attempts}</td>
                <td className="px-3 py-1.5" style={{ color: STATUS_COLOR[r.status] }}>{r.status}</td><td className="px-3 py-1.5 text-mute">{r.hash}</td></tr>))}</tbody></table>
        </Card>
      </div>
      <p className="text-xs text-mute mt-3">{DATA.note} Times are hours:minutes:seconds from the start of the simulated day.</p>
    </>
  )
}
