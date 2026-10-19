import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Play, ChevronDown, ChevronUp } from 'lucide-react'
import { useStore, DEMO_IDS } from '@/store/useStore'
import { api } from '@/services/api'

/** Guided runner for the reaction-wheel scenario. Each step calls the same actions the pages use. */
export function DemoGuide() {
  const [open, setOpen] = useState(true)
  const nav = useNavigate()
  const cases = useStore((s) => s.cases)
  const approvals = useStore((s) => s.approvals)
  const missions = useStore((s) => s.missions)
  const comp = useStore((s) => s.satellites.find((x) => x.id === DEMO_IDS.sat)?.components.find((c) => c.id === DEMO_IDS.comp))
  const mc = cases.find((c) => c.id === DEMO_IDS.case)
  const ap = approvals.find((a) => a.id === DEMO_IDS.approval)
  const prox = approvals.find((a) => a.id === DEMO_IDS.prox)
  const ms = missions.find((m) => m.id === DEMO_IDS.mission)

  let label = '', hint = '', run: () => void = () => {}, done = false
  if (!comp?.issue && !mc) { label = '1. Inject RW-02 vibration anomaly'; hint = 'Aurora EO-3 telemetry starts drifting.'; run = () => { api.injectAnomaly(); nav('/monitoring?sat=CS-203') } }
  else if (!mc) { label = '2. AI diagnoses & recommends'; hint = 'Fault Diagnosis + Maintenance Planning agents.'; run = () => { api.diagnoseAnomaly(); nav('/maintenance') } }
  else if (!ap) { label = '3. Run policy evaluation'; hint = 'Policy engine decides if approval is required.'; run = () => { api.evaluateDemoPolicy(); nav('/approvals') } }
  else if (ap.status === 'pending' || ap.status === 'hold' || ap.status === 'info-requested') { label = '4. Review & approve AP-3100'; hint = 'Switch to "Human Approval Authority" role to decide.'; run = () => nav('/approvals') }
  else if (ap.status === 'rejected') { label = 'Request rejected'; hint = 'Reset the demo to try again.'; done = true }
  else if (ms && ms.stage < 11) {
    const gateOpen = !ms.gates[ms.stage] || approvals.find((a) => a.id === ms.gates[ms.stage])?.status === 'approved'
    if (!gateOpen) { label = `5. Approve ${prox?.id ?? 'proximity ops'}`; hint = 'Mission is blocked at an approval gate.'; run = () => nav('/approvals') }
    else { label = `5. Advance mission → ${ms.stage + 1 < 11 ? ['','','','','Authorization','Planning','Rendezvous','Comms','Servicing','Verification','Reporting'][ms.stage + 1] : 'Complete'}`; hint = `Phase ${ms.stage + 1}/11`; run = () => { api.advanceMission(ms.id); nav(`/missions?m=${ms.id}`) } }
  } else { label = 'Scenario complete - view summary'; hint = 'Mission summary and updated health available.'; run = () => nav(`/missions?m=${DEMO_IDS.mission}`); done = true }

  return (
    <div className="fixed bottom-4 right-4 z-30 w-72 card shadow-2xl border-accent/30">
      <button className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold text-accent" onClick={() => setOpen(!open)}>
        <span className="flex items-center gap-1.5"><Play size={12} />Guided demo: reaction wheel scenario</span>{open ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
      </button>
      {open && (
        <div className="px-3 pb-3">
          <p className="text-xs text-mute mb-2">{hint}</p>
          <button className={done ? 'btn w-full' : 'btn btn-primary w-full justify-center'} onClick={run}>{label}</button>
        </div>
      )}
    </div>
  )
}
