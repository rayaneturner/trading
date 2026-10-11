import { PROBLEM } from '../content'
import { Bolt } from '../ui/Bolt'
import { FadeUp, RevealTitle } from '../ui/Reveal'

export function Problem() {
  return (
    <section aria-labelledby="probleme-title" className="relative bg-ink py-20 md:py-28">
      <div className="mx-auto grid max-w-7xl gap-12 px-5 md:grid-cols-[1fr_1.1fr] md:gap-16 md:px-8">
        <div>
          <p className="eyebrow mb-4 text-cream/75">Vous vous reconnaissez ?</p>
          <RevealTitle id="probleme-title" lines={PROBLEM.title} className="text-[clamp(2.9rem,12vw,6rem)]" />
        </div>
        <div>
          <ol className="space-y-7">
            {PROBLEM.pains.map((p, i) => (
              <li key={p}>
                <FadeUp delay={i * 0.08} className="flex gap-5">
                  <span aria-hidden="true" className="display oblique w-10 shrink-0 text-3xl leading-none text-bolt">
                    0{i + 1}
                  </span>
                  <p className="text-[17px] leading-relaxed text-cream/85">{p}</p>
                </FadeUp>
              </li>
            ))}
          </ol>
          <FadeUp delay={0.2} className="mt-10 border-l-4 border-bolt bg-wine-deep p-6">
            <p className="text-lg font-medium leading-relaxed text-cream">{PROBLEM.promise}</p>
            <a
              href="#methode"
              className="mt-4 inline-flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.12em] text-cream underline decoration-bolt decoration-2 underline-offset-[6px]"
            >
              Voir la méthode
              <Bolt className="h-3.5 w-auto text-bolt" />
            </a>
          </FadeUp>
        </div>
      </div>
    </section>
  )
}
