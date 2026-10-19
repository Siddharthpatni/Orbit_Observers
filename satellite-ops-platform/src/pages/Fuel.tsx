import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useScoped } from '@/store/hooks'
import { Card, CardHeader, PageHeader, DemoTag, Badge } from '@/components/ui'
import { cn } from '@/lib/util'
import raw from '@/data/fuel.json'

interface Summary { fused_kg: number; sigma_kg: number; pct_load: number; dv_mps: number; dv_lo: number; dv_hi: number; rate_mps_yr: number; years_to_reserve: number | null; status: 'ok' | 'warning' | 'critical'; flag: string; booked_kg: number; pvt_kg: number; true_kg: number; messages: string[] }
interface FSat { id: string; regime: string; load_kg: number; dry_kg: number; isp_s: number; reserve_dv: number; summary: Summary; series: number[][] }
const DATA = raw as unknown as { days: number; note: string; satellites: FSat[] }
const TONE = { ok: 'text-ok border-ok/70 bg-ok/15', warning: 'text-warn border-warn/70 bg-warn/15', critical: 'text-bad border-bad/70 bg-bad/15' }
const yrs = (y: number | null) => (y == null ? 'no use' : y > 40 ? '>40 y' : `${y.toFixed(1)} y`)

function Chart({ s }: { s: FSat }) {
  const W = 960, H = 280, L = 56, R = 12, T = 12, B = 30, n = DATA.days
  const ser = s.series
  const lo = Math.min(...ser.map((r) => Math.min(r[1], r[2], r[3], r[4] - 2 * r[5]))) * 0.995
  const hi = Math.max(...ser.map((r) => Math.max(r[1], r[2], r[3], r[4] + 2 * r[5]))) * 1.005
  const x = (d: number) => L + ((W - L - R) * d) / (n - 1), y = (v: number) => T + ((H - T - B) * (hi - v)) / (hi - lo || 1)
  const line = (i: number) => ser.map((r, k) => `${k ? 'L' : 'M'}${x(r[0]).toFixed(1)},${y(r[i]).toFixed(1)}`).join('')
  const band = ser.map((r) => `${x(r[0]).toFixed(1)},${y(r[4] + 2 * r[5]).toFixed(1)}`).join(' ') + ' ' + [...ser].reverse().map((r) => `${x(r[0]).toFixed(1)},${y(r[4] - 2 * r[5]).toFixed(1)}`).join(' ')
  const ticks = [0, 1, 2, 3, 4].map((i) => lo + ((hi - lo) * i) / 4)
  const flagStart = ser.find((r) => r[7] === 1)?.[0]
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`Propellant history for ${s.id}`}>
      {ticks.map((t) => <g key={t}><line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="currentColor" strokeOpacity={0.12} /><text x={L - 6} y={y(t) + 3} fontSize={10} textAnchor="end" fill="currentColor" opacity={0.6}>{t.toFixed(0)} kg</text></g>)}
      {[0, 90, 180, 270, 364].map((d) => <text key={d} x={x(d)} y={H - 10} fontSize={10} textAnchor="middle" fill="currentColor" opacity={0.6}>day {d}</text>)}
      {flagStart != null && <rect x={x(flagStart)} y={T} width={x(n - 1) - x(flagStart)} height={H - T - B} fill="#ff7b7b" opacity={0.08} />}
      <polygon points={band} fill="#7aa2ff" opacity={0.18} />
      <path d={line(2)} fill="none" stroke="#fcd34d" strokeWidth={1.4} />
      {ser.filter((_, k) => k % 3 === 0).map((r) => <circle key={r[0]} cx={x(r[0])} cy={y(r[3])} r={1.4} fill="#c084fc" opacity={0.7} />)}
      <path d={line(4)} fill="none" stroke="#7aa2ff" strokeWidth={2} />
      <path d={line(1)} fill="none" stroke="#4ade80" strokeWidth={1.2} strokeDasharray="4 3" />
      {ser.filter((r) => r[6] > 0).map((r) => <line key={`b${r[0]}`} x1={x(r[0])} x2={x(r[0])} y1={H - B} y2={H - B - Math.min(14, 3 + r[6] * 0.25)} stroke="#fb923c" strokeOpacity={0.8} />)}
    </svg>
  )
}

export default function Fuel() {
  const d = useScoped()
  const [sp, setSp] = useSearchParams()
  const visible = useMemo(() => DATA.satellites.filter((s) => d.satellites.some((x) => x.id === s.id)), [d.satellites])
  const sat = visible.find((s) => s.id === sp.get('sat')) ?? visible.find((s) => s.summary.status !== 'ok') ?? visible[0]
  if (!sat) return <><PageHeader title="Fuel" /><p className="text-mute">No satellites in scope.</p></>
  const name = (id: string) => d.satellites.find((s) => s.id === id)?.name ?? id
  const m = sat.summary
  const alerts = visible.filter((s) => s.summary.messages.length)

  return (
    <>
      <PageHeader title="Fuel Measurement" sub="Propellant gauged two independent ways, fused, with its uncertainty"
        actions={<DemoTag text="Simulated year - assumed tanks, burns and faults" />} />
      {alerts.length > 0 && (
        <Card className="mb-4"><CardHeader title="Fuel alerts" />
          <ul className="p-4 space-y-1.5 text-sm">{alerts.map((a) => <li key={a.id} className="flex gap-2 items-start cursor-pointer" onClick={() => setSp({ sat: a.id })}><Badge tone={TONE[a.summary.status]}>{a.summary.status}</Badge><span><b>{name(a.id)}</b> ({a.id}): {a.summary.messages.join('. ')}</span></li>)}</ul>
        </Card>
      )}
      <Card className="mb-4 overflow-x-auto">
        <CardHeader title="Fleet propellant" sub="Estimate = fused gauge ±1σ. Remaining Δv from the rocket equation. Years = operational Δv above the disposal reserve ÷ current run rate" />
        <table className="w-full text-sm">
          <thead className="text-xs text-mute text-left"><tr>{['Satellite', 'Propellant', 'of load', 'Δv remaining', 'Run rate', 'To reserve', 'Gauges agree', 'Status'].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
          <tbody>{visible.map((s) => (
            <tr key={s.id} className={cn('border-t border-line cursor-pointer hover:bg-panel2', s.id === sat.id && 'bg-accent/10')} onClick={() => setSp({ sat: s.id })}>
              <td className="px-3 py-2">{name(s.id)} <span className="text-mute">({s.id}, {s.regime})</span></td>
              <td className="px-3 py-2 font-mono">{s.summary.fused_kg.toFixed(1)} ± {s.summary.sigma_kg.toFixed(2)} kg</td>
              <td className="px-3 py-2"><div className="w-24 h-2 rounded bg-line overflow-hidden"><div className={cn('h-full', s.summary.status === 'critical' ? 'bg-bad' : s.summary.status === 'warning' ? 'bg-warn' : 'bg-ok')} style={{ width: `${Math.max(2, s.summary.pct_load)}%` }} /></div><span className="text-xs text-mute">{s.summary.pct_load.toFixed(0)}%</span></td>
              <td className="px-3 py-2 font-mono">{s.summary.dv_mps.toFixed(0)} m/s</td>
              <td className="px-3 py-2 font-mono">{s.summary.rate_mps_yr.toFixed(1)} m/s/y</td>
              <td className="px-3 py-2">{yrs(s.summary.years_to_reserve)}</td>
              <td className={cn('px-3 py-2', s.summary.flag !== 'ok' && 'text-bad')}>{s.summary.flag === 'ok' ? 'yes' : 'NO'}</td>
              <td className="px-3 py-2"><Badge tone={TONE[s.summary.status]}>{s.summary.status}</Badge></td>
            </tr>))}</tbody>
        </table>
      </Card>

      <div className="grid xl:grid-cols-3 gap-4">
        <Card className="xl:col-span-2">
          <CardHeader title={`${name(sat.id)} - propellant over one year`} sub={`${sat.regime}, ${sat.load_kg} kg load, ${sat.dry_kg} kg dry, Isp ${sat.isp_s} s, disposal reserve ${sat.reserve_dv} m/s`} />
          <div className="p-3"><Chart s={sat} />
            <div className="flex flex-wrap gap-3 text-xs mt-1">
              <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-[#7aa2ff]" />fused ±2σ</span>
              <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-[#fcd34d]" />book-keeping only</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#c084fc]" />PVT readings</span>
              <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-ok" style={{ borderTop: '1px dashed' }} />simulation truth (not available in flight)</span>
              <span className="flex items-center gap-1"><span className="w-0.5 h-3 bg-orange-400" />burn</span>
            </div>
          </div>
        </Card>
        <div className="space-y-4">
          <Card className="p-4 text-sm space-y-1">
            <h4 className="font-semibold">{sat.id} now</h4>
            <p>Propellant <b className="font-mono">{m.fused_kg.toFixed(1)} ± {m.sigma_kg.toFixed(2)} kg</b></p>
            <p>Δv remaining <b className="font-mono">{m.dv_mps.toFixed(0)} m/s</b> <span className="text-xs text-mute">(2σ range {m.dv_lo.toFixed(0)}–{m.dv_hi.toFixed(0)})</span></p>
            <p className="text-xs text-mute">Book-keeping alone: {m.booked_kg.toFixed(1)} kg · PVT alone: {m.pvt_kg.toFixed(1)} kg · simulation truth: {m.true_kg.toFixed(1)} kg</p>
            {m.messages.map((t) => <p key={t} className="text-xs text-bad">{t}</p>)}
            {m.flag !== 'ok' && <p className="text-xs text-warn">While the gauges disagree the filter stops learning from PVT, so the fused value may be stale. Δv and years above use the lowest of the three figures until the cause is resolved.</p>}
          </Card>
          <Card className="p-4 text-xs text-mute space-y-1.5">
            <h4 className="text-sm font-semibold text-text">How the gauge works</h4>
            <p><b>Book-keeping:</b> every burn's propellant use is added up from thruster on-time. Smooth, but its error grows because the real Isp differs from nominal.</p>
            <p><b>PVT:</b> helium is a fixed amount, so tank pressure and temperature give the empty (ullage) volume, and propellant is what remains. Accurate when full, weaker as the tank empties.</p>
            <p><b>Fusion:</b> a filter uses book-keeping to predict and PVT to correct, and learns the Isp error. If they keep disagreeing it raises a flag (leak or pressure sensor fault) and stops learning from PVT.</p>
          </Card>
        </div>
      </div>
      <p className="text-xs text-mute mt-3">{DATA.note}</p>
    </>
  )
}
