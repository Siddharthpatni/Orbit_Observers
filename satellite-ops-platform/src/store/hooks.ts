import { useMemo } from 'react'
import { useStore } from './useStore'
import { customerOperator, isCustomer } from '@/lib/access'

/** Role-scoped view of the data: customer users only see their own assets. */
export function useScoped() {
  const s = useStore()
  return useMemo(() => {
    if (!isCustomer(s.role)) return { ...s, scoped: false }
    const sats = s.satellites.filter((x) => x.operator === customerOperator)
    const ids = new Set(sats.map((x) => x.id))
    const missions = s.missions.filter((m) => ids.has(m.satId))
    const mIds = new Set(missions.map((m) => m.id))
    const sessions = s.sessions.filter((c) => ids.has(c.satId))
    const sIds = new Set(sessions.map((c) => c.id))
    return {
      ...s,
      scoped: true,
      satellites: [...sats, ...s.satellites.filter((x) => x.kind === 'servicer' && missions.some((m) => m.servicerId === x.id))],
      tasks: s.tasks.filter((t) => ids.has(t.satId)),
      cases: s.cases.filter((c) => ids.has(c.satId)),
      approvals: s.approvals.filter((a) => ids.has(a.satId)),
      missions,
      sessions,
      messages: s.messages.filter((m) => sIds.has(m.sessionId)),
      evals: s.evals.filter((e) => ids.has(e.satId)),
      audit: s.audit.filter((a) => a.satId && ids.has(a.satId)),
      agentEvents: s.agentEvents.filter((a) => a.satId && ids.has(a.satId)),
      policies: s.policies.filter((p) => ids.has(p.satId)),
      _mIds: mIds,
    }
  }, [s])
}
