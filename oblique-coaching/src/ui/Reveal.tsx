import { m, type Variants } from 'framer-motion'
import type { ReactNode } from 'react'

const EASE = [0.16, 1, 0.3, 1] as const

const container: Variants = { hidden: {}, show: { transition: { staggerChildren: 0.09 } } }
const line: Variants = {
  hidden: { y: '115%', skewY: 6 },
  show: { y: '0%', skewY: 0, transition: { duration: 0.9, ease: EASE } },
}

type TitleProps = {
  lines: ReactNode[]
  as?: 'h1' | 'h2' | 'h3'
  className?: string
  lineClassName?: string
  id?: string
}

// Titre révélé ligne par ligne : chaque ligne glisse en biais depuis un masque.
// Padding haut + marge négative : le masque laisse passer les accents (É, Ô) sans changer l'interlignage.
export function RevealTitle({ lines, as = 'h2', className = '', lineClassName = '', id }: TitleProps) {
  const Tag = m[as]
  return (
    <Tag
      id={id}
      className={`display ${className}`}
      variants={container}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: '0px 0px -12% 0px' }}
    >
      {lines.map((l, i) => (
        <span key={i} className="-mt-[0.16em] block overflow-hidden pb-[0.06em] pr-[0.12em] pt-[0.16em]">
          <m.span className={`oblique origin-bottom-left ${lineClassName}`} variants={line}>
            {l}
          </m.span>
        </span>
      ))}
    </Tag>
  )
}

// Apparition simple (opacité + translation) pour les blocs de texte
export function FadeUp({
  children,
  delay = 0,
  className = '',
}: {
  children: ReactNode
  delay?: number
  className?: string
}) {
  return (
    <m.div
      className={className}
      initial={{ opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '0px 0px -10% 0px' }}
      transition={{ duration: 0.8, ease: EASE, delay }}
    >
      {children}
    </m.div>
  )
}

export { EASE }
