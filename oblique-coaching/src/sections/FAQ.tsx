import { AnimatePresence, m } from 'framer-motion'
import { useId, useState } from 'react'
import { FAQ as ITEMS } from '../content'
import { WithPh } from '../ui/Ph'
import { RevealTitle } from '../ui/Reveal'

function Item({ q, a, defaultOpen }: { q: string; a: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(!!defaultOpen)
  const id = useId()
  return (
    <li className="border-b border-ink/15">
      <h3>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={`${id}-panel`}
          id={`${id}-btn`}
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center justify-between gap-6 py-6 text-left text-lg font-semibold md:text-xl"
        >
          {q}
          <span aria-hidden="true" className="relative h-5 w-5 shrink-0">
            <span className="absolute left-0 top-1/2 h-[2px] w-5 -translate-y-1/2 bg-bolt-dark" />
            <span
              className={`absolute left-1/2 top-0 h-5 w-[2px] -translate-x-1/2 bg-bolt-dark transition-transform duration-300 ${
                open ? 'scale-y-0' : 'scale-y-100'
              }`}
            />
          </span>
        </button>
      </h3>
      <div id={`${id}-panel`} role="region" aria-labelledby={`${id}-btn`} hidden={!open}>
        <AnimatePresence initial={false}>
          {open && (
            <m.p
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35 }}
              className="max-w-3xl pb-7 text-[16px] leading-relaxed text-ink/80"
            >
              <WithPh text={a} />
            </m.p>
          )}
        </AnimatePresence>
      </div>
    </li>
  )
}

export function FAQ() {
  return (
    <section id="faq" aria-labelledby="faq-title" className="on-cream bg-cream py-20 text-ink md:py-28">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 md:grid-cols-[0.8fr_1.2fr] md:px-8">
        <div>
          <p className="eyebrow mb-4 text-bolt-dark">Questions fréquentes</p>
          <RevealTitle
            id="faq-title"
            lines={['Avant de', 'commencer.']}
            className="text-[clamp(2.9rem,12vw,5.5rem)] text-wine"
          />
        </div>
        <ul className="border-t border-ink/15">
          {ITEMS.map((f, i) => (
            <Item key={f.q} q={f.q} a={f.a} defaultOpen={i === 0} />
          ))}
        </ul>
      </div>
    </section>
  )
}
