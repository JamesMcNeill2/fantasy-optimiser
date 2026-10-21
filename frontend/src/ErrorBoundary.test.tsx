// @vitest-environment jsdom
import { act, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ErrorBoundary } from './ErrorBoundary'
import { setUpBrowserTests } from './testHelpers'

setUpBrowserTests()

// Throws while rendering for as long as broken.now is true.
const broken = { now: true }
function Fragile() {
  if (broken.now) throw new Error('Unexpected data')
  return <p>Rendered fine</p>
}

// React logs every error a boundary catches; keep the test output clean.
// setUpBrowserTests restores console.error after each test.
function silenceReactErrorLog() {
  vi.spyOn(console, 'error').mockImplementation(() => {})
}

describe('ErrorBoundary', () => {
  it('shows its children when nothing fails', () => {
    broken.now = false
    render(
      <ErrorBoundary>
        <Fragile />
      </ErrorBoundary>,
    )

    expect(screen.getByText('Rendered fine')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('shows a message instead of a blank page when a child fails to render', () => {
    silenceReactErrorLog()
    broken.now = true
    render(
      <ErrorBoundary>
        <Fragile />
      </ErrorBoundary>,
    )

    expect(screen.getByRole('alert').textContent).toContain(
      'Something went wrong showing this page.',
    )
    expect(screen.getByRole('button', { name: 'Reload' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'All Leagues' }).getAttribute('href')).toBe('/')
  })

  it('tries again after Back or Forward', () => {
    silenceReactErrorLog()
    broken.now = true
    render(
      <ErrorBoundary>
        <Fragile />
      </ErrorBoundary>,
    )
    expect(screen.getByRole('alert')).toBeTruthy()

    broken.now = false
    act(() => {
      window.dispatchEvent(new PopStateEvent('popstate'))
    })
    expect(screen.getByText('Rendered fine')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})
