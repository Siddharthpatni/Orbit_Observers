import { useEffect, useState } from 'react'
import type { Satellite } from '@/lib/types'
import { healthHex } from '@/lib/util'

const R = { LEO: 62, SSO: 70, MEO: 100, GEO: 128 } as Record<string, number>

/** Illustrative 2D schematic - not to scale and not a propagated orbit. */
export function OrbitView({ sats, selected, onSelect, size = 320 }: { sats: Satellite[]; selected?: string; onSelect?: (id: string) => void; size?: number }) {
  const [t, setT] = useState(0)
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const i = setInterval(() => setT((x) => x + 1), 120)
    return () => clearInterval(i)
  }, [])
  const c = 150
  return (
    <svg viewBox="0 0 300 300" width={size} height={size} role="img" aria-label="Orbit schematic (illustrative, not to scale)" className="max-w-full">
      <circle cx={c} cy={c} r={28} fill="#0d52ad" stroke="#00c2ff" strokeOpacity={0.5} />
      {Object.entries(R).map(([k, r]) => (
        <g key={k}>
          <circle cx={c} cy={c} r={r} fill="none" stroke="#2c3544" strokeDasharray="2 4" />
          <text x={c + r * 0.72} y={c - r * 0.72} fontSize="8" fill="#cfd8e3">{k}</text>
        </g>
      ))}
      {sats.map((s) => {
        const r = R[s.orbit.regime] ?? 90
        const speed = 1 / Math.max(s.orbit.periodMin, 90) * 40
        const a = ((s.orbit.anomalyDeg + t * speed * 3) * Math.PI) / 180
        const x = c + r * Math.cos(a), y = c + r * Math.sin(a)
        const worst = Math.min(...s.components.map((k) => k.health))
        const sel = selected === s.id
        return (
          <g key={s.id} onClick={() => onSelect?.(s.id)} style={{ cursor: onSelect ? 'pointer' : 'default' }}>
            {s.kind === 'servicer' ? <rect x={x - 4} y={y - 4} width={8} height={8} fill="#00c2ff" transform={`rotate(45 ${x} ${y})`} /> : <circle cx={x} cy={y} r={sel ? 5.5 : 3.5} fill={healthHex(worst)} stroke={sel ? '#fff' : 'none'} />}
            {(sel || s.kind === 'servicer') && <text x={x + 7} y={y + 3} fontSize="8" fill="#ffffff">{s.id}</text>}
          </g>
        )
      })}
    </svg>
  )
}
