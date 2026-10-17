// Types for the api's responses. They mirror the Pydantic response models in
// services/api/app/main.py, so keep the two in step.

export interface League {
  key: number
  name: string
}

export interface Team {
  roster_id: number
  team_name: string
}

export interface RosterPlayer {
  player_id: string
  starter_slot: number | null
  reserve: boolean
  first_name: string | null
  last_name: string | null
  position: string | null
  team: string | null
  injury_status: string | null
  projected_points: number | null
  opponent: string | null
  game_status: string | null
  locked: boolean
  actual_points: number | null
}

export interface OptimalLineup {
  starter_ids: (string | null)[]
  bench_ids: string[]
  optimal_total: number
  current_total: number
}

export interface RosterResponse {
  players: RosterPlayer[]
  season: string
  week: number
  slots: string[]
  lineup: OptimalLineup
}

// URL paths for each route. Relative, so they work locally (through the
// Vite proxy) and deployed (through CloudFront) without changes.

export const leaguesPath = '/api/leagues'

export function teamsPath(leagueKey: number): string {
  return `/api/leagues/${leagueKey}/teams`
}

export function rosterPath(leagueKey: number, rosterID: number): string {
  return `/api/leagues/${leagueKey}/teams/${rosterID}/roster`
}

// A failed request. status is the HTTP status, or 0 if the server couldn't
// be reached. detail is the api's own error message, if it sent one.
export class ApiError extends Error {
  readonly status: number
  readonly detail: string | null

  constructor(status: number, detail: string | null) {
    super(detail ?? `Request failed (${status})`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

// GET a path and return its JSON body.
export async function getJson<T>(path: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(path)
  } catch {
    throw new ApiError(0, null)
  }
  if (!response.ok) {
    throw new ApiError(response.status, await readDetail(response))
  }
  try {
    return (await response.json()) as T
  } catch {
    // A success status but not JSON, e.g. the page itself if the proxy is missing
    throw new ApiError(response.status, null)
  }
}

// FastAPI errors look like {"detail": "Team not found"}. Anything else
// (a 422's list of problems, a CloudFront error page) gives null.
async function readDetail(response: Response): Promise<string | null> {
  try {
    const body: unknown = await response.json()
    if (
      typeof body === 'object' &&
      body !== null &&
      'detail' in body &&
      typeof body.detail === 'string'
    ) {
      return body.detail
    }
  } catch {
    // The body wasn't JSON
  }
  return null
}
