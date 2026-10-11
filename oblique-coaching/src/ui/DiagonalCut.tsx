// Coupe en biais entre deux sections, avec un filet rouge sur la diagonale
type Props = { from: string; to: string; flip?: boolean; line?: boolean }

export function DiagonalCut({ from, to, flip = false, line = true }: Props) {
  const poly = flip ? '0,0 100,100 0,100' : '0,100 100,0 100,100'
  const edge = flip ? 'M0,0 L100,100' : 'M0,100 L100,0'
  return (
    <div
      aria-hidden="true"
      className="relative -my-px h-[9vw] max-h-32 min-h-[44px] w-full"
      style={{ background: from }}
    >
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        <polygon points={poly} fill={to} />
        {line && <path d={edge} stroke="#E0262A" strokeWidth="3" vectorEffect="non-scaling-stroke" fill="none" />}
      </svg>
    </div>
  )
}
