// Types for the api's responses, generated from its OpenAPI schema
// (npm run gen:api). To change one, change the Pydantic model in
// services/api/app/main.py and regenerate; never edit api-schema.ts.
import type { components } from './api-schema'

type Schemas = components['schemas']

export type League = Schemas['League']
export type Team = Schemas['Team']
export type RosterPlayer = Schemas['RosterPlayer']
export type OptimalLineup = Schemas['OptimalLineup']
export type RosterResponse = Schemas['RosterResponse']

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
