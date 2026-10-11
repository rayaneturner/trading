import { Bolt } from './Bolt'

// Reprise du logo OBL⚡QUE : le "I" est remplacé par l'éclair
export function Logo({ className = '' }: { className?: string }) {
  return (
    <span className={`display oblique inline-flex items-center leading-none ${className}`} role="img" aria-label="Oblique">
      <span aria-hidden="true">OBL</span>
      <Bolt className="mx-[0.02em] h-[0.92em] w-auto text-bolt" />
      <span aria-hidden="true">QUE</span>
    </span>
  )
}
