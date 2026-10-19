export type Role = 'operator' | 'engineer' | 'aisup' | 'approver' | 'customer' | 'admin'
export type Severity = 'info' | 'low' | 'medium' | 'high' | 'critical'
export type Risk = 'Low' | 'Elevated' | 'High' | 'Critical'

export interface Component {
  id: string
  satId: string
  name: string
  subsystem: string
  unit: string
  metric: string
  health: number
  warnAt: number // telemetry warning threshold (metric units)
  series: number[]
  risk: Risk
  rulDays?: number
  issue?: string
  recommendation?: string
}

export interface Satellite {
  id: string
  name: string
  kind: 'customer' | 'servicer'
  operator: string
  role: string
  orbit: { regime: string; altKm: number; incDeg: number; raanDeg: number; ecc: number; periodMin: number; anomalyDeg: number }
  status: 'Nominal' | 'Attention' | 'Servicing' | 'Hold' | 'Standby'
  condition: string
  agentId: string
  policyId?: string
  components: Component[]
  history: { date: string; text: string }[]
}

export interface Agent {
  id: string
  name: string
  role: string
  state: 'Monitoring' | 'Analyzing' | 'Idle' | 'Awaiting human' | 'Planning'
  satIds: string[]
  tasks: string[]
}

export interface AgentEvent {
  id: string
  ts: number
  agentId: string
  kind: 'observation' | 'recommendation' | 'policy-check' | 'escalation' | 'task' | 'result'
  satId?: string
  text: string
  why?: string
  needsApproval?: boolean
  ref?: string
}

export const LIFECYCLE = ['Detected', 'Diagnosed', 'Proposed', 'Pending Approval', 'Scheduled', 'In Service', 'Verified', 'Completed'] as const

export interface MaintCase {
  id: string
  satId: string
  componentId: string
  problem: string
  severity: Severity
  evidence: string[]
  recommendation: string
  urgency: string
  window: string
  resources: string[]
  stage: number // index into LIFECYCLE
  approvalId?: string
  missionId?: string
  workOrder?: string
  createdAt: number
  report?: string
}

export interface Approval {
  id: string
  operation: string
  kind: 'Mission initiation' | 'Close-proximity operations' | 'Component replacement' | 'Configuration change' | 'Hazardous command'
  satId: string
  missionId?: string
  caseId?: string
  requester: string
  justification: string
  telemetry: string[]
  risk: Risk
  policyId: string
  consequences: string
  mitigation: string
  createdAt: number
  reviewer: string
  status: 'pending' | 'approved' | 'rejected' | 'hold' | 'info-requested'
  notes?: string
  decidedAt?: number
  decidedBy?: string
}

export const MISSION_STAGES = [
  'Customer service request', 'Satellite health assessment', 'AI diagnosis', 'Service proposal',
  'Human/customer authorization', 'Mission planning', 'Rendezvous & proximity ops', 'Communication establishment',
  'Inspection & servicing', 'Post-service verification', 'Completion & reporting',
] as const

export interface Mission {
  id: string
  title: string
  satId: string
  servicerId: string
  caseId?: string
  stage: number // index of the CURRENT stage; stage === 11 means complete
  risk: Risk
  gates: Record<number, string> // stage index -> approval id required to leave that stage
  checklist: { text: string; done: boolean }[]
  events: { ts: number; text: string }[]
  status: 'Active' | 'Blocked' | 'Completed' | 'Scheduled'
  createdAt: number
}

export interface CommSession {
  id: string
  servicerId: string
  satId: string
  missionId?: string
  status: 'Active' | 'Closed' | 'Failed' | 'Requested'
  start: number
  end?: number
  quality: number // 0-100 simulated
  latencyMs: number
  authorized: 'authorized' | 'denied' | 'pending'
}

export interface CommMsg {
  id: string
  sessionId: string
  ts: number
  dir: 'TX' | 'RX' | 'SYS'
  category: string
  text: string
  state: 'ack' | 'error' | 'pending'
  policyId?: string
}

export interface PolicyVersion { v: number; date: string; author: string; note: string }
export interface Policy {
  id: string
  satId: string
  name: string
  version: number
  versions: PolicyVersion[]
  diagnostics: string[]
  commCategories: string[]
  windows: string
  procedures: string[]
  escalationThreshold: number // health % below which escalate
  aiAllowed: string[]
  humanRequired: string[]
  emergencyHold: string
  customerAuth: boolean
}

export interface PolicyEval {
  id: string
  ts: number
  satId: string
  actor: string
  action: string
  policyId: string
  version: number
  decision: 'allowed' | 'denied' | 'approval required'
  reason: string
  ref?: string
}

export interface AuditEvent {
  id: string
  ts: number
  category: 'telemetry' | 'agent' | 'comms' | 'policy' | 'approval' | 'ticket' | 'mission' | 'repair' | 'system'
  severity: Severity
  satId?: string
  actor: string
  summary: string
  detail?: string
  ref?: string
}

export interface Notification { id: string; ts: number; text: string; severity: Severity; link?: string; read: boolean }

export interface DemoState {
  step: number // 0..N progress of scripted scenario
}

export interface AgentTask {
  id: string
  agentId: string // owning agent (primary)
  title: string
  satId: string
  componentId: string
  caseId: string
  stage: 'detected' | 'proposed' | 'awaiting-approval' | 'mission' | 'done'
  status: 'running' | 'waiting-human' | 'done' | 'failed'
  checkpoints: { text: string; done: boolean }[]
  trajectory: { ts: number; agentId: string; kind: 'thought' | 'tool' | 'observation' | 'escalation'; text: string }[]
  createdAt: number
}

export interface AutonomyState { enabled: boolean; tick: number; scenarioStarted: boolean; generated: number; lastGenTick: number }
