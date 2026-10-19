import { useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { useScoped } from '@/store/hooks'
import { Card, CardHeader, PageHeader, StatusBadge, HealthBar, Drawer, DemoTag, Empty, RiskBadge, Badge } from '@/components/ui'
import { OrbitView } from '@/components/OrbitView'
import { cn, healthColor } from '@/lib/util'
import { agentName } from '@/store/useStore'

export default function Fleet() {
  const d = useScoped()
  const [sp, setSp] = useSearchParams()
  const [q, setQ] = useState('')
  const [kind, setKind] = useState(sp.get('kind') ?? 'all')
  const [status, setStatus] = useState('all')
  const sel = d.satellites.find((s) => s.id === sp.get('sat'))
  const rows = d.satellites.filter((s) => (kind === 'all' || s.kind === kind) && (status === 'all' || s.status === status) &&
    `${s.id} ${s.name} ${s.operator} ${s.role}`.toLowerCase().includes(q.toLowerCase()))

  return (
    <>
      <PageHeader title="Satellite Fleet" sub="Company servicers and customer satellites" actions={<DemoTag />} />
      <div className="flex flex-wrap gap-2 mb-4">
        <div className="relative"><Search size={14} className="absolute left-2.5 top-2.5 text-mute" /><input aria-label="Search satellites" className="input pl-8 w-64" placeholder="Search name, ID, operator…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <select aria-label="Kind" className="input" value={kind} onChange={(e) => setKind(e.target.value)}><option value="all">All types</option><option value="customer">Customer</option><option value="servicer">Servicer</option></select>
        <select aria-label="Status" className="input" value={status} onChange={(e) => setStatus(e.target.value)}>{['all', 'Nominal', 'Attention', 'Servicing', 'Standby', 'Hold'].map((s) => <option key={s}>{s}</option>)}</select>
      </div>
      <div className="grid xl:grid-cols-3 gap-4">
        <Card className="xl:col-span-2 overflow-x-auto">
          <table className="w-full">
            <thead><tr><th className="th">Satellite</th><th className="th">Operator</th><th className="th">Role</th><th className="th">Orbit</th><th className="th">Status</th><th className="th w-32">Min health</th></tr></thead>
            <tbody>
              {rows.map((s) => {
                const w = Math.min(...s.components.map((c) => c.health))
                return (
                  <tr key={s.id} tabIndex={0} role="button" className={cn('cursor-pointer hover:bg-panel2', sel?.id === s.id && 'bg-accent/5')} onClick={() => setSp({ sat: s.id })} onKeyDown={(e) => e.key === 'Enter' && setSp({ sat: s.id })}>
                    <td className="td"><div className="font-medium">{s.name}</div><div className="text-xs text-mute font-mono">{s.id}</div></td>
                    <td className="td">{s.operator}</td><td className="td text-mute">{s.role}</td><td className="td">{s.orbit.regime} {s.orbit.altKm.toLocaleString()} km</td>
                    <td className="td"><StatusBadge s={s.status} /></td>
                    <td className="td"><span className={cn('text-xs font-mono', healthColor(w))}>{w}%</span><HealthBar v={w} /></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {rows.length === 0 && <Empty text="No satellites match your filters." />}
        </Card>
        <Card>
          <CardHeader title="Orbit schematic" sub="Click a marker to inspect" />
          <div className="grid place-items-center p-2"><OrbitView sats={rows} selected={sel?.id} onSelect={(id) => setSp({ sat: id })} size={300} /></div>
        </Card>
      </div>

      <Drawer open={!!sel} onClose={() => setSp({})} title={sel ? `${sel.name} · ${sel.id}` : ''} width="max-w-2xl">
        {sel && <SatProfile id={sel.id} />}
      </Drawer>
    </>
  )
}

function SatProfile({ id }: { id: string }) {
  const d = useScoped()
  const s = d.satellites.find((x) => x.id === id)!
  const pol = d.policies.find((p) => p.satId === id)
  const cases = d.cases.filter((c) => c.satId === id)
  return (
    <div className="space-y-5 text-sm">
      <div className="flex gap-2 flex-wrap"><StatusBadge s={s.status} /><Badge>{s.kind}</Badge><Badge>{s.operator}</Badge></div>
      <p className="text-mute">{s.role}. {s.condition}.</p>
      <section>
        <h4 className="font-semibold mb-2">Orbital parameters <DemoTag /></h4>
        <div className="grid grid-cols-3 gap-2 text-xs">
          {[['Regime', s.orbit.regime], ['Altitude', `${s.orbit.altKm.toLocaleString()} km`], ['Inclination', `${s.orbit.incDeg}°`], ['RAAN', `${s.orbit.raanDeg}°`], ['Eccentricity', s.orbit.ecc], ['Period', `${s.orbit.periodMin} min`]].map(([k, v]) => (
            <div key={String(k)} className="card p-2"><div className="text-mute">{k}</div><div className="font-mono">{v}</div></div>
          ))}
        </div>
        <div className="grid place-items-center"><OrbitView sats={[s]} selected={s.id} size={200} /></div>
      </section>
      <section>
        <h4 className="font-semibold mb-2">Subsystem health</h4>
        <div className="grid grid-cols-2 gap-2">
          {s.components.map((c) => (
            <Link key={c.id} to={`/monitoring?sat=${s.id}&comp=${encodeURIComponent(c.id)}`} className="card p-2 hover:border-accent/50">
              <div className="flex justify-between text-xs"><span>{c.name}</span><span className={cn('font-mono', healthColor(c.health))}>{c.health}%</span></div><HealthBar v={c.health} />
            </Link>
          ))}
        </div>
      </section>
      <section><h4 className="font-semibold mb-1">Connected AI agent</h4><p className="text-mute">{agentName(s.agentId)}</p></section>
      <section>
        <h4 className="font-semibold mb-1">Active service policy</h4>
        {pol ? <p className="text-mute">{pol.id} v{pol.version} - <Link className="text-accent" to={`/policies?p=${pol.id}`}>view policy</Link></p> : <p className="text-mute">Company-owned asset: no customer policy.</p>}
      </section>
      <section>
        <h4 className="font-semibold mb-1">Maintenance history</h4>
        <ul className="space-y-1 text-mute">
          {cases.map((c) => <li key={c.id}><Link className="text-accent" to="/maintenance">{c.id}</Link> - {c.problem}</li>)}
          {s.history.map((h, i) => <li key={i}>{h.date} - {h.text}</li>)}
        </ul>
      </section>
    </div>
  )
}
