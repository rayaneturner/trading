import { m, useScroll, useTransform } from 'framer-motion'
import { useRef } from 'react'
import { BRAND, CTA, LINKS } from '../content'
import { Bolt } from '../ui/Bolt'
import { MagneticLink } from '../ui/Magnetic'
import { RevealTitle } from '../ui/Reveal'

function WhatsAppIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
      <path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4.2-.4.7-1.4.1-.2 0-.3 0-.5l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.7 11.8 11.8 0 0 0 4.5 4c1.7.7 2.3.8 3.2.6.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.1-1.2l-.4-.2z" />
    </svg>
  )
}

export function FinalCTA() {
  const ref = useRef<HTMLElement>(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end start'] })
  const boltY = useTransform(scrollYProgress, [0, 1], ['-20%', '20%'])

  return (
    <section
      id="reserver"
      ref={ref}
      aria-labelledby="cta-title"
      className="on-red relative flex min-h-[100svh] items-center overflow-hidden bg-bolt-cta py-24 text-cream"
    >
      {/* Diagonale sombre */}
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-bolt-dark [clip-path:polygon(62%_0,100%_0,100%_100%,28%_100%)]"
      />
      <m.div aria-hidden="true" className="absolute -right-[10%] top-0 h-full" style={{ y: boltY }}>
        <Bolt className="h-full w-auto text-ink/15" />
      </m.div>
      <div aria-hidden="true" className="grain absolute inset-0" />

      <div className="relative mx-auto w-full max-w-7xl px-5 md:px-8">
        <p className="eyebrow mb-5 text-cream">Premier bilan offert · sans engagement</p>
        <RevealTitle
          id="cta-title"
          lines={['Le premier pas,', 'c’est maintenant.']}
          className="text-[clamp(3.2rem,14vw,9.5rem)]"
        />
        <p className="mt-8 max-w-xl text-lg leading-relaxed text-cream">
          Réservez votre séance découverte : on fait le point sur vos objectifs et vous repartez avec un plan clair.
        </p>
        <div className="mt-10 flex flex-col gap-3 sm:flex-row">
          <MagneticLink
            href={LINKS.booking}
            external
            className="btn btn-dark"
            ariaLabel={`${CTA.primary} (nouvel onglet)`}
          >
            {CTA.primary}
            <Bolt className="h-4 w-auto text-bolt" />
          </MagneticLink>
          <a
            href={LINKS.whatsapp}
            target="_blank"
            rel="noopener noreferrer"
            className="btn bg-cream text-ink hover:bg-white"
            aria-label="Écrire sur WhatsApp (nouvel onglet)"
          >
            <WhatsAppIcon />
            WhatsApp
          </a>
        </div>
        <p className="display oblique mt-16 text-2xl text-cream/90 md:text-3xl">{BRAND.slogan}</p>
      </div>
    </section>
  )
}
