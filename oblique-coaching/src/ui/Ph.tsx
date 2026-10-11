import type { ReactNode } from 'react'

// Placeholder visible : à remplacer par une vraie info client
export function Ph({ children }: { children: ReactNode }) {
  return (
    <span className="ph" title="À compléter avec une information réelle">
      {children}
    </span>
  )
}

// Rend automatiquement les segments [ ... ] d'une chaîne en placeholders
export function WithPh({ text }: { text: string }) {
  const parts = text.split(/(\[[^\]]+\])/g)
  return (
    <>
      {parts.map((p, i) => (p.startsWith('[') && p.endsWith(']') ? <Ph key={i}>{p}</Ph> : p))}
    </>
  )
}
