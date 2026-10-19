import type { Agent, AgentEvent, Approval, AuditEvent, CommMsg, CommSession, Component, MaintCase, Mission, Policy, PolicyEval, Satellite } from '@/lib/types'
import { rng, riskFor } from '@/lib/util'

// Demo assignment of serviceability tier / tumble estimate per customer satellite (not real data).
const TIER_DEMO: Record<string, [Satellite['serviceTier'], number]> = {
  'CS-101': ['C2_beacon', 3], 'CS-102': ['C1_fiducials', 2], 'CS-201': ['C3_ios_mode', 1], 'CS-202': ['C1_fiducials', 1],
  'CS-203': ['C2_beacon', 0.5], 'CS-301': ['C1_fiducials', 3], 'CS-302': ['C2_id_only', 1], 'CS-401': ['C0_unprepared', 3],
  'CS-501': ['C0_unprepared', 0.5], 'CS-502': ['C1_fiducials', 5],
}

export const OPERATORS = ['Helios Telecom', 'Aurora Earth Observation', 'Nordlicht Navigation', 'Vesta Broadcast', 'Meridian Weather']
export const CUSTOMER_DEMO_OPERATOR = 'Aurora Earth Observation'

const TEMPLATES = [
  { key: 'BAT', name: 'Battery Pack', subsystem: 'Power', metric: 'Cell voltage spread', unit: 'mV', base: 22, warn: 120 },
  { key: 'SA', name: 'Solar Array', subsystem: 'Power', metric: 'Array output deficit', unit: '%', base: 2, warn: 15 },
  { key: 'THM', name: 'Thermal Control Loop', subsystem: 'Thermal', metric: 'Radiator ΔT error', unit: '°C', base: 0.8, warn: 6 },
  { key: 'ANT', name: 'Comm Transceiver', subsystem: 'Communications', metric: 'Bit error rate ×1e-6', unit: 'ppm', base: 2, warn: 40 },
  { key: 'ADCS', name: 'Star Tracker / ADCS', subsystem: 'ADCS', metric: 'Pointing error', unit: 'mdeg', base: 12, warn: 80 },
  { key: 'RW-01', name: 'Reaction Wheel RW-01', subsystem: 'ADCS', metric: 'Vibration (RMS)', unit: 'mg', base: 4, warn: 22 },
  { key: 'RW-02', name: 'Reaction Wheel RW-02', subsystem: 'ADCS', metric: 'Vibration (RMS)', unit: 'mg', base: 4, warn: 22 },
  { key: 'PRP', name: 'Propulsion System', subsystem: 'Propulsion', metric: 'Thruster valve current drift', unit: 'mA', base: 5, warn: 40 },
  { key: 'OBC', name: 'Onboard Computer', subsystem: 'Avionics', metric: 'Single-event upset rate', unit: '/day', base: 1, warn: 9 },
  { key: 'PLD', name: 'Payload Electronics', subsystem: 'Payload', metric: 'Sensor noise floor', unit: 'dB', base: 3, warn: 14 },
]

export function buildSeries(base: number, warn: number, health: number, seed: number, len = 48) {
  const r = rng(seed)
  const last = base + ((warn - base) * (100 - health)) / 40
  const out: number[] = []
  for (let i = 0; i < len; i++) {
    const p = i / (len - 1)
    const ramp = base + (last - base) * Math.pow(p, health < 90 ? 2.2 : 1)
    out.push(+(ramp + (r() - 0.5) * (warn - base) * 0.04).toFixed(2))
  }
  return out
}

export function mkComp(satId: string, key: string, health: number, seed: number): Component {
  const t = TEMPLATES.find((x) => x.key === key)!
  return {
    id: `${satId}/${key}`,
    satId,
    name: t.name,
    subsystem: t.subsystem,
    unit: t.unit,
    metric: t.metric,
    health,
    warnAt: t.warn,
    series: buildSeries(t.base, t.warn, health, seed),
    risk: riskFor(health),
    rulDays: health >= 90 ? undefined : Math.max(10, Math.round((health - 40) * 6)),
  }
}

export const compBase = (key: string) => TEMPLATES.find((x) => x.key === key)!

type Over = Record<string, number>
function mkSat(
  id: string, name: string, kind: 'customer' | 'servicer', operator: string, role: string,
  orbit: Satellite['orbit'], agentId: string, over: Over = {}, extra: Partial<Satellite> = {},
): Satellite {
  const r = rng(id.split('').reduce((a, c) => a + c.charCodeAt(0), 0))
  const components = TEMPLATES.map((t, i) => mkComp(id, t.key, over[t.key] ?? Math.round(90 + r() * 9), i * 97 + id.length * 13 + Math.round(r() * 1000)))
  const worst = Math.min(...components.map((c) => c.health))
  const status: Satellite['status'] = kind === 'servicer' ? 'Standby' : worst < 60 ? 'Attention' : worst < 80 ? 'Attention' : 'Nominal'
  return {
    id, name, kind, operator, role, orbit, status, agentId, policyId: kind === 'customer' ? `POL-${id}` : undefined,
    condition: worst >= 80 ? 'All subsystems within nominal limits' : `Degraded: ${components.filter((c) => c.health < 80).map((c) => c.name).join(', ')}`,
    serviceTier: TIER_DEMO[id]?.[0], estTumbleDegS: TIER_DEMO[id]?.[1],
    components,
    history: [
      { date: '2025-11-02', text: 'Routine AI health baseline established' },
      { date: '2026-03-18', text: 'Firmware patch campaign v4.2 applied (customer-initiated)' },
    ],
    ...extra,
  }
}

const orb = (regime: string, altKm: number, incDeg: number, raanDeg: number, ecc: number, anomalyDeg: number): Satellite['orbit'] => ({
  regime, altKm, incDeg, raanDeg, ecc, anomalyDeg,
  periodMin: +(2 * Math.PI * Math.sqrt(Math.pow(6371 + altKm, 3) / 398600.4418) / 60).toFixed(1),
})

export function buildSatellites(): Satellite[] {
  return [
    mkSat('SVC-01', 'Atlas Servicer-1', 'servicer', 'Orbit Observers (own)', 'Servicing vehicle - LEO', orb('LEO', 560, 53, 40, 0.0002, 35), 'AG-MISSION'),
    mkSat('SVC-02', 'Atlas Servicer-2', 'servicer', 'Orbit Observers (own)', 'Servicing vehicle - SSO', orb('SSO', 700, 98.2, 120, 0.0004, 200), 'AG-MISSION', { PRP: 83 }),
    mkSat('SVC-03', 'Atlas Servicer-3', 'servicer', 'Orbit Observers (own)', 'Servicing tug - MEO/GEO', orb('MEO', 20200, 55, 210, 0.001, 310), 'AG-MISSION', {}, { status: 'Servicing' }),
    mkSat('CS-101', 'Helios Comm-1', 'customer', 'Helios Telecom', 'GEO communications', orb('GEO', 35786, 0.05, 0, 0.0002, 80), 'AG-HEALTH', { BAT: 74 }),
    mkSat('CS-102', 'Helios Comm-2', 'customer', 'Helios Telecom', 'GEO communications', orb('GEO', 35786, 0.04, 0, 0.0003, 142), 'AG-HEALTH', { ANT: 78 }),
    mkSat('CS-201', 'Aurora EO-1', 'customer', 'Aurora Earth Observation', 'Optical Earth observation', orb('SSO', 620, 97.9, 15, 0.0011, 12), 'AG-HEALTH'),
    mkSat('CS-202', 'Aurora EO-2', 'customer', 'Aurora Earth Observation', 'Optical Earth observation', orb('SSO', 620, 97.9, 75, 0.0009, 170), 'AG-HEALTH', { THM: 77 }),
    mkSat('CS-203', 'Aurora EO-3', 'customer', 'Aurora Earth Observation', 'SAR Earth observation', orb('SSO', 640, 98.0, 135, 0.0008, 250), 'AG-HEALTH', { 'RW-02': 92 }),
    mkSat('CS-301', 'Nordlicht Nav-1', 'customer', 'Nordlicht Navigation', 'Navigation (MEO)', orb('MEO', 20180, 56, 60, 0.0005, 300), 'AG-HEALTH', { 'RW-01': 55 }, { status: 'Servicing' }),
    mkSat('CS-302', 'Nordlicht Nav-2', 'customer', 'Nordlicht Navigation', 'Navigation (MEO)', orb('MEO', 20180, 56, 120, 0.0004, 10), 'AG-HEALTH'),
    mkSat('CS-401', 'Vesta Cast-1', 'customer', 'Vesta Broadcast', 'GEO broadcast', orb('GEO', 35786, 0.03, 0, 0.0001, 220), 'AG-HEALTH', { SA: 66 }),
    mkSat('CS-501', 'Meridian Wx-1', 'customer', 'Meridian Weather', 'Weather imaging (LEO)', orb('LEO', 830, 98.7, 90, 0.001, 66), 'AG-HEALTH', { OBC: 79 }),
    mkSat('CS-502', 'Meridian Wx-2', 'customer', 'Meridian Weather', 'Weather imaging (LEO)', orb('LEO', 830, 98.7, 270, 0.001, 302), 'AG-HEALTH', { PLD: 62 }),
  ]
}

export function buildAgents(): Agent[] {
  const cust = (o?: string) => buildSatellites().filter((s) => s.kind === 'customer' && (!o || s.operator === o)).map((s) => s.id)
  return [
    { id: 'AG-HEALTH', name: 'Health Monitoring Agent', role: 'Continuously scores subsystem health and detects telemetry anomalies', state: 'Monitoring', satIds: cust(), tasks: ['Baseline drift scan - all fleets', 'Trend watch: CS-401 SA output'] },
    { id: 'AG-FAULT', name: 'Fault Diagnosis Agent', role: 'Explains anomalies and ranks probable root causes', state: 'Idle', satIds: cust(), tasks: [] },
    { id: 'AG-MAINT', name: 'Maintenance Planning Agent', role: 'Turns diagnoses into maintenance proposals and work orders', state: 'Planning', satIds: cust(), tasks: ['Draft MC-1004 work order'] },
    { id: 'AG-MISSION', name: 'Mission Coordination Agent', role: 'Sequences servicing mission phases and assigns servicer assets', state: 'Analyzing', satIds: ['SVC-01', 'SVC-02', 'SVC-03', 'CS-301', 'CS-401'], tasks: ['Track MS-2001 inspection phase', 'Hold MS-2002 awaiting authorization'] },
    { id: 'AG-COMM', name: 'Communication Analysis Agent', role: 'Inspects servicer↔customer sessions for link quality and protocol errors', state: 'Monitoring', satIds: ['SVC-01', 'SVC-02', 'SVC-03', 'CS-301'], tasks: ['Monitor CX-9001 link margin'] },
    { id: 'AG-POLICY', name: 'Policy Compliance Agent', role: 'Evaluates every requested action against the customer service policy', state: 'Monitoring', satIds: cust(), tasks: [] },
  ]
}

export function buildPolicies(): Policy[] {
  return buildSatellites().filter((s) => s.kind === 'customer').map((s, i) => ({
    id: `POL-${s.id}`, satId: s.id, name: `${s.operator} - Servicing Policy`, version: 2 + (i % 3),
    versions: [
      { v: 1, date: '2025-09-10', author: 'Legal & Ops', note: 'Initial service agreement' },
      { v: 2, date: '2026-01-22', author: 'J. Moreau (customer)', note: 'Added emergency hold procedure' },
      ...(i % 3 >= 1 ? [{ v: 3, date: '2026-05-04', author: 'Orbit Observers Compliance', note: 'Tightened proximity-ops approval' }] : []),
      ...(i % 3 === 2 ? [{ v: 4, date: '2026-08-30', author: 'S. Okafor (customer)', note: 'Restricted operating windows' }] : []),
    ].slice(0, 2 + (i % 3)),
    diagnostics: ['Telemetry request', 'Health self-test', 'Visual inspection (proximity)', 'Thermal survey'],
    commCategories: ['Diagnostic telemetry', 'Authorization handshake', 'Status beacon', 'Servicing command (approved)'],
    windows: s.orbit.regime === 'GEO' ? 'Any time, 02:00-10:00 UTC preferred' : 'Ground-contact-free passes only, 00:00-12:00 UTC',
    procedures: ['Inspection', 'Component swap (modular)', 'Software patch', 'Recalibration'],
    escalationThreshold: 70,
    aiAllowed: ['Request telemetry', 'Run diagnostics', 'Draft work orders', 'Generate recommendations'],
    humanRequired: ['Mission initiation', 'Close-proximity operations', 'Component replacement', 'Configuration change', 'Hazardous command'],
    emergencyHold: 'Any operator or customer may issue HOLD; servicer retreats to 200 m keep-out.',
    customerAuth: true,
  }))
}

const now = () => Date.now()
const m = (min: number) => now() - min * 60000

export interface SeedState {
  satellites: Satellite[]; agents: Agent[]; policies: Policy[]; cases: MaintCase[]; approvals: Approval[]
  missions: Mission[]; sessions: CommSession[]; messages: CommMsg[]; evals: PolicyEval[]
  audit: AuditEvent[]; agentEvents: AgentEvent[]
}

const CHECK = (done: number) =>
  ['Verify customer authorization on file', 'Confirm servicer fuel & health', 'Plan approach trajectory (keep-out 200 m)', 'Establish encrypted link', 'Execute inspection / servicing procedure', 'Run post-service telemetry check', 'File mission report'].map((text, i) => ({ text, done: i < done }))

export function buildSeed(): SeedState {
  const satellites = buildSatellites()
  const agents = buildAgents()
  const policies = buildPolicies()

  const cases: MaintCase[] = [
    { id: 'MC-1000', satId: 'CS-501', componentId: 'CS-501/OBC', problem: 'Elevated single-event upsets (resolved)', severity: 'medium', evidence: ['SEU rate 7.2/day vs baseline 1/day'], recommendation: 'Watchdog firmware patch and memory scrub', urgency: 'Routine', window: 'Completed', resources: ['SVC-01'], stage: 7, missionId: 'MS-2000', createdAt: m(60 * 24 * 12), report: 'Patch applied, SEU rate returned to 1.2/day over 72h verification.' },
    { id: 'MC-1001', satId: 'CS-301', componentId: 'CS-301/RW-01', problem: 'Reaction wheel RW-01 bearing friction rising', severity: 'high', evidence: ['Vibration RMS 17.6 mg (warn 22)', 'Wheel current +18% over 14 days'], recommendation: 'Replace RW-01 using modular wheel cartridge', urgency: 'High - within 14 days', window: 'Next MEO servicing window', resources: ['SVC-03', 'RW cartridge type-B'], stage: 5, approvalId: 'AP-3000', missionId: 'MS-2001', createdAt: m(60 * 24 * 6) },
    { id: 'MC-1002', satId: 'CS-401', componentId: 'CS-401/SA', problem: 'Solar array output deficit increasing', severity: 'high', evidence: ['Array deficit 10.4% (warn 15%)', 'Drive motor torque ripple'], recommendation: 'Inspect solar array drive and re-lubricate / replace drive module', urgency: 'Elevated - 30 days', window: 'GEO servicing window W42', resources: ['SVC-03', 'SADA module'], stage: 3, approvalId: 'AP-3001', missionId: 'MS-2002', createdAt: m(60 * 24 * 3) },
    { id: 'MC-1004', satId: 'CS-502', componentId: 'CS-502/PLD', problem: 'Payload sensor noise floor drifting up', severity: 'medium', evidence: ['Noise 10.2 dB (warn 14)'], recommendation: 'Remote recalibration first; escalate to inspection if trend persists', urgency: 'Moderate - 45 days', window: 'TBD', resources: ['SVC-01'], stage: 1, createdAt: m(60 * 24) },
    { id: 'MC-1005', satId: 'CS-101', componentId: 'CS-101/BAT', problem: 'Battery cell imbalance growing', severity: 'medium', evidence: ['Cell spread 74 mV (warn 120)'], recommendation: 'Evaluate battery management reconfiguration (configuration change)', urgency: 'Moderate', window: 'TBD', resources: ['Remote command'], stage: 2, createdAt: m(60 * 20) },
  ]

  const approvals: Approval[] = [
    { id: 'AP-3000', operation: 'Replace reaction wheel RW-01 (CS-301)', kind: 'Component replacement', satId: 'CS-301', missionId: 'MS-2001', caseId: 'MC-1001', requester: 'Maintenance Planning Agent', justification: 'Bearing friction trend projected to cross warning threshold within ~3 weeks (simulated).', telemetry: ['Vibration RMS 17.6 mg', 'Wheel current +18%'], risk: 'High', policyId: 'POL-CS-301', consequences: 'Loss of 3-axis control margin if wheel fails before service.', mitigation: 'Use 200 m keep-out hold points and abort corridor.', createdAt: m(60 * 24 * 5), reviewer: 'Dr. A. Lindqvist', status: 'approved', notes: 'Reviewed trend data and abort corridor. Approved.', decidedAt: m(60 * 24 * 5 - 90), decidedBy: 'Human Approval Authority' },
    { id: 'AP-3001', operation: 'Inspect and service solar array drive (CS-401)', kind: 'Mission initiation', satId: 'CS-401', missionId: 'MS-2002', caseId: 'MC-1002', requester: 'Mission Coordination Agent', justification: 'Array deficit rising; inspection recommended within 30 days (simulated).', telemetry: ['Array deficit 10.4%', 'Torque ripple +22%'], risk: 'Elevated', policyId: 'POL-CS-401', consequences: 'Progressive power margin loss for broadcast payload.', mitigation: 'Inspect first; replace only if torque ripple confirmed.', createdAt: m(60 * 6), reviewer: 'Dr. A. Lindqvist', status: 'pending' },
    { id: 'AP-3002', operation: 'Reconfigure antenna beam pointing (CS-102)', kind: 'Configuration change', satId: 'CS-102', requester: 'Health Monitoring Agent', justification: 'Marginal link BER; re-pointing could improve margin.', telemetry: ['BER 17 ppm'], risk: 'Elevated', policyId: 'POL-CS-102', consequences: 'Possible coverage loss on edge of beam.', mitigation: 'Revert command staged.', createdAt: m(60 * 24 * 2), reviewer: 'M. Rossi', status: 'rejected', notes: 'Rejected: coverage commitments for Q4 not yet reviewed with customer.', decidedAt: m(60 * 24 * 2 - 40), decidedBy: 'Human Approval Authority' },
  ]

  const missions: Mission[] = [
    { id: 'MS-2000', title: 'OBC watchdog patch - Meridian Wx-1', satId: 'CS-501', servicerId: 'SVC-01', caseId: 'MC-1000', stage: 11, risk: 'Low', gates: {}, checklist: CHECK(7), events: [{ ts: m(60 * 24 * 10), text: 'Mission completed, report filed' }], status: 'Completed', createdAt: m(60 * 24 * 12) },
    { id: 'MS-2001', title: 'RW-01 replacement - Nordlicht Nav-1', satId: 'CS-301', servicerId: 'SVC-03', caseId: 'MC-1001', stage: 8, risk: 'High', gates: { 4: 'AP-3000' }, checklist: CHECK(4), events: [{ ts: m(60 * 24 * 5), text: 'Authorization recorded (AP-3000)' }, { ts: m(60 * 24 * 2), text: 'Rendezvous complete, holding at 25 m' }, { ts: m(120), text: 'Servicing in progress: wheel cartridge removal' }], status: 'Active', createdAt: m(60 * 24 * 6) },
    { id: 'MS-2002', title: 'Solar array drive service - Vesta Cast-1', satId: 'CS-401', servicerId: 'SVC-03', caseId: 'MC-1002', stage: 4, risk: 'Elevated', gates: { 4: 'AP-3001' }, checklist: CHECK(1), events: [{ ts: m(60 * 6), text: 'Awaiting human authorization (AP-3001)' }], status: 'Blocked', createdAt: m(60 * 24 * 3) },
  ]

  const sessions: CommSession[] = [
    { id: 'CX-9001', servicerId: 'SVC-03', satId: 'CS-301', missionId: 'MS-2001', status: 'Active', start: m(150), quality: 91, latencyMs: 142, authorized: 'authorized' },
    { id: 'CX-9000', servicerId: 'SVC-01', satId: 'CS-501', missionId: 'MS-2000', status: 'Closed', start: m(60 * 24 * 10 + 90), end: m(60 * 24 * 10 + 20), quality: 96, latencyMs: 38, authorized: 'authorized' },
    { id: 'CX-8999', servicerId: 'SVC-01', satId: 'CS-502', status: 'Failed', start: m(60 * 5), end: m(60 * 5 - 1), quality: 0, latencyMs: 0, authorized: 'denied' },
  ]
  const mk = (id: string, sid: string, min: number, dir: CommMsg['dir'], category: string, text: string, state: CommMsg['state'] = 'ack', policyId?: string): CommMsg => ({ id, sessionId: sid, ts: m(min), dir, category, text, state, policyId })
  const messages: CommMsg[] = [
    mk('MSG-1', 'CX-9001', 150, 'SYS', 'Session', 'Communication session requested', 'ack', 'POL-CS-301'),
    mk('MSG-2', 'CX-9001', 149.9, 'RX', 'Authorization handshake', 'Customer satellite authorization confirmed', 'ack', 'POL-CS-301'),
    mk('MSG-3', 'CX-9001', 149.8, 'TX', 'Diagnostic telemetry', 'Diagnostic telemetry requested: ADCS bus'),
    mk('MSG-4', 'CX-9001', 149.7, 'RX', 'Diagnostic telemetry', 'Telemetry response received (RW-01 current 1.18 A)'),
    mk('MSG-5', 'CX-9001', 140, 'TX', 'Servicing command (approved)', 'Wheel spin-down command (approved AP-3000)', 'ack', 'POL-CS-301'),
    mk('MSG-6', 'CX-9001', 139.9, 'RX', 'Servicing command (approved)', 'Spin-down acknowledged: 0 rpm', 'ack'),
    mk('MSG-7', 'CX-9001', 60, 'TX', 'Status beacon', 'Heartbeat', 'ack'),
    mk('MSG-8', 'CX-9001', 59.9, 'RX', 'Status beacon', 'Heartbeat response delayed (checksum retry)', 'error'),
    mk('MSG-9', 'CX-9000', 60 * 24 * 10 + 90, 'SYS', 'Session', 'Communication session requested', 'ack', 'POL-CS-501'),
    mk('MSG-10', 'CX-9000', 60 * 24 * 10 + 80, 'TX', 'Servicing command (approved)', 'Apply watchdog patch v4.3', 'ack'),
    mk('MSG-11', 'CX-8999', 300, 'SYS', 'Session', 'Session requested outside permitted operating window', 'error', 'POL-CS-502'),
  ]

  const ev = (id: string, min: number, satId: string, actor: string, action: string, policyId: string, decision: PolicyEval['decision'], reason: string, ref?: string): PolicyEval => ({
    id, ts: m(min), satId, actor, action, policyId, version: policies.find((p) => p.id === policyId)!.version, decision, reason, ref,
  })
  const evals: PolicyEval[] = [
    ev('EV-5001', 60 * 24 * 6, 'CS-301', 'Health Monitoring Agent', 'Request diagnostic telemetry', 'POL-CS-301', 'allowed', 'Diagnostics are on AI-permitted list'),
    ev('EV-5002', 60 * 24 * 5.5, 'CS-301', 'Maintenance Planning Agent', 'Replace reaction wheel RW-01', 'POL-CS-301', 'approval required', 'Component replacement requires human approval', 'MC-1001'),
    ev('EV-5003', 300, 'CS-502', 'Mission Coordination Agent', 'Open comm session', 'POL-CS-502', 'denied', 'Outside permitted operating window', 'CX-8999'),
    ev('EV-5004', 60 * 6, 'CS-401', 'Mission Coordination Agent', 'Initiate servicing mission', 'POL-CS-401', 'approval required', 'Mission initiation requires human approval', 'MS-2002'),
    ev('EV-5005', 60 * 24 * 2, 'CS-102', 'Health Monitoring Agent', 'Reconfigure antenna beam pointing', 'POL-CS-102', 'approval required', 'Configuration change requires human approval', 'AP-3002'),
  ]

  const agentEvents: AgentEvent[] = [
    { id: 'AE-1', ts: m(60 * 6), agentId: 'AG-HEALTH', kind: 'observation', satId: 'CS-401', text: 'Solar array output deficit at 10.4%, trending upward', why: 'Linear fit of last 48 samples projects crossing 15% in ~30 days (simulated).' },
    { id: 'AE-2', ts: m(60 * 6 - 3), agentId: 'AG-MISSION', kind: 'escalation', satId: 'CS-401', text: 'Requested human authorization for MS-2002', needsApproval: true, ref: 'AP-3001', why: 'Mission initiation is on the human-required list of POL-CS-401.' },
    { id: 'AE-3', ts: m(120), agentId: 'AG-MISSION', kind: 'task', satId: 'CS-301', text: 'MS-2001 inspection and servicing phase underway', ref: 'MS-2001' },
    { id: 'AE-4', ts: m(59.8), agentId: 'AG-COMM', kind: 'observation', satId: 'CS-301', text: 'Checksum retry on heartbeat; link quality still 91%', why: 'Single transient error, below escalation threshold.' },
    { id: 'AE-5', ts: m(300), agentId: 'AG-POLICY', kind: 'policy-check', satId: 'CS-502', text: 'Denied comm session outside operating window', ref: 'EV-5003' },
    { id: 'AE-6', ts: m(60 * 24), agentId: 'AG-FAULT', kind: 'result', satId: 'CS-502', text: 'Payload noise drift consistent with detector aging (confidence 0.62, simulated)', why: 'Pattern matches slow-drift signature; no step changes seen.' },
  ]

  const audit: AuditEvent[] = ([
    ...evals.map<AuditEvent>((e) => ({ id: `AU-${e.id}`, ts: e.ts, category: 'policy', severity: e.decision === 'denied' ? 'medium' : 'info', satId: e.satId, actor: e.actor, summary: `${e.action} → ${e.decision}`, detail: e.reason, ref: e.id })),
    ...approvals.filter((a) => a.decidedAt).map<AuditEvent>((a) => ({ id: `AU-${a.id}`, ts: a.decidedAt!, category: 'approval', severity: a.status === 'rejected' ? 'medium' : 'info', satId: a.satId, actor: a.decidedBy!, summary: `${a.operation} ${a.status}`, detail: a.notes, ref: a.id })),
    ...messages.filter((x) => x.state === 'error').map<AuditEvent>((x) => ({ id: `AU-${x.id}`, ts: x.ts, category: 'comms', severity: 'medium', actor: 'Communication Analysis Agent', summary: x.text, ref: x.sessionId })),
    { id: 'AU-M1', ts: m(60 * 24 * 10), category: 'mission', severity: 'info', satId: 'CS-501', actor: 'Mission Coordination Agent', summary: 'MS-2000 completed and report filed', ref: 'MS-2000' },
    { id: 'AU-M2', ts: m(120), category: 'mission', severity: 'info', satId: 'CS-301', actor: 'Mission Coordination Agent', summary: 'MS-2001 entered servicing phase', ref: 'MS-2001' },
  ] as AuditEvent[]).sort((a, b) => b.ts - a.ts)

  return { satellites, agents, policies, cases, approvals, missions, sessions, messages, evals, audit, agentEvents }
}
