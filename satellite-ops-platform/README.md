# Orbit Observers - Satellite Servicing & Operations Platform (Frontend Demo)

Frontend-only simulation of an AI-assisted satellite monitoring and servicing platform.
**All data is simulated.** No backend, real AI, authentication, telemetry, or spacecraft control exists.

## Run
```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # typecheck + production build
```

## Demo walkthrough
Use the **Guided demo** card (bottom-right) - each button runs the same actions the pages use:
1. Inject RW-02 vibration anomaly on Aurora EO-3 → warning + notification
2. AI diagnosis → maintenance case MC-1100 (Detected → Proposed)
3. Policy evaluation → "approval required" → AP-3100 pending
4. Switch role to **Human Approval Authority**, review, approve (notes required)
5. Mission MS-2100 is scheduled; AP-3101 (close-proximity ops) gates rendezvous - approve it too
6. Advance the mission through comms, servicing, verification, completion; RW-02 health returns to 97%

"Reset demo" restores the seeded state. State persists in `localStorage`.

## Autonomous agents
The agent runtime starts with the app (`App.tsx` tick every 2.5 s, `tick` in the store) and keeps running on any page:
- Health agent streams telemetry and opens a **task** for any degraded component with no open case.
- Task = checkpoints (scored, like TheAgentCompany) + a step-by-step trajectory (thought / tool / observation / escalation), shown on Agents > Autonomous task board.
- Fault, Maintenance, Policy and Mission agents then diagnose, file the case, evaluate policy, and request approval without any clicks.
- Agents **never approve** high-risk actions: they pause (`waiting-human`) at approval gates and resume the moment a human decides. A rejection makes them stand down.
- After approval the Mission agent advances phases on its own (rendezvous needs its own approval).
- The scripted RW-02 scenario fires automatically ~7 s after load; a labelled simulated fault generator adds up to 3 further faults. Pause/resume from the top bar or the Agents page.
Inspired by TheAgentCompany's task/checkpoint/trajectory model; there is no LLM or Docker environment, all behavior is deterministic simulation.

## Structure
```
src/lib/        types, role access rules, utilities
src/data/       seeded dataset (13 satellites, 6 agents, policies, missions, comms…)
src/store/      Zustand store (all cross-module workflow logic) + role-scoped hooks
src/services/   api.ts - mock service boundary; replace to integrate a real backend
src/components/ ui primitives, layout shell, orbit schematic
src/pages/      Dashboard, Fleet, Monitoring, Agents, Comms, Policies, Approvals, Maintenance, Missions, Audit
```

## Limitations / deviations
- UI primitives are hand-written shadcn-style components (no shadcn CLI install); no React Three Fiber - the orbit view is an illustrative 2D SVG, not a propagated orbit.
- Predictions, RUL, confidence values and telemetry are fabricated demo data, labeled as such.
- Role switching is a UI simulation, not security. Audit records are append-only by convention; local storage is not tamper-proof.
- Policy builder edits a subset of fields (threshold, windows, customer auth, human-required actions) and versions each save.
