import { LazyMotion, MotionConfig } from 'framer-motion'
import { useEffect } from 'react'
import { About } from './sections/About'
import { FAQ } from './sections/FAQ'
import { FinalCTA } from './sections/FinalCTA'
import { Footer } from './sections/Footer'
import { Header } from './sections/Header'
import { Hero } from './sections/Hero'
import { Marquee } from './sections/Marquee'
import { Method } from './sections/Method'
import { Problem } from './sections/Problem'
import { Services } from './sections/Services'
import { Stats } from './sections/Stats'
import { Testimonials } from './sections/Testimonials'
import { Zone } from './sections/Zone'
import { Cursor } from './ui/Cursor'
import { DiagonalCut } from './ui/DiagonalCut'
import { MobileCTA } from './ui/MobileCTA'
import { PitchNote } from './ui/PitchNote'
import { ScrollProgress } from './ui/ScrollProgress'

const loadFeatures = () => import('./motion-features').then((r) => r.default)

const C = {
  wine: '#3B0016',
  deep: '#24000D',
  cream: '#F5F1EA',
  ink: '#0B0B0B',
  red: '#D42227',
}

function useSmoothScroll() {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    let lenis: import('lenis').default | undefined
    let raf = 0
    let cancelled = false
    const onClick = (e: MouseEvent) => {
      const a = (e.target as HTMLElement).closest('a[href^="#"]') as HTMLAnchorElement | null
      if (!a || !lenis) return
      const id = a.getAttribute('href')!
      const el = id === '#top' ? document.body : document.querySelector(id)
      if (!el) return
      e.preventDefault()
      lenis.scrollTo(el as HTMLElement, { offset: id === '#top' ? 0 : -64 })
      history.replaceState(null, '', id)
    }
    // Chargé à la première interaction pour ne pas peser sur le chargement initial
    const events = ['wheel', 'pointermove', 'keydown'] as const
    const start = () => {
      events.forEach((ev) => window.removeEventListener(ev, start))
      import('lenis').then(({ default: Lenis }) => {
        if (cancelled) return
        lenis = new Lenis({ lerp: 0.11 })
        const loop = (t: number) => {
          lenis!.raf(t)
          raf = requestAnimationFrame(loop)
        }
        raf = requestAnimationFrame(loop)
      })
    }
    events.forEach((ev) => window.addEventListener(ev, start, { passive: true }))
    document.addEventListener('click', onClick)
    return () => {
      cancelled = true
      events.forEach((ev) => window.removeEventListener(ev, start))
      cancelAnimationFrame(raf)
      lenis?.destroy()
      document.removeEventListener('click', onClick)
    }
  }, [])
}

export default function App() {
  useSmoothScroll()
  return (
    <LazyMotion features={loadFeatures} strict>
      <MotionConfig reducedMotion="user">
        <a
          href="#contenu"
          className="sr-only z-[200] bg-cream px-4 py-3 font-semibold text-ink focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
        >
          Aller au contenu
        </a>
        <ScrollProgress />
        <Header />
        <main id="contenu">
          <Hero />
          <Marquee />
          <Problem />
          <DiagonalCut from={C.ink} to={C.wine} />
          <Method />
          <DiagonalCut from={C.wine} to={C.wine} line />
          <Services />
          <DiagonalCut from={C.wine} to={C.cream} />
          <Stats />
          <About />
          <DiagonalCut from={C.cream} to={C.ink} flip />
          <Testimonials />
          <DiagonalCut from={C.ink} to={C.wine} />
          <Zone />
          <DiagonalCut from={C.wine} to={C.cream} flip />
          <FAQ />
          <DiagonalCut from={C.cream} to={C.red} />
          <FinalCTA />
        </main>
        <Footer />
        <MobileCTA />
        <PitchNote />
        <Cursor />
      </MotionConfig>
    </LazyMotion>
  )
}
