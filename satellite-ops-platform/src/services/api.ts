/**
 * Mock service boundary. UI code reads data through hooks here and mutates via `api`.
 * Today these are backed by the local Zustand store; swapping in a real backend means
 * reimplementing this file (fetch/WebSocket) without touching pages or components.
 */
import { useStore } from '@/store/useStore'

export const api = {
  injectAnomaly: () => useStore.getState().injectAnomaly(),
  diagnoseAnomaly: () => useStore.getState().diagnoseAnomaly(),
  evaluateDemoPolicy: () => useStore.getState().evaluateDemoPolicy(),
  decideApproval: (...a: Parameters<ReturnType<typeof useStore.getState>['decideApproval']>) => useStore.getState().decideApproval(...a),
  advanceMission: (id: string) => useStore.getState().advanceMission(id),
  createMaintRequest: (s: string, c: string) => useStore.getState().createMaintRequest(s, c),
  createWorkOrder: (id: string) => useStore.getState().createWorkOrder(id),
  setCaseStage: (id: string, s: number) => useStore.getState().setCaseStage(id, s),
  savePolicy: (...a: Parameters<ReturnType<typeof useStore.getState>['savePolicy']>) => useStore.getState().savePolicy(...a),
  setAutonomy: (on: boolean) => useStore.getState().setAutonomy(on),
  reset: () => useStore.getState().reset(),
}
