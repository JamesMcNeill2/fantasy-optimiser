import type { ApiError } from './api'
import { canRetry, errorText } from './errors'

interface ErrorMessageProps {
  error: ApiError
  onRetry: () => void
}

// A failed request's message, with a Try Again button when retrying could help.
export function ErrorMessage({ error, onRetry }: ErrorMessageProps) {
  return (
    <p role="alert" className="error">
      {errorText(error)}
      {canRetry(error) && (
        <>
          {' '}
          <button type="button" onClick={onRetry}>
            Try Again
          </button>
        </>
      )}
    </p>
  )
}
