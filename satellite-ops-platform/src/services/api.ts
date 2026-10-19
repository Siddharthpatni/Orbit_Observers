/**
 * Mock service boundary. UI code reads data through hooks here and mutates via `api`.
 * Today these are backed by the local Zustand store; swapping in a real backend means
 * reimplementing this file (fetch/WebSocket) without touching pages or components.
 */
import { useStore } from '@/store/useStore'

const ACTOR: Record<string, string> = { operator: 'Operator', engineer: 'Engineer', aisup: 'AI supervisor', approver: 'Approval authority', customer: 'Customer', admin: 'Admin' }

/**
 * Ask the server to apply/validate a rule-bound action first (platform_api/domain.py). If no backend is configured or it
 * is unreachable, the local store enforces the same rules (demo mode). A server rejection (4xx) blocks the action.
 */
async function serverGuard(path: string, body: Record<string, unknown>): Promise<{ ok: boolean; reason?: string }> {
  if (!API_BASE) return { ok: true }
  const role = useStore.getState().role
  try {
    await pushNow()
    const r = await fetch(`${API_BASE}${path}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...body, role, actor: ACTOR[role] ?? role }),
    })
    if (r.ok) return { ok: true }
    if (r.status >= 400 && r.status < 500) return { ok: false, reason: `Server: ${(await r.json().catch(() => ({}))).detail ?? r.statusText}` }
    return { ok: true } // server error: fall back to local rules
  } catch { return { ok: true } } // unreachable: demo mode
}

export const api = {
  injectAnomaly: () => useStore.getState().injectAnomaly(),
  diagnoseAnomaly: () => useStore.getState().diagnoseAnomaly(),
  evaluateDemoPolicy: () => useStore.getState().evaluateDemoPolicy(),
  decideApproval: (id: string, decision: 'approved' | 'rejected' | 'hold' | 'info-requested', notes: string) =>
    serverGuard(`/approvals/${id}/decide`, { decision, notes }).then((g) => { if (g.ok) useStore.getState().decideApproval(id, decision, notes); return g }),
  advanceMission: (id: string): Promise<{ ok: boolean; reason?: string }> =>
    serverGuard(`/missions/${id}/advance`, {}).then((g) => (g.ok ? useStore.getState().advanceMission(id) : g)),
  createMaintRequest: (s: string, c: string) => useStore.getState().createMaintRequest(s, c),
  createWorkOrder: (id: string) => useStore.getState().createWorkOrder(id),
  setCaseStage: (id: string, s: number) => useStore.getState().setCaseStage(id, s),
  savePolicy: (...a: Parameters<ReturnType<typeof useStore.getState>['savePolicy']>) => useStore.getState().savePolicy(...a),
  setAutonomy: (on: boolean) => useStore.getState().setAutonomy(on),
  reset: () => useStore.getState().reset(),
}

// --- Feasibility (RPO Monte Carlo evidence) -------------------------------------------------
import feasibilityData from '@/data/feasibility.json'

export interface FeasCell {
  tier: string; tumble_deg_s: number; n_runs: number; n_pass: number; n_abort: number; n_unsafe: number; n_timeout: number
  p_terminal_pass: number; p_terminal_pass_ci95_low: number; p_terminal_pass_ci95_high: number; p_abort: number; p_unsafe: number
  mean_delta_v_mps: number | null; mean_time_to_capture_s: number | null
}
export interface Feasibility {
  cell: FeasCell; withinRange: boolean; notes: string[]; source: 'campaign file' | 'backend'
  provenance: { model_version: string; config_hash: string; master_seed: number; paired_seeds_per_cell: number }; caveat: string
}

/** Offline lookup in the bundled campaign table (same logic as platform_api/feasibility.py). */
export function lookupFeasibility(tier: string, tumble: number): Feasibility | null {
  const cells = (feasibilityData.cells as FeasCell[]).filter((c) => c.tier === tier)
  if (!cells.length) return null
  const grid = cells.map((c) => c.tumble_deg_s).sort((a, b) => a - b)
  const cell = cells.reduce((b, c) => (Math.abs(c.tumble_deg_s - tumble) < Math.abs(b.tumble_deg_s - tumble) ? c : b))
  const notes: string[] = []
  const within = tumble >= grid[0] && tumble <= grid[grid.length - 1]
  if (tumble > grid[grid.length - 1]) notes.push(`${tumble} deg/s is above the tested range (max ${grid[grid.length - 1]}); no evidence`)
  else if (cell.tumble_deg_s !== tumble) notes.push(`Nearest tested grid point ${cell.tumble_deg_s} deg/s used (no interpolation)`)
  if (tier === 'C3_ios_mode') notes.push('C3 assumes a 95% initial-spin reduction; IOS handover is not coupled to this result')
  const d = feasibilityData
  return { cell, withinRange: within, notes, source: 'campaign file', caveat: d.caveat,
    provenance: { model_version: d.model_version, config_hash: d.config_hash, master_seed: d.master_seed, paired_seeds_per_cell: d.paired_seeds_per_cell } }
}

/** Uses the backend when VITE_API_URL is set and reachable; otherwise the bundled table. */
export async function fetchFeasibility(tier: string, tumble: number): Promise<Feasibility | null> {
  const base = API_BASE
  if (base) {
    try {
      const r = await fetch(`${base}/feasibility?tier=${encodeURIComponent(tier)}&tumble_deg_s=${tumble}`)
      if (r.ok) {
        const j = await r.json()
        return { cell: j.cell, withinRange: j.within_tested_range, notes: j.notes, source: 'backend', provenance: j.provenance, caveat: j.caveat }
      }
    } catch { /* fall through to offline table */ }
  }
  return lookupFeasibility(tier, tumble)
}

// --- Backend mirror ---------------------------------------------------------------------------
/**
 * When VITE_API_URL is set, mirror cases/approvals/missions/satellite tiers to the server (PUT /sync) and
 * forward every new audit event to the hash-chained audit log (POST /audit). The browser store stays the
 * interactive source in demo mode; the server re-enforces the rules (see platform_api/domain.py).
 * Failures are ignored so the demo keeps working offline.
 */
const API_BASE = import.meta.env.VITE_API_URL as string | undefined
const seenAudit = new Set<string>()

async function pushNow() {
  const base = API_BASE
  if (!base) return
  {
    const s = useStore.getState()
    try {
      await fetch(`${base}/sync`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          satellites: s.satellites.map((x) => ({ id: x.id, serviceTier: x.serviceTier, estTumbleDegS: x.estTumbleDegS })),
          cases: s.cases, approvals: s.approvals, missions: s.missions,
        }),
      })
      for (const e of [...s.audit].reverse()) {
        if (seenAudit.has(e.id)) continue
        seenAudit.add(e.id)
        await fetch(`${base}/audit`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ category: e.category, actor: e.actor, summary: e.summary, detail: { id: e.id, satId: e.satId, ref: e.ref, severity: e.severity, note: e.detail } }),
        })
      }
    } catch { /* offline: ignore */ }
  }
}

export function startBackendMirror(): (() => void) | undefined {
  if (!API_BASE) return undefined
  let timer: ReturnType<typeof setTimeout> | undefined
  const push = pushNow
  const unsub = useStore.subscribe(() => { clearTimeout(timer); timer = setTimeout(push, 800) })
  timer = setTimeout(push, 800)
  return () => { unsub(); clearTimeout(timer) }
}
