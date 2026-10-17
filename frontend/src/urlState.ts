// The league and team picked, kept in the query string (?league=0&team=8)
// so a refresh keeps them and a link opens straight to a team.

export interface Selection {
  league: number | null
  team: number | null
}

// A whole number from the query string, or null if it's missing or not a number.
function readNumber(params: URLSearchParams, name: string): number | null {
  const value = params.get(name)
  return value !== null && /^\d+$/.test(value) ? Number(value) : null
}

export function readSelection(): Selection {
  const params = new URLSearchParams(window.location.search)
  const league = readNumber(params, 'league')
  return { league, team: league === null ? null : readNumber(params, 'team')}
}

// Update the address bar without reloading the page or adding a history entry.
export function writeSelection(selection: Selection): void {
  const params = new URLSearchParams()
  if (selection.league !== null) {
    params.set('league', String(selection.league))
    if (selection.team !== null) params.set('team', String(selection.team))
  }
  const query = params.toString()
  window.history.replaceState(null, '', query === '' ? window.location.pathname : `?${query}`)
}
