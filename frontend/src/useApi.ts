import { useEffect, useState } from 'react'
import { ApiError, getJson} from './api'

// What a component sees for one request. The status field says which shape
// it has, and TypeScript only allows data or error once status is checked.
export type ApiState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'success'; data: T }

// The last finished request, with the path and attempt it was for.
interface Settled<T> {
  path: string
  attempt: number
  state: ApiState<T>
}

// Fetch path whenever it changes. A null path means "nothing to fetch yet".
// Returns the current state and a function that runs the request again.
export function useApi<T>(path: string | null): [ApiState<T>, () => void] {
  const [attempt, setAttempt] = useState(0)
  const [settled, setSettled] = useState<Settled<T> | null>(null)

  useEffect(() => {
    if (path === null) return
    let ignore = false
    getJson<T>(path).then(
      (data) => {
        if (!ignore) setSettled({ path, attempt, state: { status: 'success', data } })
      },
    (error: unknown) => {
      const apiError = error instanceof ApiError ? error : new ApiError(0, null)
      if (!ignore) setSettled({ path, attempt, state: { status: 'error', error: apiError} })
    },
    )
    // Cleanup: runs when path or attempt changes before this request finishes,
    // so a slow, out-of-date response can't overwrite a newer one.
    return () => {
      ignore = true
    }
  }, [path, attempt])

  const retry = () => setAttempt((n) => n + 1)

  // Loading isn't stored: if the last finished request wasn't for this path
  // and attempt, the current one is still in flight.
  if (path === null) return [{ status: 'idle' }, retry]
  if (settled === null || settled.path !== path || settled.attempt !== attempt) {
    return [{ status: 'loading' }, retry]
  }
  return [settled.state, retry]
}
