import { ErrorMessage } from './ErrorMessage'
import type { ApiState } from './useApi'

interface PageRequest {
  state: ApiState<unknown>
  onRetry: () => void
}

interface RequestStatusProps {
  requests: PageRequest[]
  loading: string
}

// The loading or error line for a page's requests, which are checked in
// order: the first one that hasn't succeeded decides what shows. Parent lists
// come first, so a stale id's 404 is never shown before the list that
// corrects it. Nothing shows once they've all succeeded.
export function RequestStatus({ requests, loading, }: RequestStatusProps) {
  // Try again re-runs every failed request, not just the one shown
  const retryFailed = () => {
    for (const request of requests) {
      if (request.state.status === 'error') request.onRetry()
    }
  }

  for (const { state } of requests) {
    if (state.status === 'loading') return <p role="status">{loading}</p>
    if (state.status === 'error') return <ErrorMessage error={state.error} onRetry={retryFailed} />
  }
  return null
}
