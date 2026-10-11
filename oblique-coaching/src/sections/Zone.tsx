import { m } from 'framer-motion'
import { ZONE } from '../content'
import { Ph } from '../ui/Ph'
import { FadeUp, RevealTitle } from '../ui/Reveal'

// Carte stylisée (projection approximative, centre = Bourges)
function Map() {
  return (
    <svg viewBox="0 0 400 400" className="h-auto w-full" role="img" aria-labelledby="map-title map-desc">
      <title id="map-title">Zone d’intervention autour de Bourges</title>
      <desc id="map-desc">
        Bourges au centre, avec les communes voisines : {ZONE.towns.map((t) => t.name).join(', ')}.
      </desc>
      <defs>
        <pattern id="hatch" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(-35)">
          <line x1="0" y1="0" x2="0" y2="14" stroke="#F5F1EA" strokeOpacity="0.05" strokeWidth="1.5" />
        </pattern>
        <radialGradient id="zoneFill">
          <stop offset="0%" stopColor="#E0262A" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#E0262A" stopOpacity="0.04" />
        </radialGradient>
      </defs>
      <rect width="400" height="400" fill="url(#hatch)" />
      {/* Cours d'eau stylisés : l'Yèvre et le Cher */}
      <path
        d="M200 200 C175 192 150 178 128 167 S95 140 75 122 L30 95"
        fill="none"
        stroke="#F5F1EA"
        strokeOpacity="0.18"
        strokeWidth="2"
      />
      <path
        d="M190 400 C175 330 150 290 143 252 S105 170 75 122"
        fill="none"
        stroke="#F5F1EA"
        strokeOpacity="0.12"
        strokeWidth="2"
      />
      {/* Axes routiers */}
      <g stroke="#F5F1EA" strokeOpacity="0.08" strokeWidth="1.2">
        <line x1="200" y1="200" x2="0" y2="60" />
        <line x1="200" y1="200" x2="400" y2="240" />
        <line x1="200" y1="200" x2="230" y2="0" />
        <line x1="200" y1="200" x2="170" y2="400" />
      </g>
      {/* Zone d'intervention */}
      <m.g
        initial={{ scale: 0.6, opacity: 0 }}
        whileInView={{ scale: 1, opacity: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
        style={{ transformOrigin: '200px 200px' }}
      >
        <circle
          cx="200"
          cy="200"
          r="110"
          fill="url(#zoneFill)"
          stroke="#E0262A"
          strokeWidth="1.5"
          strokeDasharray="6 6"
        />
        <circle
          cx="200"
          cy="200"
          r="55"
          fill="none"
          stroke="#E0262A"
          strokeOpacity="0.5"
          strokeWidth="1"
          strokeDasharray="2 5"
        />
      </m.g>
      {ZONE.towns.map((t) => (
        <g key={t.name}>
          <circle cx={t.x} cy={t.y} r="3" fill="#F5F1EA" />
          <text
            x={t.x + (t.x > 200 ? 6 : -6)}
            y={t.y + 4}
            textAnchor={t.x > 200 ? 'start' : 'end'}
            fontSize="11"
            fontFamily="Inter, sans-serif"
            fill="#F5F1EA"
            fillOpacity="0.8"
          >
            {t.name}
          </text>
        </g>
      ))}
      <circle className="pulse-ring" cx="200" cy="200" r="9" fill="none" stroke="#E0262A" strokeWidth="2" />
      <circle cx="200" cy="200" r="8" fill="#E0262A" stroke="#F5F1EA" strokeWidth="2" />
      <text
        x="214"
        y="222"
        fontFamily="Anton, Impact, sans-serif"
        fontSize="26"
        fill="#F5F1EA"
        transform="skewX(-8)"
        style={{ transformBox: 'fill-box' }}
      >
        BOURGES
      </text>
    </svg>
  )
}

export function Zone() {
  return (
    <section aria-labelledby="zone-title" className="relative overflow-hidden bg-wine py-20 md:py-28">
      <div className="mx-auto grid max-w-7xl items-center gap-12 px-5 md:grid-cols-2 md:px-8">
        <div>
          <p className="eyebrow mb-4 text-cream/75">Zone d’intervention</p>
          <RevealTitle
            id="zone-title"
            lines={['Bourges', '& alentours.']}
            className="text-[clamp(2.9rem,12vw,6.5rem)]"
          />
          <FadeUp className="mt-8 space-y-4 text-[17px] leading-relaxed text-cream/85">
            <p>
              Séances à domicile, en extérieur ou dans vos locaux, dans un rayon de <Ph>{ZONE.radius}</Ph> autour de
              Bourges.
            </p>
            <p>Hors zone ? Le coaching en ligne vous suit partout.</p>
          </FadeUp>
        </div>
        <FadeUp className="mx-auto w-full max-w-[520px]">
          <Map />
        </FadeUp>
      </div>
    </section>
  )
}
