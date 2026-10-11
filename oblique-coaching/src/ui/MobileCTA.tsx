import { AnimatePresence, m, useMotionValueEvent, useScroll } from 'framer-motion'
import { useState } from 'react'
import { CTA, LINKS } from '../content'
import { Bolt } from './Bolt'

// Barre CTA collante sur mobile : apparaît après le hero
export function MobileCTA() {
  const { scrollY } = useScroll()
  const [show, setShow] = useState(false)
  useMotionValueEvent(scrollY, 'change', (v) => {
    const final = document.getElementById('reserver')
    const finalTop = final ? final.getBoundingClientRect().top : Infinity
    // Masquée pendant la section épinglée (elle couvrirait les cartes) et sur le CTA final
    const m = document.getElementById('methode')?.getBoundingClientRect()
    const pinned = !!m && m.top <= 0 && m.bottom >= window.innerHeight
    setShow(v > window.innerHeight * 0.85 && !pinned && finalTop > window.innerHeight * 0.6)
  })
  return (
    <AnimatePresence>
      {show && (
        <m.div
          initial={{ y: '120%' }}
          animate={{ y: 0 }}
          exit={{ y: '120%' }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="fixed inset-x-0 bottom-0 z-40 px-4 pb-[max(12px,env(safe-area-inset-bottom))] pt-3 md:hidden"
        >
          <a
            href={LINKS.booking}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary w-full shadow-[0_10px_30px_-8px_rgba(0,0,0,0.6)]"
            aria-label={`${CTA.primary} (nouvel onglet)`}
          >
            {CTA.primary}
            <Bolt className="h-4 w-auto" />
          </a>
        </m.div>
      )}
    </AnimatePresence>
  )
}
