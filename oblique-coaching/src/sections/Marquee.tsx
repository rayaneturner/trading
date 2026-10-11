import { Fragment } from 'react'
import { MARQUEE } from '../content'
import { Bolt } from '../ui/Bolt'

function Row() {
  return (
    <div className="flex shrink-0 items-center">
      {MARQUEE.map((m) => (
        <Fragment key={m}>
          <span className="display oblique whitespace-nowrap px-6 text-[clamp(2rem,7vw,4.5rem)] leading-none">{m}</span>
          <Bolt className="h-[clamp(1.6rem,5vw,3.4rem)] w-auto text-ink" />
        </Fragment>
      ))}
    </div>
  )
}

export function Marquee() {
  return (
    <section aria-label="Domaines d'intervention" className="relative z-10 overflow-hidden bg-wine py-6">
      <p className="sr-only">{MARQUEE.join(', ')}</p>
      <div aria-hidden="true" className="-mx-[5%] -rotate-[3deg] bg-bolt py-4 text-cream shadow-[0_20px_40px_-20px_rgba(0,0,0,0.6)]">
        <div className="marquee-track flex w-max">
          <Row />
          <Row />
        </div>
      </div>
    </section>
  )
}
