import { animate, m, useInView, useMotionValue, useTransform, type MotionValue } from 'framer-motion'
import { useEffect, useRef, type ReactNode } from 'react'
import { useReduced } from './hooks'

type Props = {
  children: ReactNode
  /** Progression 0 → 1 pilotée par le scroll. Si absente, se déclenche à l'entrée dans le viewport. */
  progress?: MotionValue<number>
  className?: string
  delay?: number
}

// Masque diagonal 100 % transform : un conteneur incliné glisse, le contenu est contre-incliné
// et contre-translaté pour rester immobile. Le bord d'attaque porte une lame rouge.
export function DiagonalMask({ children, progress, className = '', delay = 0 }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '0px 0px -15% 0px' })
  const reduced = useReduced()
  const local = useMotionValue(0)
  const p = progress ?? local

  useEffect(() => {
    if (progress) return
    if (reduced) return local.set(1)
    if (inView) {
      const c = animate(local, 1, { duration: 1.1, ease: [0.7, 0, 0.2, 1], delay })
      return () => c.stop()
    }
  }, [inView, progress, reduced, local, delay])

  const maskX = useTransform(p, [0, 1], ['-101%', '0%'])
  // le masque fait 1,5× la largeur du contenu : la contre-translation doit être 1,5× plus grande
  const innerX = useTransform(p, [0, 1], ['151.5%', '0%'])
  const bladeOpacity = useTransform(p, [0, 0.85, 1], [1, 1, 0])

  return (
    <div ref={ref} className={`relative overflow-hidden ${className}`}>
      {/* overflow-hidden : c'est ce conteneur incliné qui découpe le contenu */}
      <m.div className="relative -ml-[25%] h-full w-[150%] overflow-hidden" style={{ x: maskX, skewX: -14 }}>
        <m.div className="ml-[16.6667%] h-full w-[66.6667%]" style={{ x: innerX, skewX: 14 }}>
          {children}
        </m.div>
        <m.span
          aria-hidden="true"
          className="absolute inset-y-0 right-0 w-2 bg-bolt"
          style={{ opacity: bladeOpacity }}
        />
      </m.div>
    </div>
  )
}
