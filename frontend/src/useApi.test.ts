// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { deferred, json, settle, setUpBrowserTests, stubFetch } from './testHelpers'
import { useApi } from './useApi'

setUpBrowserTests()

describe('useApi', () => {
  it('is idle and fetches nothing without a path', () => {
    const fetchMock = stubFetch({})
    const { result } = renderHook(() => useApi(null))
    expect(result.current[0]).toEqual({ status: 'idle' })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('is loading until the response arrives, then has the data', async () => {
    stubFetch({ '/api/leagues': () => json(['a']) })
    const { result } = renderHook(() => useApi<string[]>('/api/leagues'))
    expect(result.current[0]).toEqual({ status: 'loading' })
    await waitFor(() => expect(result.current[0]).toEqual({ status: 'success', data: ['a'] }))
  })

  it('ignores a late response for a path it has moved on from', async () => {
    const slow = deferred<Response>()
    stubFetch({ '/api/old': () => slow.promise, '/api/new': () => json('new') })
    const { result, rerender } = renderHook(({ path }) => useApi<string>(path), {
      initialProps: { path: '/api/old' },
    })

    rerender({ path: '/api/new' })
    await waitFor(() => expect(result.current[0]).toEqual({ status: 'success', data: 'new' }))

    // The old request finally answers; it must not replace the new data
    slow.resolve(json('old'))
    await settle()
    expect(result.current[0]).toEqual({ status: 'success', data: 'new' })
  })

  it('runs the request again on retry', async () => {
    let calls = 0
    stubFetch({
      '/api/leagues': () => {
        calls += 1
        return calls === 1 ? new Response('', { status: 500 }) : json(['a'])
      },
    })
    const { result } = renderHook(() => useApi<string[]>('/api/leagues'))
    await waitFor(() => expect(result.current[0].status).toBe('error'))

    act(() => result.current[1]())
    expect(result.current[0]).toEqual({ status: 'loading' })
    await waitFor(() => expect(result.current[0]).toEqual({ status: 'success', data: ['a'] }))
  })
})
