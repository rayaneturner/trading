import { m, useScroll, useTransform } from 'framer-motion'
import { useRef } from 'react'
import { ABOUT, BRAND, LINKS } from '../content'
import { Bolt } from '../ui/Bolt'
import { DiagonalMask } from '../ui/DiagonalMask'
import { Ph, WithPh } from '../ui/Ph'
import { FadeUp, RevealTitle } from '../ui/Reveal'

export function About() {
  const ref = useRef<HTMLElement>(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end start'] })
  const photoY = useTransform(scrollYProgress, [0, 1], ['6%', '-6%'])
  const boltY = useTransform(scrollYProgress, [0, 1], ['-14%', '14%'])

  return (
    <section
      id="a-propos"
      ref={ref}
      aria-labelledby="about-title"
      className="on-cream relative overflow-hidden bg-cream pb-20 pt-8 text-ink md:pb-28"
    >
      <div className="mx-auto grid max-w-7xl items-center gap-12 px-5 md:grid-cols-[0.9fr_1.1fr] md:gap-16 md:px-8">
        <div className="relative mx-auto w-full max-w-[420px]">
          <m.div aria-hidden="true" className="absolute -left-[8%] -top-[10%] h-[120%]" style={{ y: boltY }}>
            <Bolt className="h-full w-auto text-bolt" />
          </m.div>
          <m.div style={{ y: photoY }} className="relative">
            <DiagonalMask>
              <div className="relative aspect-[4/5] bg-wine">
                <div aria-hidden="true" className="grain absolute inset-0" />
                <img
                  src="/img/jahen.webp"
                  alt="Jahen Garçaut, coach sportif à Bourges, bras croisés, en t-shirt Oblique"
                  width={520}
                  height={520}
                  loading="lazy"
                  decoding="async"
                  className="absolute left-1/2 top-1/2 w-[82%] -translate-x-1/2 -translate-y-1/2 rounded-full ring-4 ring-bolt ring-offset-4 ring-offset-wine"
                />
                <p className="display oblique absolute bottom-4 left-5 text-2xl text-cream">{BRAND.coach}</p>
              </div>
            </DiagonalMask>
          </m.div>
        </div>

        <div>
          <p className="eyebrow mb-4 text-bolt-dark">À propos</p>
          <RevealTitle id="about-title" lines={ABOUT.title} className="text-[clamp(2.9rem,12vw,6rem)] text-wine" />
          <FadeUp className="mt-8 space-y-5 text-[17px] leading-relaxed text-ink/85">
            {ABOUT.paragraphs.map((p) => (
              <p key={p}>{p}</p>
            ))}
            <p>
              <WithPh text={ABOUT.story} />
            </p>
          </FadeUp>
          <FadeUp delay={0.1}>
            <ul
              aria-label="Diplômes et certifications"
              className="mt-8 flex flex-wrap gap-3 text-sm font-semibold uppercase tracking-[0.1em]"
            >
              {ABOUT.credentials.map((c) => (
                <li
                  key={c}
                  className="bg-wine px-4 py-2.5 text-cream [clip-path:polygon(6px_0,100%_0,calc(100%-6px)_100%,0_100%)]"
                >
                  <Ph>{c}</Ph>
                </li>
              ))}
            </ul>
            <a
              href={LINKS.instagram}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-8 inline-flex items-center gap-3 text-sm font-semibold uppercase tracking-[0.12em] text-wine underline decoration-bolt decoration-2 underline-offset-[6px]"
            >
              <svg
                viewBox="0 0 24 24"
                className="h-5 w-5"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
              >
                <rect x="3" y="3" width="18" height="18" rx="5" />
                <circle cx="12" cy="12" r="4" />
                <circle cx="17.5" cy="6.5" r="1" fill="currentColor" />
              </svg>
              Mes conseils au quotidien : @oblique.coaching
            </a>
          </FadeUp>
        </div>
      </div>
    </section>
  )
}
