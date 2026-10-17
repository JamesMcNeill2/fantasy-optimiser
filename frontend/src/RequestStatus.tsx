import { ErrorMessage } from './ErrorMessage'
import type { ApiState } from './useApi'

interface RequestStatusProps {
  state: ApiState<unknown>
  loading: string
  onRetry: () => void
}

// A request's loading or error message. Idle and success show nothing here:
// what success looks like is up to the caller.
export function RequestStatus({ state, loading, onRetry }: RequestStatusProps) {
  if (state.status === 'loading') return <p>{loading}</p>
  if (state.status === 'error') return <ErrorMessage error={state.error} onRetry={onRetry} />
  return null
}
