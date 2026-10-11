import { m, useMotionValue, useSpring, useTransform } from 'framer-motion'
import type { PointerEvent } from 'react'
import { CTA, LINKS, SERVICES, type Service } from '../content'
import { Bolt } from '../ui/Bolt'
import { useFinePointer, useReduced } from '../ui/hooks'
import { FadeUp, RevealTitle } from '../ui/Reveal'

function Card({ s, i }: { s: Service; i: number }) {
  const fine = useFinePointer()
  const reduced = useReduced()
  const tilt = fine && !reduced
  const px = useMotionValue(0)
  const py = useMotionValue(0)
  const rotateY = useSpring(useTransform(px, [-0.5, 0.5], [-7, 7]), { stiffness: 200, damping: 20 })
  const rotateX = useSpring(useTransform(py, [-0.5, 0.5], [6, -6]), { stiffness: 200, damping: 20 })
  const pro = s.id === 'entreprise'

  const onMove = (e: PointerEvent<HTMLElement>) => {
    if (!tilt) return
    const r = e.currentTarget.getBoundingClientRect()
    px.set((e.clientX - r.left) / r.width - 0.5)
    py.set((e.clientY - r.top) / r.height - 0.5)
  }
  const reset = () => {
    px.set(0)
    py.set(0)
  }

  return (
    <FadeUp delay={(i % 2) * 0.08} className="[perspective:1100px]">
      <m.article
        onPointerMove={onMove}
        onPointerLeave={reset}
        style={tilt ? { rotateX, rotateY } : undefined}
        className={`group relative flex h-full flex-col overflow-hidden p-7 [transform-style:preserve-3d] md:p-9 ${
          pro ? 'bg-ink text-cream ring-1 ring-bolt/60' : 'bg-wine-deep text-cream ring-1 ring-cream/10'
        }`}
      >
        {/* Éclair qui s'illumine au survol (opacité uniquement) */}
        <div aria-hidden="true" className="absolute -right-6 -top-4 h-44 md:h-52">
          <Bolt className="h-full w-auto text-wine-soft/60" />
          <Bolt className="absolute inset-0 h-full w-auto text-bolt opacity-0 blur-[18px] transition-opacity duration-500 group-hover:opacity-90" />
          <Bolt className="absolute inset-0 h-full w-auto text-bolt opacity-0 transition-opacity duration-500 group-hover:opacity-100" />
        </div>

        <p className={`eyebrow relative ${pro ? 'text-bolt-light' : 'text-cream/75'}`}>{s.tag}</p>
        <h3 className="display oblique relative mt-4 max-w-[12ch] text-[2.6rem] md:text-5xl" style={{ transform: 'translateZ(30px) skewX(-8deg)' }}>
          {s.title}
        </h3>
        <p className="relative mt-5 text-[16px] leading-relaxed text-cream/85">{s.text}</p>
        <ul className="relative mt-6 space-y-2 text-[15px] text-cream/90">
          {s.points.map((p) => (
            <li key={p} className="flex items-start gap-3">
              <span aria-hidden="true" className="mt-[0.55em] h-1.5 w-3 shrink-0 -skew-x-12 bg-bolt" />
              {p}
            </li>
          ))}
        </ul>
        {pro && (
          <a
            href={LINKS.booking}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary relative mt-8 self-start"
            aria-label="Planifier un échange pour votre entreprise (nouvel onglet)"
          >
            Planifier un échange
          </a>
        )}
      </m.article>
    </FadeUp>
  )
}

export function Services() {
  return (
    <section id="services" aria-labelledby="services-title" className="relative bg-wine py-20 md:py-28">
      <div className="mx-auto max-w-7xl px-5 md:px-8">
        <div className="mb-12 grid gap-6 md:mb-16 md:grid-cols-2 md:items-end">
          <div>
            <p className="eyebrow mb-4 text-cream/75">Services</p>
            <RevealTitle id="services-title" lines={['Un objectif.', 'Quatre terrains.']} className="text-[clamp(2.9rem,12vw,6.5rem)]" />
          </div>
          <FadeUp>
            <p className="max-w-md text-cream/85 md:justify-self-end">
              Particuliers, sportifs ou entreprises : la même exigence, un format adapté à chacun.
            </p>
          </FadeUp>
        </div>
        <div className="grid gap-5 md:grid-cols-2">
          {SERVICES.map((s, i) => (
            <Card key={s.id} s={s} i={i} />
          ))}
        </div>
        <FadeUp className="mt-12 flex justify-center">
          <a href={LINKS.booking} target="_blank" rel="noopener noreferrer" className="btn btn-primary" aria-label={`${CTA.primary} (nouvel onglet)`}>
            {CTA.primary}
            <Bolt className="h-4 w-auto" />
          </a>
        </FadeUp>
      </div>
    </section>
  )
}
