// The league and team picked, kept in the query string (?league=0&team=8)
// so a refresh keeps them, a link opens straight to a team, and the
// browser's Back button steps back through the choices.

import { useEffect, useState } from 'react'

export interface Selection {
  league: number | null
  team: number | null
}

// A whole number from the query string, or null if it's missing or not a number.
function readNumber(params: URLSearchParams, name: string): number | null {
  const value = params.get(name)
  return value !== null && /^\d+$/.test(value) ? Number(value) : null
}

function readSelection(): Selection {
  const params = new URLSearchParams(window.location.search)
  const league = readNumber(params, 'league')
  return { league, team: league === null ? null : readNumber(params, 'team')}
}

function selectionUrl(selection: Selection): string {
  const params = new URLSearchParams()
  if (selection.league !== null) {
    params.set('league', String(selection.league))
    if (selection.team !== null) params.set('team', String(selection.team))
  }
  const query = params.toString()
  return query === '' ? window.location.pathname : `?${query}`
}

// The current selection, and a function that changes it. Each change adds a
// history entry; Back and Forward restore earlier ones.
export function useSelection(): [Selection, (next: Selection) => void] {
  const [selection, setSelection] = useState(readSelection)

  useEffect(() => {
    const onPopState = () => setSelection(readSelection())
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  function choose(next: Selection) {
    window.history.pushState(null, '', selectionUrl(next))
    setSelection(next)
    window.scrollTo(0, 0)
  }

  return [selection, choose]
}
