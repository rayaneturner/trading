import { useEffect, useState } from 'react'

function useMedia(query: string) {
  // false au premier rendu (identique au HTML pré-rendu), mis à jour après hydratation
  const [match, setMatch] = useState(false)
  useEffect(() => {
    const mq = window.matchMedia(query)
    const update = () => setMatch(mq.matches)
    update()
    mq.addEventListener('change', update)
    return () => mq.removeEventListener('change', update)
  }, [query])
  return match
}

export const useFinePointer = () => useMedia('(hover: hover) and (pointer: fine)')
export const useReduced = () => useMedia('(prefers-reduced-motion: reduce)')
export const useDesktop = () => useMedia('(min-width: 768px)')
