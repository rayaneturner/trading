import { useMotionValueEvent, useScroll } from 'framer-motion'
import { useState } from 'react'
import { CTA, LINKS } from '../content'
import { Logo } from '../ui/Logo'

const NAV = [
  { href: '#methode', label: 'Méthode' },
  { href: '#services', label: 'Services' },
  { href: '#a-propos', label: 'À propos' },
  { href: '#faq', label: 'FAQ' },
]

export function Header() {
  const { scrollY } = useScroll()
  const [solid, setSolid] = useState(false)
  useMotionValueEvent(scrollY, 'change', (v) => setSolid(v > 40))

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-colors duration-300 ${
        solid ? 'bg-wine-deep/95 shadow-[0_1px_0_rgba(245,241,234,0.08)]' : 'bg-transparent'
      }`}
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 md:h-20 md:px-8">
        <a href="#top" className="text-[28px] md:text-[32px]">
          <Logo />
          <span className="sr-only"> – retour en haut de page</span>
        </a>
        <nav aria-label="Navigation principale" className="hidden md:block">
          <ul className="flex items-center gap-8 text-sm font-medium text-cream/85">
            {NAV.map((n) => (
              <li key={n.href}>
                <a href={n.href} className="transition-colors hover:text-cream">
                  {n.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <a
          href={LINKS.booking}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-primary hidden min-h-[44px] px-5 py-2.5 text-[13px] md:inline-flex"
          aria-label={`${CTA.primary} (nouvel onglet)`}
        >
          Réserver
        </a>
        <a href="#methode" className="text-xs font-semibold uppercase tracking-[0.18em] text-cream/80 md:hidden">
          La méthode
        </a>
      </div>
    </header>
  )
}
