import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Pause, Play } from 'lucide-react'
import { api } from '@/services/api'
import { useScoped } from '@/store/hooks'
import { Card, CardHeader, PageHeader, StatusBadge, Drawer, Badge, DemoTag, Empty } from '@/components/ui'
import { agentName } from '@/store/useStore'
import type { AgentEvent, AgentTask } from '@/lib/types'
import { cn, fmtDT, ago } from '@/lib/util'

const kindTone: Record<string, string> = { observation: 'text-info', recommendation: 'text-accent', 'policy-check': 'text-ok', escalation: 'text-warn', task: 'text-mute', result: 'text-ok' }

export default function Agents() {
  const d = useScoped()
  const [sel, setSel] = useState<string>('all')
  const [ev, setEv] = useState<AgentEvent | null>(null)
  const [task, setTask] = useState<string | null>(null)
  const tk = d.tasks.find((t) => t.id === task)
  const events = d.agentEvents.filter((e) => sel === 'all' || e.agentId === sel)
  const agent = d.agents.find((a) => a.id === sel)

  return (
    <>
      <PageHeader title="AI Agent Operations Center" sub="What each agent observed, recommended, and why" actions={<><DemoTag text="Simulated agents" /><button className={d.autonomy.enabled ? 'btn btn-primary' : 'btn'} onClick={() => api.setAutonomy(!d.autonomy.enabled)}>{d.autonomy.enabled ? <><Pause size={14} />Autonomous: pause</> : <><Play size={14} />Paused: resume</>}</button></>} />
      <TaskBoard tasks={d.tasks} onOpen={setTask} />
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3 mb-5">
        {d.agents.map((a) => {
          const esc = d.agentEvents.filter((e) => e.agentId === a.id && e.needsApproval).length
          return (
            <Card key={a.id} onClick={() => setSel(sel === a.id ? 'all' : a.id)} className={cn('p-4', sel === a.id && 'border-accent')}>
              <div className="flex justify-between items-start"><h3 className="font-semibold text-sm">{a.name}</h3><StatusBadge s={a.state} /></div>
              <p className="text-xs text-mute mt-1">{a.role}</p>
              <div className="flex gap-2 mt-3 text-xs text-mute"><Badge>{a.satIds.length} sats</Badge><Badge>{d.agentEvents.filter((e) => e.agentId === a.id).length} events</Badge>{esc > 0 && <Badge tone="text-warn border-warn/70">{esc} escalations</Badge>}</div>
            </Card>
          )
        })}
      </div>
      <div className="grid xl:grid-cols-3 gap-4">
        <Card className="xl:col-span-2">
          <CardHeader title={agent ? `${agent.name} - activity` : 'Agent activity timeline'} sub="Click an entry for task detail" />
          {events.length === 0 && <Empty text="No activity yet." />}
          <ol className="p-4 space-y-0">
            {events.map((e) => (
              <li key={e.id} className="flex gap-3">
                <div className="flex flex-col items-center"><span className={cn('w-2 h-2 rounded-full mt-2 bg-current', kindTone[e.kind])} /><span className="flex-1 w-px bg-line" /></div>
                <button className="text-left pb-4 flex-1 hover:bg-panel2 rounded px-2 -mx-2" onClick={() => setEv(e)}>
                  <div className="text-xs text-mute">{agentName(e.agentId)} · <span className={kindTone[e.kind]}>{e.kind}</span> · {ago(e.ts)}{e.needsApproval && <span className="text-warn"> · approval required</span>}</div>
                  <div className="text-sm">{e.text}</div>
                </button>
              </li>
            ))}
          </ol>
        </Card>
        <Card>
          <CardHeader title={agent ? 'Tasks under evaluation' : 'All active tasks'} />
          <ul className="p-4 text-sm space-y-2">
            {(agent ? agent.tasks : d.agents.flatMap((a) => a.tasks)).map((t, i) => <li key={i} className="card p-2">{t}</li>)}
            {(agent ? agent.tasks : d.agents.flatMap((a) => a.tasks)).length === 0 && <Empty text="No open tasks" />}
          </ul>
          {agent && <div className="px-4 pb-4 text-xs text-mute">Assigned: {agent.satIds.join(', ')}</div>}
        </Card>
      </div>
      <Drawer open={!!tk} onClose={() => setTask(null)} title={tk?.title ?? ''} width="max-w-2xl">
        {tk && <TaskDetail t={tk} />}
      </Drawer>
      <Drawer open={!!ev} onClose={() => setEv(null)} title="Agent task detail">
        {ev && (
          <div className="space-y-4 text-sm">
            <div className="flex gap-2"><Badge>{agentName(ev.agentId)}</Badge><Badge>{ev.kind}</Badge>{ev.needsApproval && <Badge tone="text-warn border-warn/70">Approval required</Badge>}</div>
            <div className="text-xs text-mute font-mono">{fmtDT(ev.ts)} · {ev.id}</div>
            <p className="text-base">{ev.text}</p>
            <div><h4 className="font-semibold mb-1">Why</h4><p className="text-mute">{ev.why ?? 'No additional rationale recorded.'}</p></div>
            {ev.satId && <p>Satellite: <Link className="text-accent" to={`/fleet?sat=${ev.satId}`}>{ev.satId}</Link></p>}
            {ev.ref?.startsWith('AP') && <p>Approval: <Link className="text-accent" to="/approvals">{ev.ref}</Link></p>}
            {ev.ref?.startsWith('MS') && <p>Mission: <Link className="text-accent" to={`/missions?m=${ev.ref}`}>{ev.ref}</Link></p>}
            {ev.ref?.startsWith('MC') && <p>Case: <Link className="text-accent" to="/maintenance">{ev.ref}</Link></p>}
            <DemoTag />
          </div>
        )}
      </Drawer>
    </>
  )
}

const taskTone: Record<AgentTask['status'], string> = { running: 'running', 'waiting-human': 'Awaiting human', done: 'Completed', failed: 'rejected' }

function TaskBoard({ tasks, onOpen }: { tasks: AgentTask[]; onOpen: (id: string) => void }) {
  return (
    <Card className="mb-5">
      <CardHeader title="Autonomous task board" sub="Agents open, work and close these tasks on their own. They stop at human approval gates." />
      {tasks.length === 0 ? <Empty text="Agents are scanning telemetry. The first task opens automatically within seconds." /> : (
        <ul>
          {tasks.map((t) => {
            const done = t.checkpoints.filter((c) => c.done).length
            return (
              <li key={t.id}>
                <button className="w-full text-left px-4 py-3 border-b border-line last:border-0 hover:bg-panel2 flex flex-wrap items-center gap-3" onClick={() => onOpen(t.id)}>
                  <div className="flex-1 min-w-48"><div className="text-sm font-medium">{t.title}</div><div className="text-xs text-mute">{agentName(t.agentId)} - {t.caseId} - {t.trajectory.length} steps</div></div>
                  <div className="w-40"><div className="text-xs text-mute mb-1">Checkpoints {done}/{t.checkpoints.length}</div><div className="h-1.5 rounded-full bg-line overflow-hidden"><div className="h-full bg-gradient-to-r from-brand to-accent" style={{ width: `${(done / t.checkpoints.length) * 100}%` }} /></div></div>
                  {t.status === 'running' ? <Badge tone="text-accent border-accent/70 bg-accent/15">working</Badge> : <StatusBadge s={taskTone[t.status]} />}
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

function TaskDetail({ t }: { t: AgentTask }) {
  const done = t.checkpoints.filter((c) => c.done).length
  return (
    <div className="space-y-5 text-sm">
      <div className="flex gap-2 flex-wrap"><Badge>{t.id}</Badge><Badge>{t.status}</Badge><Badge>Score {done}/{t.checkpoints.length}</Badge><DemoTag /></div>
      <section><h4 className="font-semibold mb-2">Checkpoints</h4>
        <ul className="space-y-1">{t.checkpoints.map((c) => <li key={c.text} className={c.done ? 'text-ok' : 'text-mute'}>{c.done ? 'Done' : 'Open'}: {c.text}</li>)}</ul></section>
      <section><h4 className="font-semibold mb-2">Trajectory</h4>
        <ol className="space-y-2 font-mono text-xs">
          {t.trajectory.map((s, i) => (
            <li key={i} className="card p-2.5"><div className="text-mute">{fmtDT(s.ts)} - {agentName(s.agentId)} - <span className={s.kind === 'escalation' ? 'text-warn' : s.kind === 'tool' ? 'text-accent' : ''}>{s.kind}</span></div>{s.text}</li>
          ))}
        </ol></section>
    </div>
  )
}
