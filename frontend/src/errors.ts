// What to tell the user when a request fails, and whether to offer a retry.

import type { ApiError } from './api'

// Trying again can help when there was no response or the server failed.
// A 4xx means the request itself was wrong, so a retry would fail the same way.
export function canRetry(error: ApiError): boolean {
  return error.status === 0 || error.status >= 500
}

export function errorText(error: ApiError): string {
  if (error.status === 0) return 'Cannot reach the server. Check your connection.'
  if (error.status === 502) {
    // The api's 502 always has a detail; one without came from a proxy
    // (Vite locally, CloudFront deployed) that couldn't reach the api.
    return error.detail === null
      ? 'The server is not responding.'
      : 'Sleeper is not responding right now.'
  }
  if (error.status >= 500) return 'Something went wrong on the server.'
  if (error.status === 404 && error.detail !== null) return `${error.detail}.`
  if (error.status >= 200 && error.status < 300) {
    return 'The server sent an unexpected response.'
  }
  return 'Something went wrong with that request.'
}
