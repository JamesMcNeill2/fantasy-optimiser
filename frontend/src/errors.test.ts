import { describe, expect, it } from 'vitest'
import { ApiError } from './api'
import { canRetry, errorText } from './errors'

describe('canRetry', () => {
  it('retries when the server could not be reached', () => {
    expect(canRetry(new ApiError(0, null))).toBe(true)
  })

  it('retries server failures', () => {
    expect(canRetry(new ApiError(502, 'Sleeper request failed'))).toBe(true)
    expect(canRetry(new ApiError(500, null))).toBe(true)
  })

  it('does not retry a bad request', () => {
    expect(canRetry(new ApiError(404, 'Team not found'))).toBe(false)
    expect(canRetry(new ApiError(422, null))).toBe(false)
  })

  it('does not retry an unexpected success response', () => {
    expect(canRetry(new ApiError(200, null))).toBe(false)
  })
})

describe('errorText', () => {
  it('explains a failed connection', () => {
    expect(errorText(new ApiError(0, null))).toBe(
      'Cannot reach the server. Check your connection.',
    )
  })

  it('blames Sleeper for a 502 from the api', () => {
    expect(errorText(new ApiError(502, 'Sleeper request failed'))).toBe(
      'Sleeper is not responding right now.',
    )
  })

  it('blames the server for a 502 with no detail', () => {
    expect(errorText(new ApiError(502, null))).toBe('The server is not responding.')
  })

  it('shows the detail for a 404', () => {
    expect(errorText(new ApiError(404, 'Team not found'))).toBe('Team not found.')
  })

  it('has a general message for other server errors', () => {
    expect(errorText(new ApiError(500, null))).toBe('Something went wrong on the server.')
  })

  it('has a general message for other bad requests', () => {
    expect(errorText(new ApiError(422, null))).toBe('Something went wrong with that request.')
  })

  it('explains a success status with a body that was not JSON', () => {
    expect(errorText(new ApiError(200, null))).toBe('The server sent an unexpected response.')
  })
})
