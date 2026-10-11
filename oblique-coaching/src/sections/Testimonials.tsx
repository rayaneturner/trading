import { TESTIMONIALS } from '../content'
import { Bolt } from '../ui/Bolt'
import { Ph } from '../ui/Ph'
import { FadeUp, RevealTitle } from '../ui/Reveal'

export function Testimonials() {
  return (
    <section aria-labelledby="temoignages-title" className="relative bg-ink py-20 md:py-28">
      <div className="mx-auto max-w-7xl px-5 md:px-8">
        <p className="eyebrow mb-4 text-cream/75">Témoignages & transformations</p>
        <RevealTitle
          id="temoignages-title"
          lines={['Des résultats.', 'Leurs mots.']}
          className="text-[clamp(2.9rem,12vw,6.5rem)]"
        />
        <ul className="mt-12 grid gap-5 md:mt-16 md:grid-cols-3">
          {TESTIMONIALS.map((t, i) => (
            <li key={t.slot}>
              <FadeUp delay={i * 0.08} className="h-full">
                <figure className="flex h-full flex-col bg-wine-deep p-7 ring-1 ring-cream/10">
                  {/* Emplacement photo avant/après */}
                  <div
                    aria-hidden="true"
                    className="relative grid aspect-[4/3] grid-cols-2 overflow-hidden bg-gradient-to-br from-wine to-wine-deep"
                  >
                    <span className="eyebrow self-end p-3 text-cream/70">Avant</span>
                    <span className="eyebrow self-end justify-self-end p-3 text-cream/70">Après</span>
                    <span className="absolute left-1/2 top-[-10%] h-[120%] w-[3px] -translate-x-1/2 rotate-[14deg] bg-bolt" />
                    <Bolt className="absolute left-1/2 top-1/2 h-14 w-auto -translate-x-1/2 -translate-y-1/2 text-wine-soft" />
                  </div>
                  <blockquote className="mt-6 flex-1 text-lg leading-relaxed text-cream/85">
                    <Ph>[Témoignage client à venir]</Ph>
                  </blockquote>
                  <figcaption className="mt-6 border-t border-cream/10 pt-4 text-sm text-cream/75">
                    <Ph>[Prénom]</Ph> · {t.slot}
                  </figcaption>
                </figure>
              </FadeUp>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
