// Shared set-up for the tests that render React in a simulated browser.

import { act, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'

// Call once at the top of a DOM test file. Before each test it stubs
// window.scrollTo (jsdom doesn't implement scrolling); after each it unmounts
// whatever the test rendered, puts the real fetch back and resets the address
// bar, so no test can affect the next.
export function setUpBrowserTests() {
  beforeEach(() => {
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  })
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    window.history.replaceState(null, '', '/')
  })
}

// A JSON response, the way the api sends one.
export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

// How the fake api answers each path. A function, so every request gets a
// fresh Response (a body can only be read once), or one a test releases later.
export type Routes = Record<string, () => Response | Promise<Response>>

// Replaces fetch with a fake that answers from routes; any other path gets a
// 404. Returns the fake, so a test can check which paths were requested.
export function stubFetch(routes: Routes) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const route = routes[String(input)]
    return Promise.resolve(route === undefined ? json({ detail: 'Not Found' }, 404) : route())
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

// A promise the test resolves when it chooses, to control the order in which
// responses arrive.
export function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

// Lets every response that has already arrived finish updating the page.
export function settle() {
  return act(() => new Promise<void>((done) => setTimeout(done, 0)))
}
