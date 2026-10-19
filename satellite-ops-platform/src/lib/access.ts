import type { Role } from './types'
import { CUSTOMER_DEMO_OPERATOR } from '@/data/seed'

export const ROLES: Record<Role, { label: string; nav: string[] }> = {
  operator: { label: 'Company Mission Operator', nav: ['dashboard', 'fleet', 'monitoring', 'agents', 'comms', 'downlink', 'policies', 'approvals', 'maintenance', 'missions', 'audit'] },
  engineer: { label: 'Satellite Maintenance Engineer', nav: ['dashboard', 'fleet', 'monitoring', 'agents', 'comms', 'downlink', 'maintenance', 'missions', 'audit'] },
  aisup: { label: 'AI Operations Supervisor', nav: ['dashboard', 'fleet', 'monitoring', 'agents', 'comms', 'downlink', 'policies', 'approvals', 'audit'] },
  approver: { label: 'Human Approval Authority', nav: ['dashboard', 'approvals', 'maintenance', 'missions', 'policies', 'audit'] },
  customer: { label: 'Customer Satellite Operator', nav: ['dashboard', 'fleet', 'monitoring', 'downlink', 'maintenance', 'missions', 'policies', 'audit'] },
  admin: { label: 'System Administrator', nav: ['dashboard', 'fleet', 'monitoring', 'agents', 'comms', 'downlink', 'policies', 'approvals', 'maintenance', 'missions', 'audit'] },
}
export const canDecide = (r: Role) => r === 'approver' || r === 'admin'
export const canEditPolicy = (r: Role) => r === 'operator' || r === 'admin' || r === 'aisup'
export const canOperate = (r: Role) => r === 'operator' || r === 'engineer' || r === 'admin'
export const isCustomer = (r: Role) => r === 'customer'
export const customerOperator = CUSTOMER_DEMO_OPERATOR
