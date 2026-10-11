import { m, useMotionValue, useSpring } from 'framer-motion'
import type { ReactNode, PointerEvent } from 'react'
import { useFinePointer, useReduced } from './hooks'

type Props = {
  href: string
  children: ReactNode
  className?: string
  external?: boolean
  ariaLabel?: string
}

// Bouton magnétique : attiré par le pointeur sur desktop uniquement
export function MagneticLink({ href, children, className = '', external, ariaLabel }: Props) {
  const fine = useFinePointer()
  const reduced = useReduced()
  const active = fine && !reduced
  const x = useSpring(useMotionValue(0), { stiffness: 220, damping: 18, mass: 0.4 })
  const y = useSpring(useMotionValue(0), { stiffness: 220, damping: 18, mass: 0.4 })

  const onMove = (e: PointerEvent<HTMLAnchorElement>) => {
    if (!active) return
    const r = e.currentTarget.getBoundingClientRect()
    x.set((e.clientX - (r.left + r.width / 2)) * 0.28)
    y.set((e.clientY - (r.top + r.height / 2)) * 0.4)
  }
  const reset = () => {
    x.set(0)
    y.set(0)
  }

  return (
    <m.a
      href={href}
      className={className}
      style={{ x, y }}
      onPointerMove={onMove}
      onPointerLeave={reset}
      aria-label={ariaLabel}
      data-cursor="cta"
      {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
    >
      {children}
    </m.a>
  )
}
