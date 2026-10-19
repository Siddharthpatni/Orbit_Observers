import { useEffect, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ArrowRight, Eye, Stethoscope, ShieldCheck, UserCheck, Wrench, BadgeCheck } from 'lucide-react'
import { useScoped } from '@/store/hooks'
import { agentName } from '@/store/useStore'
import { Card, DemoTag, StatusBadge, Empty } from '@/components/ui'
import { OrbitView } from '@/components/OrbitView'
import { MISSION_STAGES } from '@/lib/types'
import { ago, cn, healthColor, healthHex } from '@/lib/util'
import { api } from '@/services/api'

function Clock() {
  const [t, setT] = useState(() => new Date())
  useEffect(() => { const i = setInterval(() => setT(new Date()), 1000); return () => clearInterval(i) }, [])
  return <span className="font-mono tabular-nums">{t.toISOString().slice(11, 19)} UTC</span>
}

function Gauge({ value }: { value: number }) {
  const r = 52, c = 2 * Math.PI * r, arc = c * 0.75
  return (
    <svg viewBox="0 0 140 140" className="w-40 h-40" role="img" aria-label={`Fleet health ${value} percent`}>
      <defs><linearGradient id="gg" x1="0" x2="1"><stop offset="0" stopColor="#0d52ad" /><stop offset="1" stopColor="#00c2ff" /></linearGradient></defs>
      <g transform="rotate(135 70 70)">
        <circle cx="70" cy="70" r={r} fill="none" stroke="#2c3544" strokeWidth="10" strokeLinecap="round" strokeDasharray={`${arc} ${c}`} />
        <circle cx="70" cy="70" r={r} fill="none" stroke="url(#gg)" strokeWidth="10" strokeLinecap="round" strokeDasharray={`${(arc * value) / 100} ${c}`} style={{ transition: 'stroke-dasharray .8s ease' }} />
      </g>
      <text x="70" y="70" textAnchor="middle" className="fill-white" fontSize="30" fontWeight="700">{value}</text>
      <text x="70" y="88" textAnchor="middle" fill="#cfd8e3" fontSize="9">FLEET HEALTH</text>
    </svg>
  )
}

const Section = ({ title, link, to, children, className }: { title: string; link?: string; to?: string; children: ReactNode; className?: string }) => (
  <Card className={cn('flex flex-col', className)}>
    <div className="flex items-center justify-between px-5 pt-4 pb-2">
      <h3 className="text-xs uppercase tracking-widest text-mute font-semibold">{title}</h3>
      {to && <Link to={to} className="text-xs text-accent hover:underline inline-flex items-center gap-1">{link} <ArrowRight size={12} /></Link>}
    </div>
    <div className="flex-1">{children}</div>
  </Card>
)

export default function Dashboard() {
  const d = useScoped()
  const nav = useNavigate()
  const cust = d.satellites.filter((s) => s.kind === 'customer')
  const comps = cust.flatMap((s) => s.components)
  const score = comps.length ? Math.round(comps.reduce((a, c) => a + c.health, 0) / comps.length) : 0
  const attn = cust.filter((s) => s.components.some((c) => c.health < 80)).length
  const crit = comps.filter((c) => c.health < 60).length
  const pending = d.approvals.filter((a) => a.status === 'pending')
  const liveMissions = d.missions.filter((m) => m.stage < 11)
  const doneMissions = d.missions.filter((m) => m.stage >= 11).length
  const stageN = (...s: number[]) => d.cases.filter((c) => s.includes(c.stage)).length
  const open = comps.filter((c) => c.health < 75 && !d.cases.some((k) => k.componentId === c.id && k.stage < 7)).length

  const pipeline = [
    { label: 'Detect', n: open + stageN(0), icon: Eye, to: '/monitoring', sub: 'anomalies' },
    { label: 'Diagnose', n: stageN(1, 2), icon: Stethoscope, to: '/maintenance', sub: 'cases' },
    { label: 'Approve', n: stageN(3), icon: UserCheck, to: '/approvals', sub: 'awaiting human' },
    { label: 'Service', n: stageN(4, 5), icon: Wrench, to: '/missions', sub: 'in mission' },
    { label: 'Verify', n: stageN(6), icon: ShieldCheck, to: '/missions', sub: 'checking' },
    { label: 'Complete', n: stageN(7), icon: BadgeCheck, to: '/audit', sub: 'closed' },
  ]

  const bySub: Record<string, number[]> = {}
  cust.forEach((s) => s.components.forEach((c) => (bySub[c.subsystem] ??= []).push(c.health)))
  const chart = Object.entries(bySub).map(([k, v]) => ({ name: k, health: Math.round(v.reduce((a, b) => a + b, 0) / v.length) })).sort((a, b) => a.health - b.health)

  const decided = d.approvals.filter((a) => a.status === 'approved' || a.status === 'rejected').length
  const scoreAvg = d.tasks.length ? Math.round((d.tasks.reduce((a, t) => a + t.checkpoints.filter((c) => c.done).length / t.checkpoints.length, 0) / d.tasks.length) * 100) : 0
  const record = [
    { k: 'Autonomous tasks closed', v: d.tasks.filter((t) => t.status === 'done').length },
    { k: 'Task checkpoint score', v: `${scoreAvg}%` },
    { k: 'Missions completed', v: doneMissions },
    { k: 'Policy evaluations', v: d.evals.length },
    { k: 'Human decisions', v: decided },
    { k: 'Audit records', v: d.audit.length },
  ]

  return (
    <div className="space-y-4 max-w-[1500px]">
      {/* Command header */}
      <div className="relative overflow-hidden rounded-2xl border border-line bg-gradient-to-br from-brand/25 via-black to-black p-6">
        <div className="absolute -right-24 -top-24 w-80 h-80 rounded-full bg-accent/10 blur-3xl pointer-events-none" aria-hidden />
        <div className="relative flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-widest text-mute mb-1">Orbit Observers Mission Control</div>
            <h1 className="text-3xl font-bold tracking-tight">In-orbit servicing, <span className="grad-text">run by autonomous agents.</span></h1>
            <p className="text-sm text-mute mt-2 max-w-2xl">Agents detect faults, diagnose, check policy and plan the repair on their own. Humans approve every critical step.</p>
          </div>
          <div className="text-right space-y-1.5">
            <div className="text-lg"><Clock /></div>
            <button className="btn" onClick={() => api.setAutonomy(!d.autonomy.enabled)} aria-pressed={d.autonomy.enabled}>
              <span className={cn('w-2 h-2 rounded-full', d.autonomy.enabled ? 'bg-ok' : 'bg-warn')} />Agents {d.autonomy.enabled ? 'autonomous' : 'paused'}
            </button>
            <div><DemoTag /></div>
          </div>
        </div>

        {/* Live pipeline */}
        <ol className="relative mt-6 grid grid-cols-2 md:grid-cols-6 gap-2" aria-label="Servicing pipeline">
          {pipeline.map((p, i) => (
            <li key={p.label} className="relative">
              <button onClick={() => nav(p.to)} className={cn('w-full text-left rounded-xl border px-4 py-3 transition hover:border-accent', p.n > 0 ? 'border-accent/60 bg-accent/10' : 'border-line bg-black/40')}>
                <div className="flex items-center justify-between text-mute"><p.icon size={16} className={p.n > 0 ? 'text-accent' : ''} /><span className="text-[11px]">{i + 1}</span></div>
                <div className="text-2xl font-bold mt-1 tabular-nums">{p.n}</div>
                <div className="text-xs font-semibold">{p.label}</div>
                <div className="text-[11px] text-mute">{p.sub}</div>
              </button>
            </li>
          ))}
        </ol>
      </div>

      {/* KPI ribbon */}
      <Card className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 divide-x divide-y xl:divide-y-0 divide-line overflow-hidden">
        {[
          { l: 'Monitored sats', v: cust.length, to: '/fleet' },
          { l: 'Servicers', v: d.satellites.filter((s) => s.kind === 'servicer').length, to: '/fleet?kind=servicer' },
          { l: 'Need attention', v: attn, tone: attn ? 'text-warn' : '', to: '/monitoring' },
          { l: 'Critical alerts', v: crit, tone: crit ? 'text-bad' : '', to: '/monitoring' },
          { l: 'Active missions', v: liveMissions.length, to: '/missions' },
          { l: 'Open recommendations', v: d.cases.filter((c) => c.stage < 7).length, to: '/maintenance' },
          { l: 'Pending approvals', v: pending.length, tone: pending.length ? 'text-warn' : '', to: '/approvals' },
          { l: 'Live comm sessions', v: d.sessions.filter((s) => s.status === 'Active').length, to: '/comms' },
        ].map((k) => (
          <button key={k.l} onClick={() => nav(k.to)} className="text-left px-4 py-3 hover:bg-panel2 transition">
            <div className={cn('text-2xl font-bold tabular-nums', k.tone)}>{k.v}</div>
            <div className="text-[11px] uppercase tracking-wider text-mute">{k.l}</div>
          </button>
        ))}
      </Card>

      <div className="grid xl:grid-cols-12 gap-4">
        {/* Orbit + health */}
        <Section title="Constellation" link="Fleet" to="/fleet" className="xl:col-span-5">
          <div className="grid place-items-center pb-2"><OrbitView sats={d.satellites} onSelect={(id) => nav(`/fleet?sat=${id}`)} size={340} /></div>
          <div className="flex justify-center gap-4 pb-4 text-[11px] text-mute">
            <span><span className="inline-block w-2 h-2 rounded-full bg-ok mr-1" />healthy</span>
            <span><span className="inline-block w-2 h-2 rounded-full bg-warn mr-1" />degraded</span>
            <span><span className="inline-block w-2 h-2 rounded-full bg-bad mr-1" />critical</span>
            <span><span className="inline-block w-2 h-2 rotate-45 bg-accent mr-1" />servicer</span>
          </div>
        </Section>

        <Section title="Fleet health" link="Monitoring" to="/monitoring" className="xl:col-span-3">
          <div className="grid place-items-center"><Gauge value={score} /></div>
          <div className="h-52 px-2 pb-3">
            <ResponsiveContainer>
              <BarChart data={chart} layout="vertical" margin={{ left: 10, right: 16 }} onClick={() => nav('/monitoring')}>
                <XAxis type="number" domain={[0, 100]} hide />
                <YAxis type="category" dataKey="name" stroke="#cfd8e3" fontSize={11} width={84} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: '#171a21' }} contentStyle={{ background: '#0e1014', border: '1px solid #2c3544', borderRadius: 12 }} />
                <Bar dataKey="health" radius={6} barSize={10} cursor="pointer" background={{ fill: '#171a21', radius: 6 } as never}>{chart.map((c) => <Cell key={c.name} fill={healthHex(c.health)} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Section>

        <Section title="Agents, live" link="Operations" to="/agents" className="xl:col-span-4">
          <ul>
            {d.agents.map((a) => {
              const last = d.agentEvents.find((e) => e.agentId === a.id)
              return (
                <li key={a.id} className="px-5 py-2.5 border-t border-line first:border-0">
                  <div className="flex items-center justify-between gap-2"><span className="text-sm font-medium truncate">{a.name}</span><StatusBadge s={a.state} /></div>
                  <div className="text-xs text-mute truncate">{last ? `${ago(last.ts)}: ${last.text}` : 'No activity yet'}</div>
                </li>
              )
            })}
          </ul>
        </Section>
      </div>

      <div className="grid xl:grid-cols-12 gap-4">
        <Section title="Mission tracker" link="All missions" to="/missions" className="xl:col-span-5">
          {liveMissions.length === 0 ? <Empty text="No active missions." /> : (
            <ul>
              {liveMissions.slice(0, 5).map((m) => {
                const gate = m.gates[m.stage]
                const blocked = !!gate && d.approvals.find((a) => a.id === gate)?.status !== 'approved'
                return (
                  <li key={m.id}>
                    <Link to={`/missions?m=${m.id}`} className="block px-5 py-3 border-t border-line first:border-0 hover:bg-panel2">
                      <div className="flex justify-between gap-2 text-sm"><span className="font-medium truncate">{m.title}</span><span className="text-xs text-mute shrink-0">{m.id}</span></div>
                      <div className="flex gap-0.5 my-2" aria-label={`Phase ${m.stage + 1} of 11`}>
                        {MISSION_STAGES.map((_, i) => <span key={i} className={cn('h-1.5 flex-1 rounded-full', i < m.stage ? 'bg-accent' : i === m.stage ? 'bg-accent/50' : 'bg-line')} />)}
                      </div>
                      <div className="flex justify-between text-xs"><span>{MISSION_STAGES[m.stage]}</span>{blocked ? <span className="text-warn">Waiting for {gate}</span> : <span className="text-mute">Phase {m.stage + 1}/11</span>}</div>
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
        </Section>

        <Section title="Needs a human" link="Approvals" to="/approvals" className="xl:col-span-3">
          {pending.length === 0 ? <Empty text="Nothing waiting. Agents are working." /> : (
            <ul>{pending.slice(0, 5).map((a) => (
              <li key={a.id}><Link to="/approvals" className="block px-5 py-3 border-t border-line first:border-0 hover:bg-panel2">
                <div className="text-[11px] text-mute font-mono">{a.id} - {a.risk} risk</div><div className="text-sm">{a.operation}</div><div className="text-xs text-mute">{ago(a.createdAt)}</div>
              </Link></li>
            ))}</ul>
          )}
        </Section>

        <Section title="Live activity" link="Audit" to="/audit" className="xl:col-span-4">
          <ul className="max-h-72 overflow-y-auto">
            {d.audit.slice(0, 9).map((a) => (
              <li key={a.id} className="px-5 py-2 border-t border-line first:border-0 text-sm">
                <div className="flex justify-between text-[11px] text-mute"><span className="uppercase tracking-wider">{a.category}</span><span>{ago(a.ts)}</span></div>
                <div className="truncate">{a.summary}</div>
              </li>
            ))}
          </ul>
        </Section>
      </div>

      {/* Track record */}
      <Card className="grid grid-cols-2 md:grid-cols-6 divide-x divide-line overflow-hidden">
        {record.map((r) => (
          <div key={r.k} className="px-4 py-4"><div className="text-2xl font-bold grad-text w-fit tabular-nums">{r.v}</div><div className="text-[11px] uppercase tracking-wider text-mute">{r.k}</div></div>
        ))}
      </Card>
      <p className="text-[11px] text-mute pb-2">All telemetry, predictions and outcomes on this screen are simulated demo data. <span className={healthColor(score)}>Fleet score is the mean component health.</span></p>
    </div>
  )
}
