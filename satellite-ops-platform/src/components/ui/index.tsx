import { useEffect, useRef, type ReactNode } from 'react'
import { X, Info, CircleAlert, TriangleAlert, OctagonAlert, CircleCheck, CircleDot } from 'lucide-react'
import { cn, riskTone, sevTone } from '@/lib/util'
import type { Risk, Severity } from '@/lib/types'

export const Card = ({ className, children, onClick }: { className?: string; children: ReactNode; onClick?: () => void }) => (
  <div className={cn('card', onClick && 'cursor-pointer hover:border-accent/50 transition', className)} onClick={onClick}
    role={onClick ? 'button' : undefined} tabIndex={onClick ? 0 : undefined} onKeyDown={onClick ? (e) => (e.key === 'Enter' || e.key === ' ') && onClick() : undefined}>{children}</div>
)

export const CardHeader = ({ title, right, sub }: { title: string; right?: ReactNode; sub?: string }) => (
  <div className="flex items-center justify-between px-4 py-3 border-b border-line">
    <div><h3 className="text-sm font-semibold">{title}</h3>{sub && <p className="text-xs text-mute">{sub}</p>}</div>{right}
  </div>
)

export const PageHeader = ({ title, sub, actions }: { title: string; sub?: string; actions?: ReactNode }) => (
  <div className="flex flex-wrap items-end justify-between gap-3 mb-5">
    <div><h1 className="text-2xl font-bold tracking-tight grad-text w-fit">{title}</h1>{sub && <p className="text-sm text-mute mt-0.5">{sub}</p>}</div>
    <div className="flex gap-2 flex-wrap">{actions}</div>
  </div>
)

export const Badge = ({ children, tone }: { children: ReactNode; tone?: string }) => (
  <span className={cn('inline-flex items-center px-2.5 py-0.5 rounded-full border text-xs font-medium whitespace-nowrap', tone ?? 'border-line text-mute')}>{children}</span>
)
const RiskIcon = ({ level }: { level: number }) => {
  const p = { size: 11, className: 'mr-1', 'aria-hidden': true as const }
  return level === 0 ? <CircleCheck {...p} /> : level === 1 ? <CircleDot {...p} /> : level === 2 ? <TriangleAlert {...p} /> : <OctagonAlert {...p} />
}
export const RiskBadge = ({ risk }: { risk: Risk }) => <Badge tone={riskTone[risk]}><RiskIcon level={['Low', 'Elevated', 'High', 'Critical'].indexOf(risk)} />{risk} risk</Badge>
export const SevBadge = ({ sev }: { sev: Severity }) => <Badge tone={sevTone[sev]}><RiskIcon level={['info', 'low', 'medium', 'high', 'critical'].indexOf(sev) <= 1 ? 0 : sev === 'medium' ? 1 : sev === 'high' ? 2 : 3} />{sev}</Badge>

const stateTone: Record<string, string> = {
  Nominal: 'text-ok border-ok/70 bg-ok/15', Attention: 'text-warn border-warn/70 bg-warn/15', Servicing: 'text-accent border-accent/70 bg-accent/15',
  Hold: 'text-bad border-bad/70 bg-bad/15', Standby: 'text-mute border-line',
  pending: 'text-warn border-warn/70 bg-warn/15', approved: 'text-ok border-ok/70 bg-ok/15', rejected: 'text-bad border-bad/70 bg-bad/15',
  hold: 'text-orange-300 border-orange-400/70 bg-orange-400/15', 'info-requested': 'text-info border-info/70 bg-info/15',
  allowed: 'text-ok border-ok/70 bg-ok/15', denied: 'text-bad border-bad/70 bg-bad/15', 'approval required': 'text-warn border-warn/70 bg-warn/15',
  Active: 'text-accent border-accent/70 bg-accent/15', Closed: 'text-mute border-line', Failed: 'text-bad border-bad/70 bg-bad/15', Requested: 'text-warn border-warn/70 bg-warn/15',
  Blocked: 'text-bad border-bad/70 bg-bad/15', Completed: 'text-ok border-ok/70 bg-ok/15', Scheduled: 'text-info border-info/70 bg-info/15',
  ack: 'text-ok border-ok/70 bg-ok/15', error: 'text-bad border-bad/70 bg-bad/15', authorized: 'text-ok border-ok/70 bg-ok/15',
  Monitoring: 'text-ok border-ok/70 bg-ok/15', Analyzing: 'text-accent border-accent/70 bg-accent/15', Idle: 'text-mute border-line',
  'Awaiting human': 'text-warn border-warn/70 bg-warn/15', Planning: 'text-info border-info/70 bg-info/15',
}
export const StatusBadge = ({ s }: { s: string }) => {
  const bad = ['Hold', 'rejected', 'denied', 'Failed', 'Blocked', 'error'].includes(s)
  const warn = ['Attention', 'pending', 'approval required', 'Awaiting human', 'Requested', 'hold', 'info-requested'].includes(s)
  const Ic = bad ? OctagonAlert : warn ? CircleAlert : CircleCheck
  return <Badge tone={stateTone[s]}><Ic size={11} className="mr-1" aria-hidden />{s}</Badge>
}

export const Skeleton = ({ className }: { className?: string }) => <div className={cn('skeleton', className)} aria-hidden />

export const DemoTag = ({ text = 'Simulated demo data' }: { text?: string }) => (
  <span className="inline-flex items-center gap-1 text-[11px] uppercase tracking-wider text-warn/90 border border-warn/30 rounded px-1.5 py-0.5"><Info size={10} />{text}</span>
)

export const Empty = ({ text }: { text: string }) => <div className="text-sm text-mute text-center py-10">{text}</div>

export function Stat({ label, value, sub, tone, onClick }: { label: string; value: ReactNode; sub?: string; tone?: string; onClick?: () => void }) {
  return (
    <Card onClick={onClick} className="p-4">
      <div className="text-xs uppercase tracking-wider text-mute">{label}</div>
      <div className={cn('text-2xl font-semibold mt-1', tone)}>{value}</div>
      {sub && <div className="text-xs text-mute mt-0.5">{sub}</div>}
    </Card>
  )
}

export function HealthBar({ v }: { v: number }) {
  const c = v >= 80 ? 'bg-ok' : v >= 60 ? 'bg-warn' : 'bg-bad'
  return <div className="h-1.5 rounded bg-line overflow-hidden"><div className={cn('h-full', c)} style={{ width: `${v}%` }} /></div>
}

export function Drawer({ open, onClose, title, children, width = 'max-w-xl' }: { open: boolean; onClose: () => void; title: string; children: ReactNode; width?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    ref.current?.focus()
    return () => window.removeEventListener('keydown', h)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div ref={ref} tabIndex={-1} className={cn('relative w-full bg-panel border-l border-line overflow-y-auto outline-none', width)}>
        <div className="sticky top-0 bg-panel border-b border-line px-5 py-3 flex items-center justify-between z-10">
          <h2 className="font-semibold">{title}</h2>
          <button className="text-mute hover:text-white" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}

export function Modal({ open, onClose, title, children, footer }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode }) {
  useEffect(() => {
    if (!open) return
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="relative card w-full max-w-md p-5 shadow-2xl">
        <h2 className="font-semibold mb-3">{title}</h2>
        {children}
        {footer && <div className="flex justify-end gap-2 mt-4">{footer}</div>}
      </div>
    </div>
  )
}

export function Sparkline({ data, color = '#00c2ff', warn }: { data: number[]; color?: string; warn?: number }) {
  const w = 120, h = 32
  const max = Math.max(...data, warn ?? 0), min = Math.min(...data)
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / (max - min || 1)) * (h - 4) - 2}`).join(' ')
  return (
    <svg width={w} height={h} aria-hidden>
      {warn !== undefined && <line x1="0" x2={w} y1={h - ((warn - min) / (max - min || 1)) * (h - 4) - 2} y2={h - ((warn - min) / (max - min || 1)) * (h - 4) - 2} stroke="#fcd34d" strokeDasharray="3 3" strokeWidth="1" />}
      <polyline fill="none" stroke={color} strokeWidth="1.5" points={pts} />
    </svg>
  )
}
