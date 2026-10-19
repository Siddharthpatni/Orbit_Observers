import clsx, { type ClassValue } from 'clsx'
import type { Risk, Severity } from './types'

export const cn = (...a: ClassValue[]) => clsx(a)

export function rng(seed: number) {
  let s = seed >>> 0
  return () => {
    s = (s + 0x6d2b79f5) >>> 0
    let t = s
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export const riskFor = (h: number): Risk => (h >= 80 ? 'Low' : h >= 60 ? 'Elevated' : h >= 40 ? 'High' : 'Critical')
export const healthColor = (h: number) => (h >= 80 ? 'text-ok' : h >= 60 ? 'text-warn' : 'text-bad')
export const healthHex = (h: number) => (h >= 80 ? '#4ade80' : h >= 60 ? '#fcd34d' : '#ff7b7b')
export const riskTone: Record<Risk, string> = {
  Low: 'text-ok border-ok/70 bg-ok/15',
  Elevated: 'text-warn border-warn/70 bg-warn/15',
  High: 'text-orange-300 border-orange-400/70 bg-orange-400/15',
  Critical: 'text-bad border-bad/70 bg-bad/15',
}
export const sevTone: Record<Severity, string> = {
  info: 'text-info border-info/70 bg-info/15',
  low: 'text-ok border-ok/70 bg-ok/15',
  medium: 'text-warn border-warn/70 bg-warn/15',
  high: 'text-orange-300 border-orange-400/70 bg-orange-400/15',
  critical: 'text-bad border-bad/70 bg-bad/15',
}

export const fmtTime = (ts: number) => new Date(ts).toISOString().slice(11, 19) + 'Z'
export const fmtDT = (ts: number) => new Date(ts).toISOString().slice(0, 19).replace('T', ' ') + 'Z'
export const ago = (ts: number) => {
  const m = Math.round((Date.now() - ts) / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  if (m < 1440) return `${Math.round(m / 60)}h ago`
  return `${Math.round(m / 1440)}d ago`
}

export function download(name: string, content: string, mime: string) {
  const url = URL.createObjectURL(new Blob([content], { type: mime }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

export function toCSV(rows: Record<string, unknown>[]) {
  if (!rows.length) return ''
  const keys = Object.keys(rows[0])
  const esc = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`
  return [keys.join(','), ...rows.map((r) => keys.map((k) => esc(r[k])).join(','))].join('\n')
}

let n = 0
export const uid = (p: string) => `${p}-${(Date.now() % 1e6).toString(36).toUpperCase()}${(n++).toString(36).toUpperCase()}`
