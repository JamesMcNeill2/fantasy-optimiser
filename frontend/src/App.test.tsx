// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { League, RosterResponse, Team } from './api'
import App from './App'
import { ErrorBoundary } from './ErrorBoundary'
import { deferred, json, settle, setUpBrowserTests, stubFetch, type Routes } from './testHelpers'

setUpBrowserTests()

const LEAGUES: League[] = [
  { key: 0, name: 'Fourth Down Heroes' },
  { key: 1, name: 'End Zone Elite' },
]

const TEAMS: Team[] = [
  { roster_id: 3, team_name: 'Blitz Brigade', avatar: null },
  { roster_id: 8, team_name: 'Hail Marys', avatar: null },
]

const ROSTER: RosterResponse = {
  league_name: 'Fourth Down Heroes',
  team_name: 'Hail Marys',
  players: [
    {
      player_id: '1',
      starter_slot: 0,
      reserve: false,
      first_name: 'Sam',
      last_name: 'Starter',
      shirt_number: 17,
      position: 'QB',
      team: 'BUF',
      injury_status: null,
      projected_points: 21.5,
      opponent: 'MIA',
      game_status: 'pre_game',
      locked: false,
      actual_points: null,
    },
  ],
  season: '2026',
  week: 6,
  slots: ['QB'],
  lineup: { starter_ids: ['1'], bench_ids: [], optimal_total: 21.5, current_total: 21.5 },
}

// The api for league 0 and team 8. A test can replace or add any path.
function api(overrides: Routes = {}): Routes {
  return {
    '/api/leagues': () => json(LEAGUES),
    '/api/leagues/0/teams': () => json(TEAMS),
    '/api/leagues/0/teams/8/roster': () => json(ROSTER),
    ...overrides,
  }
}

describe('App', () => {
  it('opens a shared lineup link without showing the pickers on the way', async () => {
    window.history.replaceState(null, '', '/?league=0&team=8')
    const fetchMock = stubFetch(api())
    render(<App />)

    // All three requests start on the first render, before any has answered
    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      '/api/leagues',
      '/api/leagues/0/teams',
      '/api/leagues/0/teams/8/roster',
    ])
    expect(screen.getByRole('status').textContent).toBe('Loading lineup…')
    expect(screen.queryByText('Choose Your League')).toBeNull()

    // findBy… waits for the element, and fails the test if it never appears
    await screen.findByRole('heading', { name: 'Hail Marys' })
    expect(screen.getByText('Sam Starter')).toBeTruthy()
  })

  it('drops back to the team list for a stale team, without a "not found" message', async () => {
    window.history.replaceState(null, '', '/?league=0&team=999')
    const teams = deferred<Response>()
    stubFetch(
      api({
        '/api/leagues/0/teams': () => teams.promise,
        '/api/leagues/0/teams/999/roster': () => json({ detail: 'Team not found' }, 404),
      }),
    )
    render(<App />)

    // The roster's 404 has arrived, but the page waits for the team list
    await settle()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByRole('status').textContent).toBe('Loading lineup…')

    teams.resolve(json(TEAMS))
    await screen.findByRole('heading', { name: 'Fourth Down Heroes' })
    expect(screen.getByRole('link', { name: 'Hail Marys' })).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('steps through to a lineup, moving focus to each heading, and Back returns', async () => {
    stubFetch(api())
    render(<App />)

    fireEvent.click(await screen.findByRole('link', { name: 'Fourth Down Heroes' }))
    const leagueHeading = await screen.findByRole('heading', { name: 'Fourth Down Heroes' })
    expect(document.activeElement).toBe(leagueHeading)
    expect(window.location.search).toBe('?league=0')

    fireEvent.click(await screen.findByRole('link', { name: 'Hail Marys' }))
    await screen.findByRole('heading', { name: 'Hail Marys' })
    expect(window.location.search).toBe('?league=0&team=8')
    expect(document.title).toBe("Hail Marys · Mac's Fantasy Lineup Optimiser")

    window.history.back()
    await screen.findByRole('heading', { name: 'Fourth Down Heroes' })
    expect(window.location.search).toBe('?league=0')
  })

  it('shows the lineup and its header from the roster alone, before either list arrives', async () => {
    window.history.replaceState(null, '', '/?league=0&team=8')
    const leagues = deferred<Response>()
    const teams = deferred<Response>()
    stubFetch(
      api({
        '/api/leagues': () => leagues.promise,
        '/api/leagues/0/teams': () => teams.promise,
      }),
    )
    render(<App />)

    // The names come from the roster response: neither list has answered
    await screen.findByRole('heading', { name: 'Hail Marys' })
    expect(screen.getByRole('link', { name: 'Back to Fourth Down Heroes' })).toBeTruthy()
    expect(document.title).toBe("Hail Marys · Mac's Fantasy Lineup Optimiser")
    expect(screen.getByText('Sam Starter')).toBeTruthy()
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('keeps showing the lineup when a list fails', async () => {
    window.history.replaceState(null, '', '/?league=0&team=8')
    stubFetch(api({ '/api/leagues': () => json({ detail: 'Sleeper request failed' }, 502) }))
    render(<App />)

    await screen.findByRole('heading', { name: 'Hail Marys' })
    await settle()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByText('Sam Starter')).toBeTruthy()
  })

  it('moves focus to the lineup heading once the roster arrives', async () => {
    window.history.replaceState(null, '', '/?league=0')
    const roster = deferred<Response>()
    stubFetch(api({ '/api/leagues/0/teams/8/roster': () => roster.promise }))
    render(<App />)

    fireEvent.click(await screen.findByRole('link', { name: 'Hail Marys' }))
    expect(screen.getByRole('status').textContent).toBe('Loading lineup…')

    roster.resolve(json(ROSTER))
    const heading = await screen.findByRole('heading', { name: 'Hail Marys' })
    expect(document.activeElement).toBe(heading)
  })

  it('shows a refreshed team list and its header together, not the header first', async () => {
    window.history.replaceState(null, '', '/?league=0')
    const teams = deferred<Response>()
    stubFetch(api({ '/api/leagues/0/teams': () => teams.promise }))
    render(<App />)

    // The leagues list has arrived, but the header waits for the team list
    await settle()
    expect(screen.queryByRole('heading', { name: 'Fourth Down Heroes' })).toBeNull()
    expect(screen.getByRole('status').textContent).toBe('Loading teams…')

    teams.resolve(json(TEAMS))
    await screen.findByRole('heading', { name: 'Fourth Down Heroes' })
    expect(screen.getByRole('link', { name: 'Hail Marys' })).toBeTruthy()
  })

  it('keeps the team list header above its error', async () => {
    window.history.replaceState(null, '', '/?league=0')
    stubFetch(
      api({ '/api/leagues/0/teams': () => json({ detail: 'Sleeper request failed' }, 502) }),
    )
    render(<App />)

    await screen.findByRole('alert')
    expect(screen.getByRole('heading', { name: 'Fourth Down Heroes' })).toBeTruthy()
  })

  it('retries every failed request with one Try Again', async () => {
    window.history.replaceState(null, '', '/?league=0&team=8')
    let serverUp = false
    // Like the Vite proxy while uvicorn is down: a 502 with no JSON detail
    const throughProxy = (answer: () => Response) => () =>
      serverUp ? answer() : new Response('Bad Gateway', { status: 502 })
    stubFetch({
      '/api/leagues': throughProxy(() => json(LEAGUES)),
      '/api/leagues/0/teams': throughProxy(() => json(TEAMS)),
      '/api/leagues/0/teams/8/roster': throughProxy(() => json(ROSTER)),
    })
    render(<App />)

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('The server is not responding.')
    await settle() // all three failures are in

    serverUp = true
    fireEvent.click(screen.getByRole('button', { name: 'Try Again' }))
    await screen.findByRole('heading', { name: 'Hail Marys' })
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('shows a message, not a blank page, when a response has an unexpected shape', async () => {
    // React logs the caught error; keep the test output clean
    vi.spyOn(console, 'error').mockImplementation(() => {})
    // An object where the leagues list should be: App itself fails to render,
    // which only a boundary above App can catch
    stubFetch(api({ '/api/leagues': () => json({ leagues: LEAGUES }) }))
    render(
      <ErrorBoundary>
        <App />
      </ErrorBoundary>,
    )

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('Something went wrong showing this page.')
  })
})
