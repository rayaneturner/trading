import { AnimatePresence, m } from 'framer-motion'
import { useEffect, useState } from 'react'
import { PITCH } from '../content'
import { Bolt } from './Bolt'

const KEY = 'oblique-pitch-note'

// Note destinée au prospect : cadre la maquette et rend les placeholders intentionnels
export function PitchNote() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!PITCH.enabled) return
    try {
      if (localStorage.getItem(KEY) === 'closed') return
    } catch {
      /* stockage indisponible : on affiche quand même */
    }
    // S'affiche quand le premier placeholder entre à l'écran : la note explique ce qu'il voit
    const target = document.querySelector('main .ph')
    if (!target) return
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setOpen(true)
          io.disconnect()
        }
      },
      { rootMargin: '0px 0px -25% 0px' },
    )
    io.observe(target)
    return () => io.disconnect()
  }, [])

  const close = () => {
    setOpen(false)
    try {
      localStorage.setItem(KEY, 'closed')
    } catch {
      /* rien */
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <m.aside
          role="note"
          aria-label="Note sur la maquette"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 16 }}
          transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
          className="on-cream fixed bottom-[88px] left-4 right-4 z-[55] bg-cream p-5 text-ink shadow-[0_24px_60px_-20px_rgba(0,0,0,0.7)] md:bottom-8 md:left-auto md:right-8 md:w-[380px]"
        >
          <span aria-hidden="true" className="absolute inset-y-0 left-0 w-1.5 bg-bolt" />
          <p className="flex items-center gap-2 pr-8 font-semibold leading-snug">
            <Bolt className="h-4 w-auto shrink-0 text-bolt-dark" />
            {PITCH.title}
          </p>
          <p className="mt-2 text-sm leading-relaxed text-ink/80">
            {PITCH.text.split(/(en pointillés)/).map((part, i) =>
              part === 'en pointillés' ? (
                <span key={i} className="ph">
                  en pointillés
                </span>
              ) : (
                part
              ),
            )}
          </p>
          <p className="mt-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink/70">Maquette {PITCH.by}</p>
          <button
            type="button"
            onClick={close}
            className="absolute right-2 top-2 grid h-11 w-11 place-items-center text-ink/70 hover:text-ink"
            aria-label="Fermer la note"
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
              <path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </m.aside>
      )}
    </AnimatePresence>
  )
}
