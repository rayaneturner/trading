type Props = { className?: string; title?: string }

// Éclair signature : même géométrie partout (logo, séparateurs, cartes, favicon)
export function Bolt({ className, title }: Props) {
  return (
    <svg
      viewBox="0 0 24 40"
      className={className}
      fill="currentColor"
      aria-hidden={title ? undefined : true}
      role={title ? 'img' : undefined}
    >
      {title && <title>{title}</title>}
      <path d="M16.5 0 2 23h8.5L6 40 22 15h-8.6L16.5 0z" />
    </svg>
  )
}
