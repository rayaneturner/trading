import { m, useScroll, useTransform, type MotionValue } from 'framer-motion'
import { useRef } from 'react'
import { METHOD } from '../content'
import { DiagonalMask } from '../ui/DiagonalMask'
import { useReduced } from '../ui/hooks'
import { RevealTitle } from '../ui/Reveal'

type Step = (typeof METHOD)[number]

function StepCard({ step, index, progress }: { step: Step; index: number; progress?: MotionValue<number> }) {
  // Mobile : les étapes s'empilent au même endroit, chacune recouvre la précédente
  return (
    <li className={progress ? 'h-full [grid-area:stack] md:[grid-area:auto]' : ''} style={{ zIndex: index + 1 }}>
      <DiagonalMask progress={progress} className="h-full">
        <article className="relative flex h-full min-h-[270px] flex-col justify-between overflow-hidden bg-cream p-6 text-ink md:min-h-[400px] md:p-9">
          <span
            aria-hidden="true"
            className="display oblique absolute -right-3 -top-6 text-[9rem] leading-none text-wine/[0.07]"
          >
            {step.n}
          </span>
          <div>
            <p className="eyebrow text-bolt-dark">Étape {step.n}</p>
            <h3 className="display oblique mt-3 text-[2.6rem] md:text-6xl">{step.title}</h3>
          </div>
          <p className="mt-6 text-[16px] leading-relaxed text-ink/80 md:mt-8">{step.text}</p>
          <span aria-hidden="true" className="absolute bottom-0 left-0 h-1.5 w-full origin-left -skew-x-12 bg-bolt" />
        </article>
      </DiagonalMask>
    </li>
  )
}

function Progress({ progress }: { progress: MotionValue<number> }) {
  const scaleX = useTransform(progress, [0, 1], [0, 1])
  return (
    <div aria-hidden="true" className="mt-5 h-[3px] w-full bg-cream/15 md:mt-8">
      <m.div className="h-full origin-left bg-bolt" style={{ scaleX }} />
    </div>
  )
}

export function Method() {
  const ref = useRef<HTMLElement>(null)
  const reduced = useReduced()
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end end'] })

  // Transitions courtes, puis chaque étape reste lisible sur environ un quart de la course :
  // si le visiteur s'arrête de scroller, il tombe presque toujours sur une carte nette.
  const p0 = useTransform(scrollYProgress, [0, 0.06], [0, 1])
  const p1 = useTransform(scrollYProgress, [0.33, 0.41], [0, 1])
  const p2 = useTransform(scrollYProgress, [0.66, 0.74], [0, 1])
  const progresses = [p0, p1, p2]

  return (
    <section
      id="methode"
      ref={ref}
      aria-labelledby="methode-title"
      className={`relative bg-wine ${reduced ? '' : 'h-[300vh]'}`}
    >
      <div className={`${reduced ? 'py-16' : 'sticky top-0 flex h-[100svh] flex-col justify-center pb-5 pt-16'} md:py-24`}>
        <div className="mx-auto w-full max-w-7xl px-5 md:px-8">
          <div className="mb-6 flex flex-col gap-4 md:mb-14 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="eyebrow mb-3 text-cream/75 md:mb-4">La méthode Oblique</p>
              <RevealTitle
                id="methode-title"
                lines={['3 étapes.', 'Zéro improvisation.']}
                className="text-[clamp(2.3rem,10.5vw,6.5rem)]"
              />
            </div>
            <p className="hidden max-w-sm text-cream/80 md:block">
              Un cadre clair, du premier rendez-vous au résultat. Chaque étape prépare la suivante.
            </p>
          </div>
          <ol
            className={`grid md:grid-cols-3 md:gap-5 ${
              reduced ? 'gap-4' : "[grid-template-areas:'stack'] md:[grid-template-areas:none]"
            }`}
          >
            {METHOD.map((s, i) => (
              <StepCard key={s.n} step={s} index={i} progress={reduced ? undefined : progresses[i]} />
            ))}
          </ol>
          {!reduced && <Progress progress={scrollYProgress} />}
        </div>
      </div>
    </section>
  )
}
