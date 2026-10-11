import { m, useScroll, useTransform } from 'framer-motion'
import { useRef } from 'react'
import { CTA, HERO, LINKS } from '../content'
import { Bolt } from '../ui/Bolt'
import { MagneticLink } from '../ui/Magnetic'
import { EASE } from '../ui/Reveal'

const SWEEP_DELAY = 0.05
const LETTERS_DELAY = 0.3

function Letters({ text, offset, accent }: { text: string; offset: number; accent?: string }) {
  let i = offset
  return (
    <>
      {text.split(' ').map((word, w, words) => (
        <span key={w} className="inline-block whitespace-nowrap">
          {word.split('').map((ch, k) => {
            const idx = i++
            return (
              <m.span
                key={k}
                className={`inline-block ${accent && word.startsWith(accent) ? 'text-bolt' : ''}`}
                initial={{ x: '-0.35em', y: '105%' }}
                animate={{ x: 0, y: 0 }}
                transition={{ duration: 0.75, ease: EASE, delay: LETTERS_DELAY + idx * 0.03 }}
              >
                {ch}
              </m.span>
            )
          })}
          {w < words.length - 1 && ' '}
        </span>
      ))}
    </>
  )
}

export function Hero() {
  const ref = useRef<HTMLElement>(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end start'] })
  const boltY = useTransform(scrollYProgress, [0, 1], ['0%', '28%'])
  const textY = useTransform(scrollYProgress, [0, 1], ['0%', '-12%'])
  const [l1, l2] = HERO.lines

  return (
    <section
      id="top"
      ref={ref}
      aria-labelledby="hero-title"
      className="relative flex min-h-[100svh] flex-col justify-end overflow-hidden bg-wine pb-8 pt-24 md:pb-20 md:pt-28"
    >
      {/* Décor : grand éclair translucide (repris de la bannière) + grain */}
      <m.div aria-hidden="true" className="pointer-events-none absolute -right-[18%] -top-[6%] h-[115%] md:-right-[4%]" style={{ y: boltY }}>
        <Bolt className="h-full w-auto text-wine-soft opacity-70" />
      </m.div>
      <div aria-hidden="true" className="grain pointer-events-none absolute inset-0" />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-[10%] bottom-[22%] h-[2px] w-[140%] origin-left -rotate-[14deg] bg-bolt/70"
      />

      {/* Coupe diagonale rouge qui balaie l'écran à l'arrivée */}
      <m.div
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 left-0 z-20 w-[70%] bg-bolt"
        initial={{ x: '-160%', skewX: -14 }}
        animate={{ x: '260%' }}
        transition={{ duration: 1.05, ease: [0.7, 0, 0.25, 1], delay: SWEEP_DELAY }}
      />

      <m.div className="relative z-10 mx-auto w-full max-w-7xl px-5 md:px-8" style={{ y: textY }}>
        <m.p
          className="eyebrow mb-5 flex items-center gap-2 text-cream/85"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
        >
          <Bolt className="h-4 w-auto text-bolt" />
          {HERO.kicker}
        </m.p>

        <h1
          id="hero-title"
          aria-label="Reprenez le contrôle."
          className="display text-[clamp(4.4rem,22vw,13.5rem)] leading-[0.86]"
        >
          <span aria-hidden="true" className="oblique -mt-[0.4em] block overflow-hidden pr-[0.1em] pt-[0.4em]">
            <Letters text={l1} offset={0} />
          </span>
          <span aria-hidden="true" className="oblique -mt-[0.4em] block overflow-hidden pr-[0.1em] pt-[0.4em]">
            <Letters text={l2} offset={l1.length} accent="CONTRÔLE" />
          </span>
        </h1>

        <m.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: EASE, delay: 0.75 }}
          className="mt-5 grid gap-5 md:mt-10 md:gap-8 md:grid-cols-[1fr_auto] md:items-end"
        >
          <p className="max-w-xl text-base leading-relaxed text-cream/90 md:text-lg">{HERO.sub}</p>
          <div className="flex flex-col gap-3 sm:flex-row md:justify-end">
            <MagneticLink
              href={LINKS.booking}
              external
              className="btn btn-primary"
              ariaLabel={`${CTA.primary} (nouvel onglet)`}
            >
              {CTA.primary}
              <Bolt className="h-4 w-auto" />
            </MagneticLink>
            <a href="#methode" className="btn btn-ghost hidden sm:inline-flex">
              {CTA.secondary}
            </a>
            <a href="#methode" className="self-start py-2 text-sm font-semibold uppercase tracking-[0.12em] text-cream/85 underline decoration-bolt decoration-2 underline-offset-[6px] sm:hidden">
              {CTA.secondary}
            </a>
          </div>
        </m.div>

        <m.ul
          aria-label="En bref"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 1 }}
          className="mt-6 flex flex-wrap gap-x-5 gap-y-2 border-t border-cream/15 pt-4 md:mt-10 md:pt-5 text-[12px] font-medium uppercase tracking-[0.12em] text-cream/80 md:text-[13px]"
        >
          {HERO.proofs.map((p) => (
            <li key={p} className="flex items-center gap-2">
              <span aria-hidden="true" className="h-1.5 w-1.5 rotate-45 bg-bolt" />
              {p}
            </li>
          ))}
        </m.ul>
      </m.div>
    </section>
  )
}
