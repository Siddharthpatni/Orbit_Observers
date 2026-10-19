import { useNavigate, useSearchParams } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, Wrench } from 'lucide-react'
import { useScoped } from '@/store/hooks'
import { Card, CardHeader, PageHeader, HealthBar, RiskBadge, DemoTag, Empty } from '@/components/ui'
import { api } from '@/services/api'
import { canOperate } from '@/lib/access'
import { cn, healthColor, healthHex } from '@/lib/util'

export default function Monitoring() {
  const d = useScoped()
  const nav = useNavigate()
  const [sp, setSp] = useSearchParams()
  const cust = d.satellites.filter((s) => s.kind === 'customer')
  const sat = d.satellites.find((s) => s.id === sp.get('sat')) ?? cust.find((s) => s.components.some((c) => c.health < 80)) ?? cust[0] ?? d.satellites[0]
  if (!sat) return <Empty text="No satellites available." />
  const comp = sat.components.find((c) => c.id === sp.get('comp')) ?? [...sat.components].sort((a, b) => a.health - b.health)[0]
  const data = comp.series.map((v, i) => ({ t: `T-${comp.series.length - 1 - i}`, v }))
  const last = comp.series[comp.series.length - 1]
  const anomaly = last > comp.warnAt * 0.55 || comp.health < 80
  const openCase = d.cases.find((c) => c.componentId === comp.id && c.stage < 7)
  const set = (o: Record<string, string>) => setSp({ sat: sat.id, ...o })

  return (
    <>
      <PageHeader title="AI Health Monitoring" sub="Continuous component analysis by the Health Monitoring Agent" actions={<><DemoTag text="Predictions are simulated" /><select aria-label="Satellite" className="input" value={sat.id} onChange={(e) => setSp({ sat: e.target.value })}>{d.satellites.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.id})</option>)}</select></>} />
      <div className="grid xl:grid-cols-3 gap-4">
        <Card className="xl:col-span-1">
          <CardHeader title="Components" sub={`${sat.name} · ${sat.condition}`} />
          <ul>
            {sat.components.map((c) => (
              <li key={c.id}>
                <button className={cn('w-full text-left px-4 py-2.5 border-b border-line hover:bg-panel2', c.id === comp.id && 'bg-accent/5')} onClick={() => set({ comp: c.id })}>
                  <div className="flex justify-between text-sm"><span>{c.name}</span><span className={cn('font-mono', healthColor(c.health))}>{c.health}%</span></div>
                  <HealthBar v={c.health} />
                  {c.issue && <div className="text-xs text-warn mt-1 flex items-center gap-1"><AlertTriangle size={11} />{c.issue}</div>}
                </button>
              </li>
            ))}
          </ul>
        </Card>
        <div className="xl:col-span-2 space-y-4">
          <Card>
            <CardHeader title={comp.name} sub={`${comp.subsystem} · ${comp.metric} (${comp.unit})`} right={<RiskBadge risk={comp.risk} />} />
            <p className="px-4 pt-3 text-xs text-mute">Summary: {comp.metric} moved from {comp.series[0]} to {last} {comp.unit} over {comp.series.length} samples; warning threshold {comp.warnAt} {comp.unit} ({last >= comp.warnAt ? 'exceeded' : `${Math.round((last / comp.warnAt) * 100)}% of threshold`}). Simulated data.</p>
            <div className="h-64 p-3" role="img" aria-label={`Line chart of ${comp.metric} for ${comp.name} with dashed warning threshold at ${comp.warnAt} ${comp.unit}`}>
              <ResponsiveContainer>
                <LineChart data={data}>
                  <CartesianGrid stroke="#2c3544" vertical={false} />
                  <XAxis dataKey="t" stroke="#cfd8e3" fontSize={10} interval={7} />
                  <YAxis stroke="#cfd8e3" fontSize={11} domain={[0, Math.ceil(comp.warnAt * 1.15)]} />
                  <Tooltip contentStyle={{ background: '#0e1014', border: '1px solid #2c3544' }} />
                  <ReferenceLine y={comp.warnAt} stroke="#fcd34d" strokeDasharray="4 4" label={{ value: 'Warning threshold', fill: '#fcd34d', fontSize: 10, position: 'insideTopRight' }} />
                  <Line type="monotone" dataKey="v" stroke={healthHex(comp.health)} dot={false} strokeWidth={2} name={comp.unit} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <div className="grid md:grid-cols-4 gap-3">
            <Card className="p-3"><div className="text-xs text-mute uppercase">Health</div><div className={cn('text-2xl font-semibold', healthColor(comp.health))}>{comp.health}%</div></Card>
            <Card className="p-3"><div className="text-xs text-mute uppercase">Latest</div><div className="text-2xl font-semibold font-mono">{last}<span className="text-xs text-mute"> {comp.unit}</span></div></Card>
            <Card className="p-3"><div className="text-xs text-mute uppercase">Anomaly</div><div className={cn('text-lg font-semibold', anomaly ? 'text-warn' : 'text-ok')}>{anomaly ? 'Detected' : 'None'}</div></Card>
            <Card className="p-3"><div className="text-xs text-mute uppercase">Est. RUL</div><div className="text-lg font-semibold">{comp.rulDays ? `~${comp.rulDays} d` : 'n/a'}</div></Card>
          </div>
          <Card className="p-4 text-sm space-y-2">
            <div className="flex items-center justify-between"><h4 className="font-semibold">AI assessment</h4><DemoTag text="Illustrative - not a validated forecast" /></div>
            <p><span className="text-mute">Detected issue:</span> {comp.issue ?? 'No abnormal trend'}</p>
            <p><span className="text-mute">Predicted failure risk:</span> {comp.risk}</p>
            <p><span className="text-mute">Recommendation:</span> {comp.recommendation ?? 'Continue routine monitoring'}</p>
            <div className="flex gap-2 pt-1">
              {openCase
                ? <button className="btn btn-primary" onClick={() => nav('/maintenance')}>View {openCase.id}</button>
                : comp.health < 85 && canOperate(d.role) && <button className="btn btn-primary" onClick={() => { const id = api.createMaintRequest(sat.id, comp.id); nav(`/maintenance?c=${id}`) }}><Wrench size={14} />Create maintenance request</button>}
            </div>
          </Card>
        </div>
      </div>
    </>
  )
}
