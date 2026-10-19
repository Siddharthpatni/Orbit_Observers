import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Bell, ChevronLeft, ChevronRight, LayoutDashboard, Satellite, Activity, Bot, Radio, ScrollText, ShieldCheck, Wrench, Rocket, FileSearch, RotateCcw, Circle } from 'lucide-react'
import { useStore } from '@/store/useStore'
import { useScoped } from '@/store/hooks'
import { ROLES } from '@/lib/access'
import type { Role } from '@/lib/types'
import { cn, ago } from '@/lib/util'
import { api } from '@/services/api'
import { Modal, DemoTag, Skeleton } from '@/components/ui'
import { DemoGuide } from './DemoGuide'

const NAV = [
  { key: 'dashboard', to: '/', label: 'Mission Control', icon: LayoutDashboard },
  { key: 'fleet', to: '/fleet', label: 'Fleet', icon: Satellite },
  { key: 'monitoring', to: '/monitoring', label: 'AI Health Monitoring', icon: Activity },
  { key: 'agents', to: '/agents', label: 'Agent Operations', icon: Bot },
  { key: 'comms', to: '/comms', label: 'Communications', icon: Radio },
  { key: 'policies', to: '/policies', label: 'Policy & Compliance', icon: ScrollText },
  { key: 'approvals', to: '/approvals', label: 'Approvals', icon: ShieldCheck },
  { key: 'maintenance', to: '/maintenance', label: 'Maintenance', icon: Wrench },
  { key: 'missions', to: '/missions', label: 'Missions', icon: Rocket },
  { key: 'audit', to: '/audit', label: 'Audit & Reports', icon: FileSearch },
]

export function Layout() {
  const [collapsed, setCollapsed] = useState(() => typeof window !== 'undefined' && window.innerWidth < 1100)
  const loc = useLocation()
  const [loading, setLoading] = useState(false)
  useEffect(() => {
    setLoading(true)
    const t = setTimeout(() => setLoading(false), 220)
    return () => clearTimeout(t)
  }, [loc.pathname])
  useEffect(() => {
    const on = () => window.innerWidth < 1000 && setCollapsed(true)
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
  }, [])
  const [bell, setBell] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)
  const role = useStore((s) => s.role)
  const setRole = useStore((s) => s.setRole)
  const notes = useStore((s) => s.notifications)
  const markAll = useStore((s) => s.markAllRead)
  const auto = useStore((s) => s.autonomy.enabled)
  const waiting = useStore((s) => s.tasks.filter((t) => t.status === 'waiting-human').length)
  const d = useScoped()
  const nav = useNavigate()
  const unread = notes.filter((n) => !n.read).length
  const pending = d.approvals.filter((a) => a.status === 'pending').length
  const active = d.missions.filter((m) => m.status === 'Active').length
  const crit = d.satellites.filter((s) => s.components.some((c) => c.health < 60)).length

  return (
    <div className="flex h-full">
      <aside className={cn('shrink-0 bg-panel border-r border-line flex flex-col transition-all', collapsed ? 'w-14' : 'w-56')} aria-label="Primary">
        <div className="h-14 flex items-center px-3 border-b border-line gap-2">
          <div className="w-7 h-7 rounded grid place-items-center text-white text-xs font-bold bg-gradient-to-r from-brand to-accent">OO</div>
          {!collapsed && <div className="leading-tight"><div className="text-sm font-bold grad-text whitespace-nowrap">Orbit Observers</div><div className="text-[11px] text-mute">Servicing Operations</div></div>}
        </div>
        <nav className="flex-1 py-2 overflow-y-auto">
          {NAV.filter((n) => ROLES[role].nav.includes(n.key)).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'} title={n.label}
              className={({ isActive }) => cn('flex items-center gap-3 px-4 py-2 text-sm text-mute hover:text-white hover:bg-panel2 border-l-2 border-transparent', isActive && 'text-white bg-gradient-to-r from-brand/30 to-transparent border-accent')}>
              <n.icon size={17} />{!collapsed && <span className="truncate">{n.label}</span>}
              {!collapsed && n.key === 'approvals' && pending > 0 && <span className="ml-auto text-[11px] bg-warn/20 text-warn rounded px-1.5">{pending}</span>}
            </NavLink>
          ))}
        </nav>
        <button className="h-10 border-t border-line grid place-items-center text-mute hover:text-white" onClick={() => setCollapsed(!collapsed)} aria-label="Toggle sidebar">
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 shrink-0 border-b border-line bg-panel/80 backdrop-blur flex items-center gap-4 px-4">
          <div className="hidden lg:flex items-center gap-4 text-xs text-mute">
            <button className="flex items-center gap-1.5 hover:text-white" onClick={() => api.setAutonomy(!auto)} title="Toggle autonomous agents" aria-pressed={auto}><Circle size={8} className={auto ? 'fill-ok text-ok' : 'fill-warn text-warn'} />Agents {auto ? 'autonomous' : 'paused'}{waiting > 0 && ` (${waiting} waiting for human)`}</button>
            <span>{active} active missions</span>
            <span className={crit ? 'text-bad' : ''}>{crit} critical</span>
            <span className={pending ? 'text-warn' : ''}>{pending} pending approvals</span>
          </div>
          <div className="ml-auto flex items-center gap-3">
            <DemoTag text="Demo - no real satellites" />
            <label className="sr-only" htmlFor="role">Role</label>
            <select id="role" className="input !py-1 !rounded-full" value={role} onChange={(e) => { setRole(e.target.value as Role); nav('/') }}>
              {(Object.keys(ROLES) as Role[]).map((r) => <option key={r} value={r}>{ROLES[r].label}</option>)}
            </select>
            <div className="relative">
              <button className="relative p-2 text-mute hover:text-white" onClick={() => setBell(!bell)} aria-label={`Notifications (${unread} unread)`}>
                <Bell size={18} />{unread > 0 && <span className="absolute top-0.5 right-0.5 text-[9px] bg-bad text-white rounded-full min-w-4 h-4 grid place-items-center px-1">{unread}</span>}
              </button>
              {bell && (
                <div className="absolute right-0 mt-2 w-80 card shadow-2xl z-40 max-h-96 overflow-y-auto">
                  <div className="flex justify-between px-3 py-2 border-b border-line text-xs"><span className="font-semibold">Notifications</span><button className="text-accent" onClick={markAll}>Mark all read</button></div>
                  {notes.length === 0 && <div className="p-4 text-sm text-mute">No notifications yet. Start the demo scenario.</div>}
                  {notes.slice(0, 30).map((n) => (
                    <button key={n.id} className={cn('w-full text-left px-3 py-2 border-b border-line text-sm hover:bg-panel2', !n.read && 'bg-accent/5')} onClick={() => { setBell(false); n.link && nav(n.link) }}>
                      {n.text}<div className="text-xs text-mute">{ago(n.ts)}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button className="btn" onClick={() => setConfirmReset(true)}><RotateCcw size={14} />Reset demo</button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          {loading ? (
            <div aria-busy="true" aria-label="Loading"><Skeleton className="h-7 w-64 mb-5" /><div className="grid grid-cols-4 gap-3 mb-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />)}</div><Skeleton className="h-72" /></div>
          ) : <Outlet />}
        </main>
      </div>
      <DemoGuide />
      <Modal open={confirmReset} onClose={() => setConfirmReset(false)} title="Reset demo data?"
        footer={<><button className="btn" onClick={() => setConfirmReset(false)}>Cancel</button><button className="btn btn-bad" onClick={() => { api.reset(); setConfirmReset(false); nav('/') }}>Reset</button></>}>
        <p className="text-sm text-mute">All local changes, approvals and logs return to the initial seeded state.</p>
      </Modal>
    </div>
  )
}
