import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { buildSeed, buildSeries, compBase, type SeedState } from '@/data/seed'
import type { AgentTask, AutonomyState, Approval, AuditEvent, MaintCase, Mission, Notification, Policy, PolicyEval, Role, Severity } from '@/lib/types'
import { LIFECYCLE, MISSION_STAGES } from '@/lib/types'
import { riskFor, uid } from '@/lib/util'

export interface Data extends SeedState {
  role: Role
  notifications: Notification[]
  tasks: AgentTask[]
  autonomy: AutonomyState
}

interface Actions {
  tick: () => void
  setAutonomy: (on: boolean) => void
  setRole: (r: Role) => void
  reset: () => void
  markAllRead: () => void
  injectAnomaly: () => void
  diagnoseAnomaly: () => void
  evaluateDemoPolicy: () => void
  decideApproval: (id: string, decision: 'approved' | 'rejected' | 'hold' | 'info-requested', notes: string) => void
  advanceMission: (id: string) => { ok: boolean; reason?: string }
  createMaintRequest: (satId: string, compId: string) => string
  createWorkOrder: (caseId: string) => void
  setCaseStage: (caseId: string, stage: number) => void
  savePolicy: (p: Policy, note: string) => void
  evaluateAction: (satId: string, actor: string, action: string, kind?: string) => PolicyEval
}

export type Store = Data & Actions

const DEMO = { sat: 'CS-203', comp: 'CS-203/RW-02', case: 'MC-1100', approval: 'AP-3100', prox: 'AP-3101', mission: 'MS-2100' }
export const DEMO_IDS = DEMO
const servicerFor = (regime: string) => (regime === 'SSO' ? 'SVC-02' : regime === 'LEO' ? 'SVC-01' : 'SVC-03')

const AGENT_NAME: Record<string, string> = {
  'AG-HEALTH': 'Health Monitoring Agent', 'AG-FAULT': 'Fault Diagnosis Agent', 'AG-MAINT': 'Maintenance Planning Agent',
  'AG-MISSION': 'Mission Coordination Agent', 'AG-COMM': 'Communication Analysis Agent', 'AG-POLICY': 'Policy Compliance Agent',
}

const initial = (): Data => ({ ...buildSeed(), role: 'operator', notifications: [], tasks: [], autonomy: { enabled: true, tick: 0, scenarioStarted: false, generated: 0, lastGenTick: 0 } })

export const useStore = create<Store>()(
  persist(
    (set, get) => {
      /** Clone data, run a mutation, commit. Keeps every action a single atomic update. */
      const mutate = (fn: (d: Data, h: Helpers) => void) => {
        const s = get()
        const d = structuredClone({
          satellites: s.satellites, agents: s.agents, policies: s.policies, cases: s.cases, approvals: s.approvals,
          missions: s.missions, sessions: s.sessions, messages: s.messages, evals: s.evals, audit: s.audit,
          agentEvents: s.agentEvents, notifications: s.notifications, role: s.role, tasks: s.tasks, autonomy: s.autonomy,
        }) as Data
        fn(d, helpers(d))
        set(d)
      }

      type Helpers = ReturnType<typeof helpers>
      const helpers = (d: Data) => ({
        audit: (category: AuditEvent['category'], severity: Severity, actor: string, summary: string, o: { satId?: string; detail?: string; ref?: string } = {}) =>
          d.audit.unshift({ id: uid('AU'), ts: Date.now(), category, severity, actor, summary, ...o }),
        agent: (agentId: string, kind: 'observation' | 'recommendation' | 'policy-check' | 'escalation' | 'task' | 'result', text: string, o: { satId?: string; why?: string; needsApproval?: boolean; ref?: string } = {}) =>
          d.agentEvents.unshift({ id: uid('AE'), ts: Date.now(), agentId, kind, text, ...o }),
        notify: (text: string, severity: Severity, link?: string) => d.notifications.unshift({ id: uid('N'), ts: Date.now(), text, severity, link, read: false }),
        msg: (sessionId: string, dir: 'TX' | 'RX' | 'SYS', category: string, text: string, state: 'ack' | 'error' | 'pending' = 'ack', policyId?: string, offsetMs = 0) =>
          d.messages.push({ id: uid('MSG'), sessionId, ts: Date.now() + offsetMs, dir, category, text, state, policyId }),
        sat: (id: string) => d.satellites.find((x) => x.id === id)!,
        evalPolicy: (satId: string, actor: string, action: string, decision: PolicyEval['decision'], reason: string, ref?: string) => {
          const pol = d.policies.find((p) => p.satId === satId)
          const e: PolicyEval = { id: uid('EV'), ts: Date.now(), satId, actor, action, policyId: pol?.id ?? 'n/a', version: pol?.version ?? 0, decision, reason, ref }
          d.evals.unshift(e)
          d.audit.unshift({ id: uid('AU'), ts: Date.now(), category: 'policy', severity: decision === 'denied' ? 'medium' : 'info', satId, actor, summary: `${action} → ${decision}`, detail: reason, ref: e.id })
          return e
        },
      })

      const recomputeSat = (d: Data, satId: string) => {
        const sat = d.satellites.find((s) => s.id === satId)
        if (!sat || sat.kind === 'servicer') return
        const worst = Math.min(...sat.components.map((c) => c.health))
        if (sat.status !== 'Servicing' && sat.status !== 'Hold') sat.status = worst < 80 ? 'Attention' : 'Nominal'
        sat.condition = worst >= 80 ? 'All subsystems within nominal limits' : `Degraded: ${sat.components.filter((c) => c.health < 80).map((c) => c.name).join(', ')}`
      }

      const decide = (policy: Policy | undefined, kind: string, health?: number): { decision: PolicyEval['decision']; reason: string } => {
        if (!policy) return { decision: 'denied', reason: 'No servicing policy on file for this satellite' }
        if (policy.humanRequired.includes(kind)) return { decision: 'approval required', reason: `${kind} is on the human-required list of ${policy.id} v${policy.version}` }
        if (health !== undefined && health < policy.escalationThreshold) return { decision: 'approval required', reason: `Health ${health}% below escalation threshold ${policy.escalationThreshold}%` }
        return { decision: 'allowed', reason: `${kind} is permitted for AI agents under ${policy.id} v${policy.version}` }
      }


      const CHECKS = ['Anomaly detected', 'Diagnosis and case filed', 'Policy evaluated', 'Human decision obtained', 'Servicing mission executed', 'Post-service verification passed']
      const step = (t: AgentTask, agentId: string, kind: AgentTask['trajectory'][number]['kind'], text: string) => t.trajectory.push({ ts: Date.now(), agentId, kind, text })
      const newTask = (d: Data, c: { id: string; name: string; satId: string }, caseId: string) => {
        const t: AgentTask = {
          id: uid('TASK'), agentId: 'AG-HEALTH', title: `Respond to ${c.name} anomaly (${c.satId})`, satId: c.satId, componentId: c.id, caseId,
          stage: 'detected', status: 'running', checkpoints: CHECKS.map((text) => ({ text, done: false })), trajectory: [], createdAt: Date.now(),
        }
        d.tasks.unshift(t)
        return t
      }

      const doInject = (d: Data, h: Helpers) => {
        const sat = h.sat(DEMO.sat)
        const c = sat.components.find((x) => x.id === DEMO.comp)!
        if (c.issue || d.cases.some((k) => k.id === DEMO.case)) return
        const b = compBase('RW-02')
        c.health = 68
        c.risk = riskFor(68)
        c.series = buildSeries(b.base, b.warn, 68, 4242)
        c.rulDays = 55
        c.issue = 'Increasing vibration trend'
        c.recommendation = 'Schedule inspection and evaluate replacement'
        d.autonomy.scenarioStarted = true
        recomputeSat(d, sat.id)
        h.notify('New warning: RW-02 vibration trend on Aurora EO-3 (simulated)', 'high', '/monitoring')
        h.agent('AG-HEALTH', 'observation', 'Anomaly: RW-02 vibration RMS rising, health 92% to 68% (simulated)', { satId: sat.id, why: 'Vibration slope exceeded 3 sigma of fleet baseline for 6 consecutive orbits.', ref: DEMO.comp })
        h.audit('telemetry', 'high', 'Health Monitoring Agent', 'Anomaly detected: Reaction Wheel RW-02 vibration trend', { satId: sat.id, ref: DEMO.comp, detail: 'Simulated telemetry, demo data' })
        d.agents.find((a) => a.id === 'AG-HEALTH')!.tasks.unshift('Investigate CS-203 RW-02 vibration')
      }

      const doDiagnose = (d: Data, h: Helpers, satId: string, compId: string, caseId: string) => {
        if (d.cases.some((k) => k.id === caseId)) return
        const sat = h.sat(satId)
        const c = sat.components.find((x) => x.id === compId)!
        const demo = compId === DEMO.comp
        const last = c.series[c.series.length - 1]
        h.agent('AG-FAULT', 'result', demo ? 'Diagnosis: probable bearing lubricant degradation in RW-02 (confidence 0.74, simulated)' : `Diagnosis: ${c.name} wear-out trend (confidence 0.66, simulated)`, {
          satId, ref: compId,
          why: demo ? 'Vibration harmonics at 1.8x wheel speed plus +11% motor current match the lubricant-starvation signature in the demo model.' : `${c.metric} drifted toward its warning threshold; pattern matches slow wear-out in the demo model.`,
        })
        d.cases.unshift({
          id: caseId, satId, componentId: compId, problem: demo ? 'Reaction wheel RW-02 abnormal vibration trend' : (c.issue ?? `${c.name} degradation`), severity: c.health < 60 ? 'high' : 'high',
          evidence: [`${c.metric} ${last} ${c.unit} (warn ${c.warnAt})`, `Health ${c.health}%`, 'Simulated model output, not a validated forecast'],
          recommendation: demo ? 'Schedule inspection and evaluate replacement of RW-02 with modular wheel cartridge' : `Inspect and replace or repair ${c.name}`,
          urgency: 'Elevated, within 21 days', window: 'Next servicing window', resources: [servicerFor(sat.orbit.regime), 'Replacement module'], stage: 2, createdAt: Date.now(),
        })
        h.agent('AG-MAINT', 'recommendation', `Maintenance request ${caseId} created: inspect and evaluate ${c.name} replacement`, { satId, ref: caseId, why: `Health ${c.health}% is below the policy escalation threshold.` })
        h.audit('ticket', 'medium', 'Maintenance Planning Agent', `Maintenance case ${caseId} opened (Detected, Diagnosed, Proposed)`, { satId, ref: caseId })
        h.notify(`Maintenance recommendation ${caseId} generated for ${sat.name}`, 'medium', '/maintenance')
      }

      const doPolicy = (d: Data, h: Helpers, satId: string, compId: string, caseId: string, apId: string, missionId: string) => {
        if (d.approvals.some((a) => a.id === apId)) return
        const sat = h.sat(satId)
        const c = sat.components.find((x) => x.id === compId)!
        const pol = d.policies.find((p) => p.satId === satId)
        const r = decide(pol, 'Component replacement', c.health)
        h.evalPolicy(satId, 'Policy Compliance Agent', `Replace ${c.name}`, r.decision, r.reason, caseId)
        const ap: Approval = {
          id: apId, operation: `Replace ${c.name} (${sat.name})`, kind: 'Component replacement', satId, caseId, missionId,
          requester: 'Maintenance Planning Agent',
          justification: `${c.name} shows ${c.issue ?? 'a degradation trend'} (health ${c.health}%). Replacement in the next window avoids loss of margin (simulated analysis).`,
          telemetry: [`${c.metric} ${c.series[c.series.length - 1]} ${c.unit}`, `Health ${c.health}%`], risk: 'High', policyId: pol?.id ?? 'n/a',
          consequences: 'Failure would degrade the satellite mission; servicing carries proximity-operation risk.',
          mitigation: 'Servicer holds at 200 m keep-out until proximity approval; abort corridor pre-planned; customer HOLD honored.',
          createdAt: Date.now(), reviewer: 'Dr. A. Lindqvist', status: 'pending',
        }
        d.approvals.unshift(ap)
        const mc = d.cases.find((x) => x.id === caseId)!
        mc.stage = 3
        mc.approvalId = apId
        h.agent('AG-POLICY', 'policy-check', `Policy ${pol?.id} v${pol?.version}: ${r.decision}. ${r.reason}`, { satId, ref: apId })
        h.agent('AG-MAINT', 'escalation', `Escalated to Human Approval Authority: ${apId}`, { satId, needsApproval: true, ref: apId, why: 'High-risk component replacement may not proceed on AI authority alone.' })
        h.audit('approval', 'high', 'Policy Compliance Agent', `Approval request ${apId} created (pending human review)`, { satId, ref: apId })
        h.notify(`Approval required: ${apId} ${c.name} replacement`, 'high', '/approvals')
        d.agents.find((a) => a.id === 'AG-MAINT')!.state = 'Awaiting human'
      }

      const advanceTask = (d: Data, h: Helpers, t: AgentTask) => {
        const sat = h.sat(t.satId)
        const comp = sat.components.find((c) => c.id === t.componentId)!
        const n = d.approvals.length
        if (t.stage === 'detected') {
          step(t, 'AG-FAULT', 'tool', `run_diagnosis(${comp.id})`)
          doDiagnose(d, h, t.satId, t.componentId, t.caseId)
          step(t, 'AG-FAULT', 'observation', 'Probable wear-out cause identified; confidence is simulated.')
          step(t, 'AG-MAINT', 'tool', `create_maintenance_case(${t.caseId})`)
          t.checkpoints[1].done = true
          t.stage = 'proposed'
        } else if (t.stage === 'proposed') {
          const demo = t.componentId === DEMO.comp
          const apId = demo ? DEMO.approval : `AP-${3200 + n}`
          const msId = demo ? DEMO.mission : `MS-${2200 + d.missions.length}`
          step(t, 'AG-POLICY', 'tool', `evaluate_policy("Component replacement", ${t.satId})`)
          doPolicy(d, h, t.satId, t.componentId, t.caseId, apId, msId)
          step(t, 'AG-POLICY', 'observation', 'Decision: approval required (component replacement is on the human-required list).')
          step(t, 'AG-MAINT', 'escalation', `request_human_approval(${apId}). I will not proceed until a human decides.`)
          t.checkpoints[2].done = true
          t.stage = 'awaiting-approval'
          t.status = 'waiting-human'
          t.agentId = 'AG-MAINT'
        } else if (t.stage === 'awaiting-approval') {
          const mc = d.cases.find((k) => k.id === t.caseId)
          const ap = d.approvals.find((a) => a.id === mc?.approvalId)
          if (ap?.status === 'approved') {
            step(t, 'AG-MISSION', 'observation', `${ap.id} approved by ${ap.decidedBy}. Mission scheduled.`)
            t.checkpoints[3].done = true
            t.stage = 'mission'; t.status = 'running'; t.agentId = 'AG-MISSION'
          } else if (ap?.status === 'rejected') {
            step(t, 'AG-MAINT', 'observation', `${ap.id} rejected. Standing down; case returned to Proposed for rework.`)
            t.status = 'failed'; t.stage = 'done'
          } else if (ap && ap.status !== 'pending' && !t.trajectory.some((x) => x.text.includes(ap.status))) {
            step(t, 'AG-MAINT', 'observation', `${ap.id} is ${ap.status}; waiting for the reviewer.`)
          }
        } else if (t.stage === 'mission') {
          const mc = d.cases.find((k) => k.id === t.caseId)
          const ms = d.missions.find((m) => m.id === mc?.missionId)
          if (!ms) return
          const gate = ms.gates[ms.stage]
          const gateOpen = !gate || d.approvals.find((a) => a.id === gate)?.status === 'approved'
          if (ms.stage >= 11) {
            t.checkpoints[4].done = true; t.checkpoints[5].done = true
            step(t, 'AG-MISSION', 'observation', `${ms.id} complete; ${comp.name} health ${comp.health}%. Report filed.`)
            t.status = 'done'; t.stage = 'done'
          } else {
            if (ms.stage >= 9) t.checkpoints[4].done = true
            const waiting = !gateOpen
            if (waiting && t.status !== 'waiting-human') step(t, 'AG-MISSION', 'escalation', `Paused at "${MISSION_STAGES[ms.stage]}": waiting for ${gate}.`)
            t.status = waiting ? 'waiting-human' : 'running'
          }
        }
      }

      return {
        ...initial(),

        setRole: (role) => set({ role }),
        reset: () => set(initial()),
        markAllRead: () => set({ notifications: get().notifications.map((n) => ({ ...n, read: true })) }),

        evaluateAction: (satId, actor, action, kind) => {
          let out!: PolicyEval
          mutate((d, h) => {
            const pol = d.policies.find((p) => p.satId === satId)
            const r = decide(pol, kind ?? action)
            out = h.evalPolicy(satId, actor, action, r.decision, r.reason)
          })
          return out
        },

        // ---- Scenario steps (manual buttons call the same pipeline the autonomous agents use) ----
        injectAnomaly: () => mutate((d, h) => doInject(d, h)),
        diagnoseAnomaly: () => mutate((d, h) => doDiagnose(d, h, DEMO.sat, DEMO.comp, DEMO.case)),
        evaluateDemoPolicy: () => mutate((d, h) => doPolicy(d, h, DEMO.sat, DEMO.comp, DEMO.case, DEMO.approval, DEMO.mission)),

        setAutonomy: (on) => mutate((d, h) => { d.autonomy.enabled = on; h.audit('system', 'info', 'Operator', `Agent autonomy ${on ? 'enabled' : 'paused'}`) }),

        // ---- Autonomous runtime: one tick = every agent takes at most one step ---------------
        tick: () => {
          if (!get().autonomy.enabled) return
          mutate((d, h) => {
            const A = d.autonomy
            A.tick++
            const T = A.tick
            // live telemetry stream
            if (T % 3 === 0) {
              d.satellites.forEach((sat) => sat.components.forEach((c) => {
                const b = compBase(c.id.split('/')[1])
                const last = c.series[c.series.length - 1]
                const nx = Math.max(0, +(last + (Math.random() - 0.5) * (b.warn - b.base) * 0.015).toFixed(2))
                c.series = [...c.series.slice(1), nx]
              }))
            }
            // the scripted scenario starts by itself
            if (!A.scenarioStarted && T >= 3) { A.scenarioStarted = true; doInject(d, h) }
            // continuous simulated fault generator (labelled simulated)
            if (A.scenarioStarted && A.generated < 3 && T - A.lastGenTick >= 25 && !d.tasks.some((t) => t.status === 'running' || t.status === 'waiting-human')) {
              const pool = d.satellites.filter((x) => x.kind === 'customer').flatMap((x) => x.components).filter((c) => c.health >= 90 && !c.id.endsWith('RW-02'))
              const c = pool[Math.floor(Math.random() * pool.length)]
              if (c) {
                const b = compBase(c.id.split('/')[1])
                c.health = 66; c.risk = riskFor(66); c.series = buildSeries(b.base, b.warn, 66, T * 31); c.rulDays = 40
                c.issue = 'Abnormal degradation trend (simulated fault injection)'; c.recommendation = 'Inspect and evaluate repair'
                recomputeSat(d, c.satId)
                A.generated++; A.lastGenTick = T
                h.notify(`New warning: ${c.name} on ${h.sat(c.satId).name} (simulated fault)`, 'high', '/monitoring')
                h.audit('telemetry', 'high', 'Fault generator (simulation)', `Simulated degradation injected: ${c.name}`, { satId: c.satId, ref: c.id })
              }
            }
            // Health agent scan: open a task for any unattended degraded component
            d.satellites.filter((x) => x.kind === 'customer').forEach((sat) => sat.components.forEach((c) => {
              if (c.health >= 75) return
              if (d.cases.some((k) => k.componentId === c.id && k.stage < 7) || d.tasks.some((t) => t.componentId === c.id && t.stage !== 'done')) return
              const demo = c.id === DEMO.comp
              const n = d.cases.length
              const caseId = demo ? DEMO.case : `MC-${1300 + n}`
              const t = newTask(d, c, caseId)
              step(t, 'AG-HEALTH', 'thought', `Scan found ${c.name} on ${sat.name} at ${c.health}% health, below the 75% watch level and with no open case.`)
              step(t, 'AG-HEALTH', 'tool', `query_telemetry(${c.id}) -> ${c.series[c.series.length - 1]} ${c.unit} (warn ${c.warnAt})`)
              if (!c.issue) {
                c.issue = 'Degradation trend detected'; c.recommendation = 'Inspect and evaluate repair'
                h.agent('AG-HEALTH', 'observation', `Anomaly: ${c.name} health ${c.health}% (simulated)`, { satId: sat.id, ref: c.id, why: 'Health fell below the watch level.' })
                h.audit('telemetry', 'medium', 'Health Monitoring Agent', `Anomaly detected: ${c.name}`, { satId: sat.id, ref: c.id })
              }
              t.checkpoints[0].done = true
            }))
            // advance every active task by one step
            d.tasks.filter((t) => t.status === 'running' || t.status === 'waiting-human').forEach((t) => advanceTask(d, h, t))
          })

          // Mission agent: drive scheduled/active missions through every phase whose approval gate is clear
          const s = get()
          if (s.autonomy.tick % 2 === 0) {
            s.missions.filter((m) => m.stage < 11 && (m.status === 'Active' || m.status === 'Scheduled' || m.status === 'Blocked')).forEach((m) => {
              const gate = m.gates[m.stage]
              const ok = !gate || get().approvals.find((a) => a.id === gate)?.status === 'approved'
              if (!ok) return
              const r = get().advanceMission(m.id)
              if (r.ok) {
                const nm = get().missions.find((x) => x.id === m.id)!
                mutate((d) => {
                  const t = d.tasks.find((x) => x.caseId === m.caseId && x.stage === 'mission')
                  if (t) step(t, 'AG-MISSION', 'tool', `advance_mission_phase(${m.id}) -> ${nm.stage >= 11 ? 'Mission complete' : MISSION_STAGES[nm.stage]}`)
                })
              }
            })
          }
        },

        // ---- Human-in-the-loop decision -----------------------------------------------------
        decideApproval: (id, decision, notes) =>
          mutate((d, h) => {
            const ap = d.approvals.find((x) => x.id === id)
            if (!ap) return
            const actor = 'Human Approval Authority'
            ap.status = decision
            ap.notes = notes
            ap.decidedAt = Date.now()
            ap.decidedBy = actor
            const label = { approved: 'approved', rejected: 'rejected', hold: 'placed on hold', 'info-requested': 'returned for more information' }[decision]
            h.audit('approval', decision === 'approved' ? 'info' : 'medium', actor, `${ap.operation} ${label}`, { satId: ap.satId, detail: notes, ref: ap.id })
            h.agent(ap.requester === 'Maintenance Planning Agent' ? 'AG-MAINT' : 'AG-MISSION', 'result', `Human decision on ${ap.id}: ${label}`, { satId: ap.satId, ref: ap.id, why: notes })
            h.notify(`${ap.id} ${label}`, decision === 'approved' ? 'low' : 'medium', '/approvals')

            const mc = d.cases.find((x) => x.id === ap.caseId)
            let ms = d.missions.find((x) => x.id === ap.missionId)

            if (decision === 'approved') {
              if (ap.kind === 'Component replacement' && mc && !ms) {
                // spawn mission scheduled from the approved service plan
                const prox: Approval = {
                  id: ap.id === DEMO.approval ? DEMO.prox : `${ap.id}-PX`, operation: `Close-proximity operations & docking (${h.sat(ap.satId).name})`, kind: 'Close-proximity operations', satId: ap.satId, missionId: ap.missionId, caseId: mc.id,
                  requester: 'Mission Coordination Agent', justification: 'Rendezvous to ≤25 m and docking required for wheel cartridge exchange.', telemetry: ['Relative nav solution nominal (sim)', 'Servicer health nominal (sim)'],
                  risk: 'Critical', policyId: ap.policyId, consequences: 'Collision or contact risk with customer asset.', mitigation: '200 m keep-out hold, safe-abort corridor, customer HOLD channel monitored.',
                  createdAt: Date.now(), reviewer: 'Dr. A. Lindqvist', status: 'pending',
                }
                d.approvals.unshift(prox)
                ms = {
                  id: ap.missionId ?? DEMO.mission, title: `${mc.componentId.split('/')[1]} replacement - ${h.sat(ap.satId).name}`, satId: ap.satId, servicerId: servicerFor(h.sat(ap.satId).orbit.regime), caseId: mc.id, stage: 5, risk: 'High',
                  gates: { 4: ap.id, 5: prox.id }, checklist: [], events: [{ ts: Date.now(), text: `Authorization recorded (${ap.id}); mission scheduled` }], status: 'Scheduled', createdAt: Date.now(),
                }
                ms.checklist = ['Verify customer authorization on file', 'Confirm servicer fuel & health', 'Plan approach trajectory (keep-out 200 m)', 'Establish encrypted link', 'Execute inspection / servicing procedure', 'Run post-service telemetry check', 'File mission report'].map((text, i) => ({ text, done: i < 1 }))
                d.missions.unshift(ms)
                mc.missionId = ms.id
                h.agent('AG-POLICY', 'escalation', 'Proximity operations require separate approval AP-3101', { satId: ap.satId, needsApproval: true, ref: prox.id, why: 'Policy lists Close-proximity operations as human-required.' })
                h.evalPolicy(ap.satId, 'Policy Compliance Agent', 'Close-proximity operations', 'approval required', 'Close-proximity operations require human approval', prox.id)
                h.notify('Approval required: AP-3101 close-proximity operations', 'high', '/approvals')
                h.audit('mission', 'info', 'Mission Coordination Agent', `Mission ${ms.id} scheduled`, { satId: ap.satId, ref: ms.id })
                
              } else if (ms) {
                ms.status = ms.stage >= 11 ? 'Completed' : 'Active'
                ms.events.push({ ts: Date.now(), text: `${ap.id} approved - gate cleared` })
              }
              if (mc && ap.kind === 'Component replacement') {
                mc.stage = Math.max(mc.stage, 4)
                h.audit('ticket', 'info', actor, `${mc.id} advanced to Scheduled`, { satId: mc.satId, ref: mc.id })
              }
              d.agents.find((a) => a.id === 'AG-MAINT')!.state = 'Planning'
            } else if (ms) {
              ms.status = 'Blocked'
              ms.events.push({ ts: Date.now(), text: `${ap.id} ${label} - mission blocked` })
              if (decision === 'rejected' && mc) mc.stage = Math.min(mc.stage, 2)
            }
          }),

        // ---- Mission phase simulation -------------------------------------------------------
        advanceMission: (id) => {
          const s0 = get()
          const m0 = s0.missions.find((x) => x.id === id)
          if (!m0 || m0.stage >= 11) return { ok: false, reason: 'Mission already complete' }
          const gate = m0.gates[m0.stage]
          if (gate) {
            const ap = s0.approvals.find((a) => a.id === gate)
            if (!ap || ap.status !== 'approved') {
              mutate((d, h) => {
                const dm = d.missions.find((x) => x.id === id)!
                dm.status = 'Blocked'
                h.evalPolicy(dm.satId, 'Mission Coordination Agent', `Advance past "${MISSION_STAGES[dm.stage]}"`, 'approval required', `Blocked until ${gate} is approved by a human`, id)
                h.notify(`${id} blocked: ${gate} not approved`, 'medium', '/approvals')
              })
              return { ok: false, reason: `Approval ${gate} is ${ap?.status ?? 'missing'} - human approval required` }
            }
          }
          mutate((d, h) => {
            const ms = d.missions.find((x) => x.id === id)!
            const sat = h.sat(ms.satId)
            const svc = h.sat(ms.servicerId)
            const mc = d.cases.find((x) => x.id === ms.caseId)
            ms.stage += 1
            ms.status = 'Active'
            const ns = ms.stage
            const stageName = ns <= 10 ? MISSION_STAGES[ns] : 'Mission complete'
            ms.events.push({ ts: Date.now(), text: `Entered phase ${ns + 1 > 11 ? 11 : ns + 1}: ${stageName}` })
            ms.checklist.forEach((c, i) => (c.done = i < Math.ceil((Math.min(ns, 11) * 7) / 11)))
            h.audit('mission', 'info', 'Mission Coordination Agent', `${ms.id}: ${stageName}`, { satId: ms.satId, ref: ms.id })
            const sess = () => d.sessions.find((x) => x.missionId === ms.id)
            const pol = d.policies.find((p) => p.satId === ms.satId)

            if (ns === 6) {
              svc.status = 'Servicing'; sat.status = 'Servicing'
              h.evalPolicy(ms.satId, 'Mission Coordination Agent', 'Close-proximity operations', 'allowed', `Human approval ${ms.gates[5]} recorded`, ms.id)
              h.agent('AG-MISSION', 'task', `${svc.name} approaching ${sat.name}; holding at 200 m keep-out`, { satId: ms.satId, ref: ms.id })
            }
            if (ns === 7) {
              const sid = uid('CX')
              d.sessions.unshift({ id: sid, servicerId: ms.servicerId, satId: ms.satId, missionId: ms.id, status: 'Active', start: Date.now(), quality: 93, latencyMs: 61, authorized: 'authorized' })
              h.msg(sid, 'SYS', 'Session', 'Communication session requested', 'ack', pol?.id, 0)
              h.msg(sid, 'RX', 'Authorization handshake', 'Customer satellite authorization confirmed', 'ack', pol?.id, 2000)
              h.msg(sid, 'TX', 'Diagnostic telemetry', `Diagnostic telemetry requested: ${mc?.componentId.split('/')[1] ?? 'subsystem'}`, 'ack', pol?.id, 4000)
              h.msg(sid, 'RX', 'Diagnostic telemetry', 'Telemetry response received', 'ack', pol?.id, 6000)
              h.msg(sid, 'SYS', 'Analysis', 'AI agent begins anomaly analysis', 'ack', pol?.id, 9000)
              h.msg(sid, 'SYS', 'Analysis', 'Maintenance recommendation confirmed', 'ack', pol?.id, 14000)
              h.evalPolicy(ms.satId, 'Mission Coordination Agent', 'Open communication session', 'allowed', 'Customer authorization confirmed; category permitted', sid)
              h.audit('comms', 'info', 'Communication Analysis Agent', `Session ${sid} established (simulated)`, { satId: ms.satId, ref: sid })
              h.agent('AG-COMM', 'observation', `Session ${sid} up: quality 93%, latency 61 ms (simulated)`, { satId: ms.satId, ref: sid })
            }
            if (ns === 8) {
              const s = sess()
              if (s) {
                h.msg(s.id, 'TX', 'Servicing command (approved)', 'Wheel spin-down command (approved)', 'ack', pol?.id)
                h.msg(s.id, 'RX', 'Servicing command (approved)', 'Spin-down acknowledged: 0 rpm', 'ack', pol?.id, 1500)
                h.msg(s.id, 'SYS', 'Servicing', 'Inspection complete; cartridge exchanged (simulated)', 'ack', pol?.id, 4000)
              }
              if (mc) mc.stage = Math.max(mc.stage, 5)
              h.audit('repair', 'info', 'Satellite Maintenance Engineer', 'Inspection and component exchange performed (simulated)', { satId: ms.satId, ref: ms.id })
              h.agent('AG-MISSION', 'task', 'Servicing in progress', { satId: ms.satId, ref: ms.id })
            }
            if (ns === 9) {
              const comp = sat.components.find((c) => c.id === mc?.componentId)
              if (comp) {
                const key = comp.id.split('/')[1]
                const b = compBase(key)
                comp.health = 97
                comp.risk = riskFor(97)
                comp.series = comp.series.slice(0, 36).concat(buildSeries(b.base, b.warn, 97, 99, 12))
                comp.issue = undefined
                comp.recommendation = undefined
                comp.rulDays = undefined
              }
              if (mc) mc.stage = 6
              const s = sess()
              if (s) h.msg(s.id, 'RX', 'Diagnostic telemetry', 'Post-service telemetry nominal: vibration 4.3 mg', 'ack', pol?.id)
              sat.history.push({ date: new Date().toISOString().slice(0, 10), text: `${mc?.problem ?? 'Service'} - repaired and verified (simulated, ${ms.id})` })
              h.audit('repair', 'info', 'Health Monitoring Agent', 'Post-service verification passed (simulated)', { satId: ms.satId, ref: ms.id })
              h.agent('AG-HEALTH', 'result', 'Verification: component health restored to 97% (simulated)', { satId: ms.satId, ref: ms.id })
              recomputeSat(d, sat.id)
            }
            if (ns === 11) {
              ms.status = 'Completed'
              svc.status = 'Standby'
              if (sat.status === 'Servicing') sat.status = 'Nominal'
              recomputeSat(d, sat.id)
              const s = sess()
              if (s) { s.status = 'Closed'; s.end = Date.now(); h.msg(s.id, 'SYS', 'Session', 'Communication session closed', 'ack', pol?.id) }
              if (mc) {
                mc.stage = 7
                mc.report = `Mission ${ms.id} completed. ${mc.problem} addressed via ${mc.recommendation}. Post-service verification passed (simulated).`
              }
              h.notify(`Mission ${ms.id} completed - summary available`, 'low', `/missions?m=${ms.id}`)
              h.agent('AG-MISSION', 'result', `Mission ${ms.id} complete; report filed`, { satId: ms.satId, ref: ms.id })
              h.audit('mission', 'info', 'Mission Coordination Agent', `${ms.id} completed and report filed`, { satId: ms.satId, ref: ms.id })
            }
            if (ns < 11) h.notify(`${ms.id}: ${stageName}`, 'info', '/missions')
          })
          return { ok: true }
        },

        // ---- Maintenance ---------------------------------------------------------------------
        createMaintRequest: (satId, compId) => {
          const existing = get().cases.find((c) => c.componentId === compId && c.stage < 7)
          if (existing) return existing.id
          const id = `MC-${1200 + get().cases.length}`
          mutate((d, h) => {
            const sat = h.sat(satId)
            const c = sat.components.find((x) => x.id === compId)!
            d.cases.unshift({
              id, satId, componentId: compId, problem: c.issue ?? `${c.name} degradation`, severity: c.health < 60 ? 'high' : 'medium',
              evidence: [`${c.metric}: ${c.series[c.series.length - 1]} ${c.unit} (warn ${c.warnAt})`, `Health ${c.health}% (simulated)`],
              recommendation: c.recommendation ?? 'Inspect and evaluate repair options', urgency: 'Moderate', window: 'TBD', resources: ['SVC-01'], stage: 2, createdAt: Date.now(),
            })
            h.audit('ticket', 'info', 'Satellite Maintenance Engineer', `Maintenance request ${id} created from ${c.name}`, { satId, ref: id })
            h.notify(`Maintenance request ${id} created`, 'info', '/maintenance')
          })
          return id
        },
        createWorkOrder: (caseId) =>
          mutate((d, h) => {
            const c = d.cases.find((x) => x.id === caseId)
            if (!c || c.workOrder) return
            c.workOrder = `WO-${caseId.slice(3)}`
            h.audit('ticket', 'info', 'Satellite Maintenance Engineer', `Work order ${c.workOrder} created (simulated)`, { satId: c.satId, ref: caseId })
          }),
        setCaseStage: (caseId, stage) =>
          mutate((d, h) => {
            const c = d.cases.find((x) => x.id === caseId)
            if (!c) return
            // High-risk stages may not be skipped past the approval gate
            if (stage >= 4 && c.stage < 4 && d.approvals.find((a) => a.id === c.approvalId)?.status !== 'approved') return
            c.stage = stage
            h.audit('ticket', 'info', 'Satellite Maintenance Engineer', `${caseId} status set to ${LIFECYCLE[stage]}`, { satId: c.satId, ref: caseId })
          }),

        savePolicy: (p, note) =>
          mutate((d, h) => {
            const i = d.policies.findIndex((x) => x.id === p.id)
            const nv = i >= 0 ? d.policies[i].version + 1 : 1
            const next: Policy = { ...p, version: nv, versions: [...(i >= 0 ? d.policies[i].versions : []), { v: nv, date: new Date().toISOString().slice(0, 10), author: 'Demo user', note }] }
            if (i >= 0) d.policies[i] = next
            else d.policies.push(next)
            h.audit('policy', 'info', 'Demo user', `Policy ${p.id} saved as v${nv}`, { satId: p.satId, detail: note, ref: p.id })
          }),
      }
    },
    { name: 'orbit-observers-demo-v2', version: 2 },
  ),
)

export const agentName = (id: string) => AGENT_NAME[id] ?? id
export const satName = (sats: { id: string; name: string }[], id?: string) => sats.find((s) => s.id === id)?.name ?? id ?? '-'

export type { Mission, MaintCase }
