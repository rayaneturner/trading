import { m, useMotionValue, useSpring } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useFinePointer, useReduced } from './hooks'

// Curseur discret (anneau) en complément du curseur système. Desktop uniquement.
export function Cursor() {
  const fine = useFinePointer()
  const reduced = useReduced()
  const x = useMotionValue(-100)
  const y = useMotionValue(-100)
  const sx = useSpring(x, { stiffness: 500, damping: 40, mass: 0.3 })
  const sy = useSpring(y, { stiffness: 500, damping: 40, mass: 0.3 })
  const [hover, setHover] = useState(false)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!fine || reduced) return
    const move = (e: PointerEvent) => {
      x.set(e.clientX)
      y.set(e.clientY)
      setVisible(true)
      const t = e.target as HTMLElement | null
      setHover(!!t?.closest('a, button, [data-cursor]'))
    }
    const leave = () => setVisible(false)
    window.addEventListener('pointermove', move, { passive: true })
    document.documentElement.addEventListener('pointerleave', leave)
    return () => {
      window.removeEventListener('pointermove', move)
      document.documentElement.removeEventListener('pointerleave', leave)
    }
  }, [fine, reduced, x, y])

  if (!fine || reduced) return null
  return (
    <m.div
      aria-hidden="true"
      className="pointer-events-none fixed left-0 top-0 z-[100] -ml-4 -mt-4 h-8 w-8 rounded-full border-[1.5px] border-bolt mix-blend-difference"
      style={{ x: sx, y: sy }}
      animate={{ scale: hover ? 1.9 : 1, opacity: visible ? 1 : 0 }}
      transition={{ duration: 0.25 }}
    />
  )
}
