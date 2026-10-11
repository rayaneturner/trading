import { animate, useInView } from 'framer-motion'
import { useEffect, useRef } from 'react'
import { STATS } from '../content'
import { useReduced } from '../ui/hooks'
import { Ph } from '../ui/Ph'
import { FadeUp } from '../ui/Reveal'

function Counter({ value, prefix = '', suffix = '' }: { value: number; prefix?: string; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true, margin: '0px 0px -10% 0px' })
  const reduced = useReduced()

  useEffect(() => {
    const el = ref.current
    if (!el || !inView || reduced) return
    const c = animate(0, value, {
      duration: 1.6,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => (el.textContent = `${prefix}${Math.round(v)}${suffix}`),
    })
    return () => c.stop()
  }, [inView, reduced, value, prefix, suffix])

  // Valeur finale dans le HTML : lisible sans JS et pour les lecteurs d'écran
  return (
    <span ref={ref} className="tabular-nums">
      {`${prefix}${value}${suffix}`}
    </span>
  )
}

export function Stats() {
  return (
    <section aria-label="Chiffres clés" className="on-cream relative bg-cream py-16 text-ink md:py-24">
      <ul className="mx-auto grid max-w-7xl grid-cols-2 gap-x-5 gap-y-12 px-5 md:grid-cols-4 md:px-8">
        {STATS.map((s, i) => (
          <li key={s.label}>
            <FadeUp delay={i * 0.06}>
              <p className="display oblique text-[clamp(3.4rem,15vw,6.5rem)] leading-none text-wine">
                {s.value === null ? (
                  <span className="text-[0.62em] text-bolt-dark">
                    <Ph>[XX]</Ph>
                  </span>
                ) : (
                  <Counter value={s.value} prefix={s.prefix} suffix={s.suffix} />
                )}
              </p>
              <p className="mt-3 h-px w-10 bg-bolt" aria-hidden="true" />
              <p className="mt-3 text-[15px] font-medium leading-snug text-ink/80">{s.label}</p>
            </FadeUp>
          </li>
        ))}
      </ul>
    </section>
  )
}
