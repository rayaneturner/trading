import { useState } from 'react'
import { BRAND, LEGAL, LINKS } from '../content'
import { Logo } from '../ui/Logo'
import { WithPh } from '../ui/Ph'

export function Footer() {
  const [legal, setLegal] = useState(false)
  return (
    <footer className="bg-ink pb-28 pt-16 text-cream md:pb-12">
      <div className="mx-auto max-w-7xl px-5 md:px-8">
        <div className="flex flex-col gap-10 md:flex-row md:items-end md:justify-between">
          <div>
            <Logo className="text-6xl md:text-7xl" />
            <p className="mt-3 text-cream/75">{BRAND.slogan}</p>
            <p className="mt-1 text-sm text-cream/70">
              {BRAND.coach} · Coach sportif & expert en nutrition · Bourges
            </p>
          </div>
          <nav aria-label="Liens du pied de page">
            <ul className="flex flex-wrap gap-x-6 gap-y-3 text-sm font-medium">
              <li><a className="hover:text-bolt-light" href="#methode">Méthode</a></li>
              <li><a className="hover:text-bolt-light" href="#services">Services</a></li>
              <li><a className="hover:text-bolt-light" href="#faq">FAQ</a></li>
              <li><a className="hover:text-bolt-light" href={LINKS.instagram} target="_blank" rel="noopener noreferrer">Instagram</a></li>
              <li><a className="hover:text-bolt-light" href={LINKS.linkedin} target="_blank" rel="noopener noreferrer">LinkedIn</a></li>
              <li><span className="text-cream/80"><WithPh text={LINKS.email} /></span></li>
            </ul>
          </nav>
        </div>

        <div className="mt-12 flex flex-col gap-4 border-t border-cream/10 pt-6 text-xs text-cream/70 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-4">
            <span>© {new Date().getFullYear()} {BRAND.name}</span>
            <button type="button" className="underline underline-offset-4 hover:text-cream" aria-expanded={legal} aria-controls="mentions" onClick={() => setLegal((v) => !v)}>
              Mentions légales
            </button>
          </div>
          <p className="text-cream/70">
            Maquette réalisée par <span className="font-semibold text-cream/80">ScaleSync</span>
          </p>
        </div>
        <div id="mentions" hidden={!legal} className="mt-4 space-y-1 text-xs leading-relaxed text-cream/70">
          {LEGAL.lines.map((l) => (
            <p key={l}>
              <WithPh text={l} />
            </p>
          ))}
        </div>
      </div>
    </footer>
  )
}
